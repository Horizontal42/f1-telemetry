import pytest
from telemetry.resample import auto_steps, adaptive_points, sample_at
from telemetry.segments import detect_corners


def test_auto_steps_ranges(sample_lap):
    dense, sparse = auto_steps(sample_lap)
    assert 1.0 <= dense <= 5.0
    assert sparse >= 20.0
    assert dense < sparse


def test_adaptive_points_monotone(sample_lap):
    corners = detect_corners(sample_lap)
    pts = adaptive_points(sample_lap, corners)
    assert all(pts[i] < pts[i + 1] for i in range(len(pts) - 1))


def test_adaptive_points_bounds(sample_lap):
    corners = detect_corners(sample_lap)
    dist = sample_lap.ch["LapDistance"]
    pts = adaptive_points(sample_lap, corners)
    assert pts[0] == dist[0]
    assert pts[-1] == dist[-1]
    assert all(dist[0] <= p <= dist[-1] for p in pts)


def test_sample_at_length(sample_lap):
    corners = detect_corners(sample_lap)
    dists = adaptive_points(sample_lap, corners)
    vals = sample_at(sample_lap, "Speed", dists)
    assert len(vals) == len(dists)


def test_sample_at_endpoint_clamping(sample_lap):
    dist = sample_lap.ch["LapDistance"]
    speed = sample_lap.ch["Speed"]
    # query exactly at and beyond the recorded endpoints
    before = dist[0] - 10.0
    after = dist[-1] + 10.0
    vals = sample_at(sample_lap, "Speed", [before, dist[0], dist[-1], after])
    assert vals[0] == speed[0]
    assert vals[1] == speed[0]
    assert vals[2] == speed[-1]
    assert vals[3] == speed[-1]


def test_sample_at_missing_channel_returns_zeros(sample_lap):
    dist = sample_lap.ch["LapDistance"]
    dists = [dist[0], dist[-1]]
    vals = sample_at(sample_lap, "NonExistentChannel", dists)
    assert vals == [0.0, 0.0]
