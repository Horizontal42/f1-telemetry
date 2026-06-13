import os
import pytest
import telemetry.report_technique as rt
import telemetry.report_setup as rs
import telemetry.report_compare as rc
import telemetry.report_race as rr


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
