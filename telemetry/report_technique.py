from .parser import Lap, laptime_s
from .segments import detect_corners, straights, Corner, Straight
from .resample import adaptive_points, sample_at, format_trace_row
from .report_common import (
    header_block, setup_summary, legend, md_table, write_report, report_path,
    load_prompt, game_of,
    LEGEND_DIST, LEGEND_TIME, LEGEND_SPD, LEGEND_THR_BRK, LEGEND_STEER,
    LEGEND_GEAR, LEGEND_DRS, LEGEND_GLAT, LEGEND_GLON, LEGEND_FUEL, LEGEND_ERS,
    LEGEND_LOCK, LEGEND_SPIN, LEGEND_TF, LEGEND_RPM, LEGEND_SLIP, LEGEND_YAW,
)


def _corner_rows(corners: list[Corner]) -> list[list[str]]:
    rows = []
    for c in corners:
        flag_str = '—'
        flags = []
        if c.lockup:
            flags.append('LOCK')
        if c.wheelspin:
            flags.append('SPIN')
        if flags:
            flag_str = '/'.join(flags)
        brake_m = f'{c.brake_start_m:.0f}' if c.brake_start_m is not None else '—'
        ft_m = f'{c.full_throttle_m:.0f}' if c.full_throttle_m is not None else '—'
        rows.append([
            str(c.number),
            brake_m,
            f'{c.v_entry:.0f}',
            f'{c.v_min:.0f}',
            f'{c.apex_m:.0f}',
            str(c.gear_apex),
            ft_m,
            f'{c.v_exit:.0f}',
            f'{c.brake_max:.0f}',
            f'{c.g_lat_max:.2f}',
            f'{c.time_s:.2f}',
            f'{c.lock_pct:.1f}',
            f'{c.spin_pct:.1f}',
            str(int(c.coast_m)),
            str(int(c.rear_tyre_temp_peak)),
            flag_str,
        ])
    return rows


def _straight_rows(ss: list[Straight]) -> list[list[str]]:
    rows = []
    for s in ss:
        rows.append([
            f'{s.start_m:.0f}→{s.end_m:.0f}',
            f'{s.v_max:.0f}',
            'Y' if s.drs else 'N',
            f'{s.time_s:.2f}',
        ])
    return rows


def _driving_cost(lap: Lap, corners: list[Corner], game: str = 'f1') -> str:
    ch = lap.ch
    fuel = ch.get('FuelRemaining', [])
    fuel_used = (fuel[0] - fuel[-1]) if len(fuel) >= 2 else 0.0

    wear_keys = ['TyreWearFrontLeft', 'TyreWearFrontRight', 'TyreWearRearLeft', 'TyreWearRearRight']
    wear_lines = []
    for k in wear_keys:
        v = ch.get(k, [])
        if len(v) >= 2:
            wear_lines.append(f'  {k.replace("TyreWear","")}: Δ{v[-1]-v[0]:.2f}%')

    ers_spent = ch.get('ERSSpent', [])
    mguk_h = ch.get('MGUKHarvested', [])
    mguh_h = ch.get('MGUHHarvested', [])
    ers_mj = (ers_spent[-1] / 1e6) if ers_spent else 0.0
    mguk_mj = (mguk_h[-1] / 1e6) if mguk_h else 0.0
    mguh_mj = (mguh_h[-1] / 1e6) if mguh_h else 0.0

    lock_count = sum(1 for c in corners if c.lockup)
    spin_count = sum(1 for c in corners if c.wheelspin)
    worst_lock = min(corners, key=lambda c: c.lock_pct, default=None)
    worst_spin = max(corners, key=lambda c: c.spin_pct, default=None)
    worst_lock_str = f'T{worst_lock.number} ({worst_lock.lock_pct:.1f}%)' if worst_lock else '—'
    worst_spin_str = f'T{worst_spin.number} ({worst_spin.spin_pct:.1f}%)' if worst_spin else '—'

    bt_keys = ['BrakeTemperatureFrontLeft', 'BrakeTemperatureFrontRight',
               'BrakeTemperatureRearLeft', 'BrakeTemperatureRearRight']
    bt_lines = []
    for k in bt_keys:
        v = ch.get(k, [])
        if v:
            bt_lines.append(f'  {k.replace("BrakeTemperature","")}: max {max(v):.0f} °C')

    lines = [
        f'- Fuel used: {fuel_used:.2f} kg',
        '- Tyre wear Δ:',
        *wear_lines,
    ]
    if game != 'acc':
        lines.append(
            f'- ERS spent: {ers_mj:.3f} MJ | MGU-K harvested: {mguk_mj:.3f} MJ | MGU-H harvested: {mguh_mj:.3f} MJ'
        )
    lines += [
        f'- Corners flagged LOCK: {lock_count} | SPIN: {spin_count}',
        f'- Worst lock%: {worst_lock_str} | Worst spin%: {worst_spin_str}',
        '- Max brake temps:',
        *bt_lines,
    ]
    return '\n'.join(lines)


def _trace_block(lap: Lap, corners: list[Corner]) -> str:
    dists = adaptive_points(lap, corners)
    if not dists:
        return ''

    def s(channel: str) -> list[float]:
        return sample_at(lap, channel, dists)

    lt = s('LapTime')
    spd = s('Speed')
    thr = s('ThrottlePercentage')
    brk = s('BrakePercentage')
    steer = s('Steer')
    gear = s('Gear')
    drs = s('DRS')
    glat = s('GForceLatitudinal')
    glon = s('GForceLongitudinal')
    fuel = s('FuelRemaining')
    ers_raw = s('ERSSpent')
    ers = [v / 1e6 for v in ers_raw]
    tf_fl = s('TyreTemperatureFrontLeft')
    tf_fr = s('TyreTemperatureFrontRight')
    tr_rl = s('TyreTemperatureRearLeft')
    tr_rr = s('TyreTemperatureRearRight')
    rpm_raw = s('EngineRevs')
    tf = [(tf_fl[i] + tf_fr[i]) / 2 for i in range(len(dists))]
    tr = [(tr_rl[i] + tr_rr[i]) / 2 for i in range(len(dists))]
    rpm = [round(rpm_raw[i] / 100) * 100 for i in range(len(dists))]

    slip_fl = s('WheelSlipFrontLeft')
    slip_fr = s('WheelSlipFrontRight')
    slip_rl = s('WheelSlipRearLeft')
    slip_rr = s('WheelSlipRearRight')
    yaw_vals = s('LocalAngularVelocityY')
    slip_f = [min(slip_fl[i], slip_fr[i]) / max(spd[i], 30.0) * 100.0 for i in range(len(dists))]
    slip_r = [max(slip_rl[i], slip_rr[i]) / max(spd[i], 30.0) * 100.0 for i in range(len(dists))]

    header = 'dist,time,spd,thr,brk,steer,gear,drs,gLat,gLon,fuel,ers,Tf,Tr,rpm,slipF,slipR,yaw'
    rows = [
        format_trace_row(dists[i], lt[i], spd[i], thr[i], brk[i],
                         steer[i], gear[i], drs[i], glat[i], glon[i], fuel[i], ers[i],
                         tf[i], tr[i], rpm[i], slip_f[i], slip_r[i], yaw_vals[i])
        for i in range(len(dists))
    ]
    return '```\n' + header + '\n' + '\n'.join(rows) + '\n```'


def generate(lap: Lap, out_path: str, lang: str = 'ru', include_prompt: bool = True,
             game: str | None = None) -> tuple[str, int]:
    g = game or game_of(lap)
    corners = detect_corners(lap)
    ss = straights(corners, lap)

    corner_table = md_table(
        ['T', 'brake@m', 'Ventry', 'Vmin', 'apex@m', 'gear', 'fullThr@m', 'Vexit', 'maxBrake%', 'gLat', 'time s', 'lock%', 'spin%', 'coast m', 'Tr peak °C', 'flags'],
        _corner_rows(corners),
    )
    straight_table = md_table(
        ['from→to m', 'Vmax', 'DRS', 'time s'],
        _straight_rows(ss),
    )

    parts = [header_block(lap)]
    if g != 'acc':
        parts.append(f'\n**Setup:** {setup_summary(lap)}')
    parts += [
        '\n## Corners',
        corner_table,
        '\n## Straights',
        straight_table,
        '\n## Driving cost (per lap)',
        _driving_cost(lap, corners, g),
        '\n## Trace',
        _trace_block(lap, corners),
        '\n' + legend([
            LEGEND_DIST, LEGEND_TIME, LEGEND_SPD, LEGEND_THR_BRK, LEGEND_STEER,
            LEGEND_GEAR, LEGEND_DRS, LEGEND_GLAT, LEGEND_GLON, LEGEND_FUEL, LEGEND_ERS,
            LEGEND_TF, LEGEND_RPM, LEGEND_SLIP, LEGEND_YAW, LEGEND_LOCK, LEGEND_SPIN,
        ]),
    ]
    text = '\n'.join(parts)
    if include_prompt:
        prompt = load_prompt('technique', lang, g)
        if prompt:
            text += '\n\n---\n\n' + prompt
    return write_report(out_path, text)
