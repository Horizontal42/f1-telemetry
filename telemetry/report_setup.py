from .parser import Lap
from .segments import detect_corners, Corner
from .segments import _indices_in_range
from .report_common import (
    header_block, legend, md_table, write_report, load_prompt,
    LEGEND_DIST, LEGEND_TIME, LEGEND_SPD, LEGEND_THR_BRK, LEGEND_STEER,
    LEGEND_GEAR, LEGEND_DRS, LEGEND_GLAT, LEGEND_GLON, LEGEND_FUEL,
    LEGEND_LOCK, LEGEND_SPIN, LEGEND_STEER_G_CAVEAT, LEGEND_SUSP,
)


def _safe_avg(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _safe_min(vals: list[float]) -> float:
    return min(vals) if vals else 0.0


def _safe_max(vals: list[float]) -> float:
    return max(vals) if vals else 0.0


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _corner_balance(lap: Lap, corners: list[Corner]) -> str:
    dist = lap.ch.get('LapDistance', [])
    glat = lap.ch.get('GForceLatitudinal', [])
    steer = lap.ch.get('Steer', [])
    slip_fl = lap.ch.get('WheelSlipFrontLeft', [])
    slip_fr = lap.ch.get('WheelSlipFrontRight', [])
    slip_rl = lap.ch.get('WheelSlipRearLeft', [])
    slip_rr = lap.ch.get('WheelSlipRearRight', [])

    # lap-wide axle baselines
    all_front = [abs(v) for v in slip_fl] + [abs(v) for v in slip_fr]
    all_rear = [abs(v) for v in slip_rl] + [abs(v) for v in slip_rr]
    front_baseline = _median(all_front)
    rear_baseline = _median(all_rear)

    rows = []
    for c in corners:
        idxs = _indices_in_range(dist, c.start_m, c.end_m)
        if not idxs:
            continue

        glat_vals = [abs(glat[i]) for i in idxs if i < len(glat)]
        steer_vals = [abs(steer[i]) for i in idxs if i < len(steer)]
        glat_avg = _safe_avg(glat_vals)
        steer_per_g = (_safe_avg(steer_vals) / glat_avg) if glat_avg > 0 else 0.0

        front_slip = [abs(slip_fl[i]) for i in idxs if i < len(slip_fl)] + \
                     [abs(slip_fr[i]) for i in idxs if i < len(slip_fr)]
        rear_slip = [abs(slip_rl[i]) for i in idxs if i < len(slip_rl)] + \
                    [abs(slip_rr[i]) for i in idxs if i < len(slip_rr)]
        front_avg = _safe_avg(front_slip)
        rear_avg = _safe_avg(rear_slip)

        front_excess = front_avg - front_baseline
        rear_excess = rear_avg - rear_baseline
        diff = front_excess - rear_excess
        if diff > 0.5:
            balance = 'US'
        elif diff < -0.5:
            balance = 'OS'
        else:
            balance = '—'

        rows.append([
            str(c.number),
            f'{c.v_min:.0f}',
            f'{c.g_lat_max:.2f}',
            f'{steer_per_g:.2f}',
            f'{front_avg:.3f}',
            f'{rear_avg:.3f}',
            balance,
        ])

    return md_table(
        ['T', 'Vmin', 'gLat_max', 'steer/g', 'front|slip|', 'rear|slip|', 'balance'],
        rows,
    )


def _tyre_section(lap: Lap) -> str:
    ch = lap.ch
    setup = lap.setup
    wheels = ['FrontLeft', 'FrontRight', 'RearLeft', 'RearRight']
    rows = []
    for w in wheels:
        wear = ch.get(f'TyreWear{w}', [])
        wear_d = f'{wear[-1]-wear[0]:.2f}' if len(wear) >= 2 else '—'

        surf = ch.get(f'TyreTemperature{w}', [])
        if surf:
            surf_min = f'{_safe_min(surf):.0f}'
            surf_avg = f'{_safe_avg(surf):.0f}'
            surf_max = f'{_safe_max(surf):.0f}'
        else:
            surf_min = surf_avg = surf_max = '—'

        carc = ch.get(f'TyreCarcassTemperature{w}', [])
        if carc:
            carc_min = f'{_safe_min(carc):.0f}'
            carc_avg = f'{_safe_avg(carc):.0f}'
            carc_max = f'{_safe_max(carc):.0f}'
        else:
            carc_min = carc_avg = carc_max = '—'

        press_ch = ch.get(f'TyrePressure{w}', [])
        if press_ch and any(v != 0.0 for v in press_ch):
            press = f'{_safe_avg(press_ch):.1f} PSI'
        else:
            key_map = {'FrontLeft': 'FLTyrePressure', 'FrontRight': 'FRTyrePressure',
                       'RearLeft': 'RLTyrePressure', 'RearRight': 'RRTyrePressure'}
            press = setup.get(key_map.get(w, ''), '—') + ' PSI'

        rows.append([w, wear_d, f'{surf_min}/{surf_avg}/{surf_max}',
                     f'{carc_min}/{carc_avg}/{carc_max}', press])

    return md_table(['Wheel', 'wearΔ%', 'surf min/avg/max °C', 'carc min/avg/max °C', 'pressure'], rows)


def _brake_section(lap: Lap) -> str:
    ch = lap.ch
    wheels = ['FrontLeft', 'FrontRight', 'RearLeft', 'RearRight']
    rows = []
    for w in wheels:
        bt = ch.get(f'BrakeTemperature{w}', [])
        if bt:
            rows.append([w, f'{_safe_min(bt):.0f}', f'{_safe_avg(bt):.0f}', f'{_safe_max(bt):.0f}'])
        else:
            rows.append([w, '—', '—', '—'])
    return md_table(['Wheel', 'min °C', 'avg °C', 'max °C'], rows)


def _lap_phases(lap: Lap) -> str:
    dist = lap.ch.get('LapDistance', [])
    if not dist:
        return ''
    d_min, d_max = dist[0], dist[-1]
    third = (d_max - d_min) / 3
    phases = [
        ('Phase 1', d_min, d_min + third),
        ('Phase 2', d_min + third, d_min + 2 * third),
        ('Phase 3', d_min + 2 * third, d_max),
    ]
    wheels = ['FrontLeft', 'FrontRight', 'RearLeft', 'RearRight']
    headers = ['Phase'] + wheels
    rows = []
    for label, start, end in phases:
        idxs = _indices_in_range(dist, start, end)
        row = [label]
        for w in wheels:
            surf = lap.ch.get(f'TyreTemperature{w}', [])
            vals = [surf[i] for i in idxs if i < len(surf)]
            row.append(f'{_safe_avg(vals):.0f}' if vals else '—')
        rows.append(row)
    return md_table(headers, rows)


def _full_setup_table(lap: Lap) -> str:
    rows = [[k, v] for k, v in lap.setup.items()]
    return md_table(['Parameter', 'Value'], rows)


def _suspension_section(lap: Lap, corners: list[Corner]) -> str | None:
    ch = lap.ch
    susp_keys = ['SuspensionPositionFrontLeft', 'SuspensionPositionFrontRight',
                 'SuspensionPositionRearLeft', 'SuspensionPositionRearRight']
    if not all(k in ch for k in susp_keys):
        return None

    fl = ch['SuspensionPositionFrontLeft']
    fr = ch['SuspensionPositionFrontRight']
    rl = ch['SuspensionPositionRearLeft']
    rr = ch['SuspensionPositionRearRight']

    front_avg_mm = _safe_avg([v * 1000 for v in fl] + [v * 1000 for v in fr])
    rear_avg_mm = _safe_avg([v * 1000 for v in rl] + [v * 1000 for v in rr])
    rake_mm = front_avg_mm - rear_avg_mm

    rake_line = (
        f'Rake: front avg {front_avg_mm:.1f} mm / rear avg {rear_avg_mm:.1f} mm'
        f' / Δ (rake) {rake_mm:.1f} mm'
    )

    dist = ch.get('LapDistance', [])
    glat = ch.get('GForceLatitudinal', [])

    rows = []
    for c in corners:
        idxs = _indices_in_range(dist, c.start_m, c.end_m)
        if not idxs:
            continue

        fl_z = [fl[i] * 1000 for i in idxs if i < len(fl)]
        fr_z = [fr[i] * 1000 for i in idxs if i < len(fr)]
        rl_z = [rl[i] * 1000 for i in idxs if i < len(rl)]
        rr_z = [rr[i] * 1000 for i in idxs if i < len(rr)]

        left_avg = _safe_avg(fl_z + rl_z)
        right_avg = _safe_avg(fr_z + rr_z)
        roll_mm = left_avg - right_avg

        glat_vals = [glat[i] for i in idxs if i < len(glat)]
        mean_glat = _safe_avg(glat_vals)
        glat_sign = '+' if mean_glat >= 0 else '-'

        rows.append([str(c.number), f'{c.v_min:.0f}', f'{roll_mm:.1f}', glat_sign])

    roll_table = md_table(['T', 'Vmin', 'roll mm', 'gLat sign'], rows)
    return rake_line + '\n\n' + roll_table


def generate(lap: Lap, out_path: str, lang: str = 'ru', include_prompt: bool = True) -> tuple[str, int]:
    corners = detect_corners(lap)
    susp = _suspension_section(lap, corners)

    parts = [
        header_block(lap),
        '\n## Setup',
        _full_setup_table(lap),
        '\n## Corner balance',
        _corner_balance(lap, corners),
        '\n## Tyres',
        _tyre_section(lap),
        '\n## Brakes',
        _brake_section(lap),
    ]

    if susp is not None:
        parts += ['\n## Suspension', susp]

    legend_entries = [LEGEND_GLAT, LEGEND_STEER, LEGEND_LOCK, LEGEND_SPIN, LEGEND_STEER_G_CAVEAT]
    if susp is not None:
        legend_entries.append(LEGEND_SUSP)

    parts += [
        '\n## Lap phases (avg surface temp °C)',
        _lap_phases(lap),
        '\n' + legend(legend_entries),
    ]
    text = '\n'.join(parts)
    if include_prompt:
        prompt = load_prompt('setup', lang)
        if prompt:
            text += '\n\n---\n\n' + prompt
    return write_report(out_path, text)
