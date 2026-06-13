import bisect
import statistics

from .parser import Lap
from .segments import Corner

_DISCRETE = {'Gear', 'DRS', 'ERSMode'}


def auto_steps(lap: Lap) -> tuple[float, float]:
    dist = lap.ch.get('LapDistance', [])
    diffs = [dist[i + 1] - dist[i] for i in range(len(dist) - 1) if dist[i + 1] - dist[i] > 0]
    if not diffs:
        return (4.0, 25.0)
    med = statistics.median(diffs)
    dense = max(round(med, 1), 1.0)
    sparse = max(round(med * 8, 0), 20.0)
    return (dense, sparse)


def adaptive_points(
    lap: Lap,
    corners: list[Corner],
    dense_step: float | None = None,
    sparse_step: float | None = None,
    approach_m: float = 100.0,
) -> list[float]:
    if dense_step is None or sparse_step is None:
        auto_d, auto_s = auto_steps(lap)
        if dense_step is None:
            dense_step = auto_d
        if sparse_step is None:
            sparse_step = auto_s

    dist = lap.ch.get('LapDistance', [])
    if not dist:
        return []

    d_min = dist[0]
    d_max = dist[-1]

    # build dense/sparse bands
    dense_ranges: list[tuple[float, float]] = []
    for c in corners:
        band_start = max(d_min, c.start_m - approach_m)
        dense_ranges.append((band_start, c.end_m))

    def in_dense(d: float) -> bool:
        for a, b in dense_ranges:
            if a <= d <= b:
                return True
        return False

    points: list[float] = [d_min]
    d = d_min
    while d < d_max:
        step = dense_step if in_dense(d) else sparse_step
        d = min(d + step, d_max)
        points.append(d)

    if points[-1] != d_max:
        points.append(d_max)

    return sorted(set(points))


def _interp(xs: list[float], ys: list[float], x: float) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_left(xs, x)
    x0, x1 = xs[i - 1], xs[i]
    y0, y1 = ys[i - 1], ys[i]
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _nearest(xs: list[float], ys: list[float], x: float) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_left(xs, x)
    if i == 0:
        return ys[0]
    if abs(xs[i] - x) < abs(xs[i - 1] - x):
        return ys[i]
    return ys[i - 1]


def sample_at(lap: Lap, channel: str, dists: list[float]) -> list[float]:
    src_dist = lap.ch.get('LapDistance', [])
    src_vals = lap.ch.get(channel, [])
    if not src_dist or not src_vals:
        return [0.0] * len(dists)

    discrete = channel in _DISCRETE
    fn = _nearest if discrete else _interp
    return [fn(src_dist, src_vals, d) for d in dists]


def _round_channel(ch: str, v: float) -> str:
    if ch in ('LapTime', 'LapDistance'):
        return f'{v:.0f}' if ch == 'LapDistance' else f'{v:.2f}'
    if ch in ('FuelRemaining',):
        return f'{v:.2f}'
    if ch in ('Steer', 'ThrottlePercentage', 'BrakePercentage'):
        return f'{v:.0f}'
    if ch in ('Speed', 'GForceLatitudinal', 'GForceLongitudinal'):
        return f'{v:.0f}'
    if ch in ('Gear', 'DRS', 'ERSMode'):
        return f'{int(v)}'
    return f'{v:.1f}'


def format_trace_row(
    dist: float,
    laptime: float,
    speed: float,
    throttle: float,
    brake: float,
    steer: float,
    gear: float,
    drs: float,
    g_lat: float,
    g_lon: float,
    fuel: float,
    ers: float = 0.0,
    tf: float = 0.0,
    tr: float = 0.0,
    rpm: float = 0.0,
    slip_f: float = 0.0,
    slip_r: float = 0.0,
    yaw: float = 0.0,
) -> str:
    steer_norm = 0.0 if steer == 0.0 or steer == -0.0 else steer
    return (
        f'{dist:.0f},{laptime:.2f},{speed:.0f},{throttle:.0f},'
        f'{brake:.0f},{steer_norm:.0f},{int(gear)},{int(drs)},'
        f'{g_lat:.1f},{g_lon:.1f},{fuel:.2f},{ers:.3f},'
        f'{tf:.0f},{tr:.0f},{rpm:.0f},'
        f'{slip_f:.1f},{slip_r:.1f},{yaw:.2f}'
    )
