import pytest
from telemetry.parser import load_lap, laptime_s, sector_times


def test_sample_metadata(sample_lap):
    assert sample_lap.session["track"] == "Zandvoort"
    assert sample_lap.session["car"] == "Ferrari"
    assert sample_lap.track["Lap"] == "7"
    assert sample_lap.track["Tyre"] == "C2"
    assert sample_lap.n > 1000


def test_all_zero_channels_dropped(sample_lap):
    assert "Torque" not in sample_lap.ch
    assert "IcePower" not in sample_lap.ch


def test_live_channel_present(sample_lap):
    assert "Speed" in sample_lap.ch


def test_setup_trailing_comma_handled(sample_lap):
    assert "FuelLoad" in sample_lap.setup
    assert "" not in sample_lap.setup


def test_utf8_loads_cleanly(sample_path):
    # implicit — load_lap opens with encoding='utf-8'; raises on decode error
    lap = load_lap(sample_path)
    assert lap.n > 0


def test_truncated_file_loads(truncated_path):
    lap = load_lap(truncated_path)
    assert 1 <= lap.n <= 20


def test_laptime_s(sample_lap):
    lt = laptime_s(sample_lap)
    assert 70.0 < lt < 80.0


def test_sector_times_sum_to_laptime(sample_lap):
    lt = laptime_s(sample_lap)
    s1, s2, s3 = sector_times(sample_lap)
    assert abs((s1 + s2 + s3) - lt) < 0.1
