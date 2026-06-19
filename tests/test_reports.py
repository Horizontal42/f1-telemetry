import os
import dataclasses
import pytest
import telemetry.report_technique as rt
import telemetry.report_setup as rs
import telemetry.report_compare as rc
import telemetry.report_race as rr
import telemetry.report_profile as rp
from telemetry.__main__ import is_fresh
from telemetry.parser import Lap
from telemetry import report_common
from telemetry.report_common import game_of, load_prompt


def _check(result, path):
    abs_path, tokens = result
    assert tokens > 0
    assert os.path.isabs(abs_path)
    assert os.path.isfile(abs_path)
    assert os.path.getsize(abs_path) > 0
    assert abs_path == os.path.abspath(path)


def test_technique_generate(sample_lap, tmp_path):
    out = str(tmp_path / "out_technique.md")
    result = rt.generate(sample_lap, out)
    _check(result, out)


def test_setup_generate(sample_lap, tmp_path):
    out = str(tmp_path / "out_setup.md")
    result = rs.generate(sample_lap, out)
    _check(result, out)


def test_compare_generate_same_lap(sample_lap, tmp_path):
    out = str(tmp_path / "out_compare.md")
    result = rc.generate([sample_lap, sample_lap], out)
    _check(result, out)


def test_race_generate_same_lap(sample_lap, tmp_path):
    out = str(tmp_path / "out_race.md")
    result = rr.generate([sample_lap, sample_lap], out)
    _check(result, out)


def test_technique_output_contains_corners(sample_lap, tmp_path):
    out = str(tmp_path / "tech_corners.md")
    rt.generate(sample_lap, out)
    with open(out, encoding="utf-8") as f:
        text = f.read()
    assert "## Corners" in text
    assert "## Trace" in text


def test_setup_output_contains_setup(sample_lap, tmp_path):
    out = str(tmp_path / "setup_check.md")
    rs.generate(sample_lap, out)
    with open(out, encoding="utf-8") as f:
        text = f.read()
    assert "## Setup" in text
    assert "## Tyres" in text


def test_dedup_laps_prefers_valid():
    invalid_fast = Lap(
        session={'laptime': '113.5'},
        track={'Lap': '8', 'Valid': 'false'},
        setup={},
        ch={},
        n=0,
    )
    valid_slow = Lap(
        session={'laptime': '115.2'},
        track={'Lap': '8', 'Valid': 'true'},
        setup={},
        ch={},
        n=0,
    )
    result = rr._dedup_laps([invalid_fast, valid_slow])
    assert len(result) == 1
    assert result[0].track['Valid'] == 'true'


def _variant(lap, *, laptime=None, lap_no=None, fuel=None, tyre=None):
    session = dict(lap.session)
    track = dict(lap.track)
    if laptime is not None:
        session['laptime'] = str(laptime)
    if lap_no is not None:
        track['Lap'] = str(lap_no)
    if fuel is not None:
        track['Fuel at Start'] = str(fuel)
    if tyre is not None:
        track['Tyre'] = tyre
    return dataclasses.replace(lap, session=session, track=track)


def test_include_prompt_toggle(sample_lap, tmp_path):
    with_p = str(tmp_path / "with.md")
    no_p = str(tmp_path / "no.md")
    rt.generate(sample_lap, with_p, 'ru', include_prompt=True)
    rt.generate(sample_lap, no_p, 'ru', include_prompt=False)
    a = open(with_p, encoding="utf-8").read()
    b = open(no_p, encoding="utf-8").read()
    assert len(b) < len(a)
    assert "## Trace" in b  # data kept
    assert "Начинай анализ" not in b  # prompt dropped
    assert "Начинай анализ" in a


def test_compare_verdict_fuel_correction_range(sample_lap, tmp_path):
    lap_a = _variant(sample_lap, laptime=100.0, fuel=60.0)
    lap_b = _variant(sample_lap, laptime=99.0, fuel=40.0)
    out = str(tmp_path / "cmp.md")
    rc.generate([lap_a, lap_b], out, 'ru', include_prompt=False)
    text = open(out, encoding="utf-8").read()
    assert "## Verdict" in text
    # fuel benefit (60-40)*[0.03..0.05] = 0.6..1.0 ; residual = -1.0 - [1.0..0.6] = -2.0..-1.6
    assert "-2.000" in text and "-1.600" in text


def test_profile_sections_and_pick(sample_lap, tmp_path):
    laps = [
        _variant(sample_lap, lap_no=1, laptime=80.0, tyre='C3'),
        _variant(sample_lap, lap_no=2, laptime=75.0, tyre='C3'),
        _variant(sample_lap, lap_no=3, laptime=78.0, tyre='C3'),
    ]
    out = str(tmp_path / "prof.md")
    rp.generate(laps, out, 'ru', include_prompt=False)
    text = open(out, encoding="utf-8").read()
    assert "Тенденции по поворотам" in text
    assert "Рекомендованные круги" in text
    assert "L2" in text  # fastest valid lap picked


def test_profile_covers_multiple_compounds(sample_lap, tmp_path):
    laps = (
        [_variant(sample_lap, lap_no=i, laptime=80.0, tyre='C3') for i in range(1, 4)]
        + [_variant(sample_lap, lap_no=i, laptime=82.0, tyre='C2') for i in range(4, 7)]
    )
    out = str(tmp_path / "prof_multi.md")
    rp.generate(laps, out, 'ru', include_prompt=False)
    text = open(out, encoding="utf-8").read()
    assert "состав C3" in text
    assert "состав C2" in text  # secondary compound not ignored


def test_merge_gap_scales_with_track_length(sample_lap):
    from telemetry.segments import merge_gap_for, MERGE_GAP_M, MERGE_GAP_MIN, MERGE_GAP_MAX
    # sample lap is Zandvoort (~4257 m) → anchor, unchanged
    assert abs(merge_gap_for(sample_lap) - MERGE_GAP_M) < 1.0
    # tight circuit clamps low, long circuit clamps high
    short = _variant(sample_lap)
    short.track['Tracklen'] = '1500'
    assert merge_gap_for(short) == MERGE_GAP_MIN
    long = _variant(sample_lap)
    long.track['Tracklen'] = '9000'
    assert merge_gap_for(long) == MERGE_GAP_MAX


def test_dedup_keeps_laps_without_number():
    # export missing the 'Lap' field must NOT collapse the field to one lap
    laps = [
        Lap(session={'laptime': str(80 + i)}, track={'Tyre': 'C3'}, setup={}, ch={}, n=0)
        for i in range(5)
    ]
    result = rr._dedup_laps(laps)
    assert len(result) == 5


def test_is_fresh_cache(tmp_path):
    src = tmp_path / "src.csv"
    rep = tmp_path / "rep.md"
    src.write_text("x")
    rep.write_text("y")
    os.utime(rep, (src.stat().st_atime + 10, src.stat().st_mtime + 10))
    assert is_fresh(str(rep), [str(src)]) is True
    os.utime(src, (rep.stat().st_atime + 20, rep.stat().st_mtime + 20))
    assert is_fresh(str(rep), [str(src)]) is False


class TestACC:
    """ACC support: game detection, prompt fallback, game-aware report sections."""

    def test_game_of_acc_vs_f1(self, acc_lap, sample_lap):
        assert game_of(acc_lap) == 'acc'
        assert game_of(sample_lap) == 'f1'

    def test_load_prompt_acc_falls_back_to_f1(self):
        # ACC requests resolve to the ACC prompt if present, else the F1 prompt —
        # never empty while an F1 prompt exists.
        base = os.path.normpath(os.path.join(
            os.path.dirname(report_common.__file__), '..', 'prompts', 'ru'))
        for mode in ('technique', 'setup', 'compare', 'race'):
            acc_file = os.path.join(base, 'acc', f'{mode}.md')
            f1_file = os.path.join(base, f'{mode}.md')
            expected = open(acc_file if os.path.exists(acc_file) else f1_file,
                            encoding='utf-8').read().strip()
            assert load_prompt(mode, 'ru', 'acc') == expected
            assert load_prompt(mode, 'ru', 'f1') == open(f1_file, encoding='utf-8').read().strip()

    def test_acc_setup_no_param_table_keeps_balance(self, acc_lap, tmp_path):
        out = str(tmp_path / "acc_setup.md")
        rs.generate(acc_lap, out, 'ru', include_prompt=False)
        text = open(out, encoding="utf-8").read()
        assert "| Parameter | Value |" not in text   # zero-filled setup table dropped
        assert "не экспортирует сетап" in text        # explanatory note instead
        assert "## Corner balance" in text            # telemetry-derived sections kept
        assert "## Tyres" in text

    def test_acc_technique_no_setup_line_no_ers(self, acc_lap, tmp_path):
        out = str(tmp_path / "acc_tech.md")
        rt.generate(acc_lap, out, 'ru', include_prompt=False)
        text = open(out, encoding="utf-8").read()
        assert "## Corners" in text
        assert "**Setup:**" not in text   # zero-filled setup summary skipped
        assert "ERS spent:" not in text   # hybrid block dropped

    def test_f1_technique_keeps_setup_and_ers(self, sample_lap, tmp_path):
        # regression: F1 path unchanged
        out = str(tmp_path / "f1_tech.md")
        rt.generate(sample_lap, out, 'ru', include_prompt=False)
        text = open(out, encoding="utf-8").read()
        assert "**Setup:**" in text
        assert "ERS spent:" in text

    def test_acc_race_skips_ers_table(self, acc_lap, tmp_path):
        out = str(tmp_path / "acc_race.md")
        rr.generate([acc_lap], out, 'ru', include_prompt=False)
        text = open(out, encoding="utf-8").read()
        assert "## ERS per lap" not in text
        assert "## Lap times" in text


class TestRegressionReports:
    """Regression: report generators must not crash on valid single-lap input."""

    def test_technique_no_exception(self, sample_lap, tmp_path):
        rt.generate(sample_lap, str(tmp_path / "r_tech.md"))

    def test_setup_no_exception(self, sample_lap, tmp_path):
        rs.generate(sample_lap, str(tmp_path / "r_setup.md"))

    def test_compare_no_exception(self, sample_lap, tmp_path):
        rc.generate([sample_lap], str(tmp_path / "r_cmp.md"))

    def test_race_no_exception(self, sample_lap, tmp_path):
        rr.generate([sample_lap], str(tmp_path / "r_race.md"))
