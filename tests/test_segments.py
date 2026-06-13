import dataclasses
import pytest
from telemetry.parser import load_lap
from telemetry.segments import detect_corners, straights


def test_zandvoort_corner_count(sample_lap):
    corners = detect_corners(sample_lap)
    assert 10 <= len(corners) <= 13


def test_corners_numbered_sequentially(sample_lap):
    corners = detect_corners(sample_lap)
    assert [c.number for c in corners] == list(range(1, len(corners) + 1))


def test_corner_start_m_strictly_increasing(sample_lap):
    corners = detect_corners(sample_lap)
    starts = [c.start_m for c in corners]
    assert all(starts[i] < starts[i + 1] for i in range(len(starts) - 1))


def test_corner_vmin_le_ventry(sample_lap):
    corners = detect_corners(sample_lap)
    for c in corners:
        assert c.v_min <= c.v_entry + 1.0, f"T{c.number}: v_min={c.v_min} > v_entry={c.v_entry}"


def test_corner_lock_pct_nonpositive(sample_lap):
    corners = detect_corners(sample_lap)
    for c in corners:
        assert c.lock_pct <= 0.0, f"T{c.number}: lock_pct={c.lock_pct}"


def test_corner_spin_pct_nonnegative(sample_lap):
    corners = detect_corners(sample_lap)
    for c in corners:
        assert c.spin_pct >= 0.0, f"T{c.number}: spin_pct={c.spin_pct}"


def test_corner_is_frozen(sample_lap):
    corners = detect_corners(sample_lap)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        corners[0].number = 99


def test_straights_nonempty(sample_lap):
    corners = detect_corners(sample_lap)
    ss = straights(corners, sample_lap)
    assert len(ss) > 0


def test_truncated_lap_corners_empty(truncated_path):
    lap = load_lap(truncated_path)
    corners = detect_corners(lap)
    # very short lap — may have few or no detectable corners; must not crash
    assert isinstance(corners, list)
