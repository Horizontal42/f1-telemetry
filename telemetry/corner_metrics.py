from .parser import Lap
from .segments import (
    Corner,
    BRAKE_MARK, FULL_THROTTLE, LOCKUP_REL_PCT, SPIN_REL_PCT,
)

_SAFE_SPEED_FLOOR = 30.0


def _safe(lst: list[float], i: int, default: float = 0.0) -> float:
    return lst[i] if i < len(lst) else default


def corner_from_zone(
    lap: Lap,
    ia: int,
    ib: int,
    number: int,
    dist: list[float],
    speed: list[float],
    brake: list[float],
    throttle: list[float],
    gear: list[float],
    glat: list[float],
    laptime: list[float],
    slip_fl: list[float],
    slip_fr: list[float],
    slip_rl: list[float],
    slip_rr: list[float],
    tyre_temp_rl: list[float],
    tyre_temp_rr: list[float],
) -> Corner:
    idxs = list(range(ia, ib + 1))

    spds = [_safe(speed, i) for i in idxs]
    v_entry = spds[0] if spds else 0.0
    v_exit = spds[-1] if spds else 0.0
    v_min = min(spds) if spds else 0.0
    apex_i = idxs[spds.index(v_min)]
    apex_m = dist[apex_i]
    gear_apex = int(_safe(gear, apex_i))

    brake_start_m: float | None = None
    for i in idxs:
        if _safe(brake, i) > BRAKE_MARK:
            brake_start_m = dist[i]
            break

    brake_vals = [_safe(brake, i) for i in idxs]
    brake_max = max(brake_vals) if brake_vals else 0.0

    glat_vals = [abs(_safe(glat, i)) for i in idxs]
    g_lat_max = max(glat_vals) if glat_vals else 0.0

    full_throttle_m: float | None = None
    apex_idx_in_idxs = spds.index(v_min)
    post_apex = idxs[apex_idx_in_idxs:]
    if laptime:
        i = 0
        while i < len(post_apex):
            pi = post_apex[i]
            if _safe(throttle, pi) >= FULL_THROTTLE:
                t_start = _safe(laptime, pi)
                j = i
                while j < len(post_apex) and _safe(throttle, post_apex[j]) >= FULL_THROTTLE:
                    j += 1
                t_end = _safe(laptime, post_apex[j - 1])
                if (t_end - t_start) >= 0.3:
                    full_throttle_m = dist[pi]
                    break
                i = j
            else:
                i += 1
    else:
        for pi in post_apex:
            if _safe(throttle, pi) >= FULL_THROTTLE:
                full_throttle_m = dist[pi]
                break

    time_zone = 0.0
    if laptime and idxs:
        time_zone = _safe(laptime, ib) - _safe(laptime, ia)

    # lock_pct: min relative front slip under braking (negative = locking tendency)
    brake_slip_vals = []
    for i in idxs:
        if _safe(brake, i) > 20:
            front = min(_safe(slip_fl, i), _safe(slip_fr, i))
            spd = max(_safe(speed, i), _SAFE_SPEED_FLOOR)
            brake_slip_vals.append(front / spd * 100.0)
    lock_pct = min(brake_slip_vals) if brake_slip_vals else 0.0

    # spin_pct: max relative rear slip on throttle (positive = spinning tendency)
    throttle_slip_vals = []
    for i in idxs:
        if _safe(throttle, i) > 80:
            rear = max(_safe(slip_rl, i), _safe(slip_rr, i))
            spd = max(_safe(speed, i), _SAFE_SPEED_FLOOR)
            throttle_slip_vals.append(rear / spd * 100.0)
    spin_pct = max(throttle_slip_vals) if throttle_slip_vals else 0.0

    lockup = lock_pct < LOCKUP_REL_PCT
    wheelspin = spin_pct > SPIN_REL_PCT

    brake_off_m: float | None = None
    if brake_start_m is not None:
        brake_start_idx = next((i for i in idxs if dist[i] >= brake_start_m), None)
        if brake_start_idx is not None:
            for i in idxs[idxs.index(brake_start_idx):idxs.index(apex_i) + 1]:
                if _safe(brake, i) > BRAKE_MARK:
                    brake_off_m = dist[i]

    coast_m = 0.0
    if brake_off_m is not None and full_throttle_m is not None and full_throttle_m > brake_off_m:
        coast_m = full_throttle_m - brake_off_m

    rear_tyre_temp_peak = 0.0
    if tyre_temp_rl and tyre_temp_rr:
        peaks = [max(_safe(tyre_temp_rl, i), _safe(tyre_temp_rr, i)) for i in idxs]
        rear_tyre_temp_peak = max(peaks) if peaks else 0.0

    return Corner(
        number=number,
        start_m=dist[ia],
        end_m=dist[ib],
        brake_start_m=brake_start_m,
        v_entry=v_entry,
        v_min=v_min,
        apex_m=apex_m,
        gear_apex=gear_apex,
        full_throttle_m=full_throttle_m,
        v_exit=v_exit,
        brake_max=brake_max,
        g_lat_max=g_lat_max,
        time_s=time_zone,
        lock_pct=lock_pct,
        spin_pct=spin_pct,
        coast_m=coast_m,
        rear_tyre_temp_peak=rear_tyre_temp_peak,
        lockup=lockup,
        wheelspin=wheelspin,
    )
