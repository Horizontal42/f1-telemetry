from dataclasses import dataclass

from .parser import Lap

STEER_ON = 6.0
BRAKE_ON = 5.0
MERGE_GAP_M = 40.0          # anchored at Zandvoort (~4257 m): tracks scale around this
MERGE_GAP_REF_LEN = 4257.0
MERGE_GAP_MIN = 28.0
MERGE_GAP_MAX = 60.0
MIN_LEN_M = 15.0
BRAKE_MARK = 20.0
FULL_THROTTLE = 98.0
LOCKUP_REL_PCT = -10.0
SPIN_REL_PCT = 8.0


def merge_gap_for(lap: Lap) -> float:
    """Corner-merge / cluster gap scaled to track length so chicanes and long
    circuits self-tune instead of relying on a fixed metre value. Equals
    MERGE_GAP_M at the reference length; clamped at the extremes."""
    raw = lap.track.get('Tracklen', '')
    try:
        tracklen = float(raw)
    except (TypeError, ValueError):
        dist = lap.ch.get('LapDistance', [])
        tracklen = (dist[-1] - dist[0]) if len(dist) >= 2 else 0.0
    if tracklen <= 0:
        return MERGE_GAP_M
    g = MERGE_GAP_M * tracklen / MERGE_GAP_REF_LEN
    return min(max(g, MERGE_GAP_MIN), MERGE_GAP_MAX)


@dataclass(frozen=True)
class Corner:
    number: int
    start_m: float
    end_m: float
    brake_start_m: float | None
    v_entry: float
    v_min: float
    apex_m: float
    gear_apex: int
    full_throttle_m: float | None
    v_exit: float
    brake_max: float
    g_lat_max: float
    time_s: float
    lock_pct: float
    spin_pct: float
    coast_m: float
    rear_tyre_temp_peak: float
    lockup: bool
    wheelspin: bool


@dataclass(frozen=True)
class Straight:
    start_m: float
    end_m: float
    v_max: float
    drs: bool
    time_s: float


def _get(lap: Lap, ch: str) -> list[float]:
    return lap.ch.get(ch, [])


def _indices_in_range(dist: list[float], start: float, end: float) -> list[int]:
    return [i for i, d in enumerate(dist) if start <= d <= end]


def detect_corners(lap: Lap) -> list[Corner]:
    from .corner_metrics import corner_from_zone

    dist = _get(lap, 'LapDistance')
    steer = _get(lap, 'Steer')
    brake = _get(lap, 'BrakePercentage')
    speed = _get(lap, 'Speed')
    gear = _get(lap, 'Gear')
    throttle = _get(lap, 'ThrottlePercentage')
    glat = _get(lap, 'GForceLatitudinal')
    laptime = _get(lap, 'LapTime')
    slip_rl = _get(lap, 'WheelSlipRearLeft')
    slip_rr = _get(lap, 'WheelSlipRearRight')
    slip_fl = _get(lap, 'WheelSlipFrontLeft')
    slip_fr = _get(lap, 'WheelSlipFrontRight')
    tyre_temp_rl = _get(lap, 'TyreTemperatureRearLeft')
    tyre_temp_rr = _get(lap, 'TyreTemperatureRearRight')

    n = len(dist)
    if n < 2:
        return []

    cornering = [
        (abs(steer[i]) > STEER_ON if i < len(steer) else False) or
        (brake[i] > BRAKE_ON if i < len(brake) else False)
        for i in range(n)
    ]

    zones: list[tuple[int, int]] = []
    in_zone = False
    z_start = 0
    for i, c in enumerate(cornering):
        if c and not in_zone:
            in_zone = True
            z_start = i
        elif not c and in_zone:
            in_zone = False
            zones.append((z_start, i - 1))
    if in_zone:
        zones.append((z_start, n - 1))

    merge_gap = merge_gap_for(lap)
    merged: list[tuple[int, int]] = []
    for z in zones:
        if merged and (dist[z[0]] - dist[merged[-1][1]]) < merge_gap:
            merged[-1] = (merged[-1][0], z[1])
        else:
            merged.append(list(z))

    valid = [(a, b) for a, b in merged if (dist[b] - dist[a]) >= MIN_LEN_M]

    return [
        corner_from_zone(
            lap, ia, ib, num,
            dist, speed, brake, throttle, gear, glat, laptime,
            slip_fl, slip_fr, slip_rl, slip_rr,
            tyre_temp_rl, tyre_temp_rr,
        )
        for num, (ia, ib) in enumerate(valid, 1)
    ]


def straights(corners: list[Corner], lap: Lap) -> list[Straight]:
    dist = _get(lap, 'LapDistance')
    speed = _get(lap, 'Speed')
    drs_ch = _get(lap, 'DRS')
    laptime = _get(lap, 'LapTime')

    if not dist:
        return []

    track_start = dist[0]
    track_end = dist[-1]

    gaps: list[tuple[float, float]] = []
    if not corners:
        gaps = [(track_start, track_end)]
    else:
        if corners[0].start_m > track_start + MIN_LEN_M:
            gaps.append((track_start, corners[0].start_m))
        for i in range(len(corners) - 1):
            gaps.append((corners[i].end_m, corners[i + 1].start_m))
        if corners[-1].end_m < track_end - MIN_LEN_M:
            gaps.append((corners[-1].end_m, track_end))

    result: list[Straight] = []
    for start, end in gaps:
        idxs = _indices_in_range(dist, start, end)
        if not idxs:
            continue
        spds = [speed[i] for i in idxs if i < len(speed)]
        v_max = max(spds) if spds else 0.0
        drs_used = any(drs_ch[i] == 1.0 for i in idxs if i < len(drs_ch))
        time_zone = 0.0
        if laptime and idxs:
            time_zone = laptime[idxs[-1]] - laptime[idxs[0]]
        result.append(Straight(start_m=start, end_m=end, v_max=v_max, drs=drs_used, time_s=time_zone))

    return result
