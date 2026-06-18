import bisect

from .parser import Lap, laptime_s, sector_times
from .segments import detect_corners, Corner
from .resample import adaptive_points, sample_at
from .report_common import (
    legend, md_table, write_report, token_estimate, load_prompt,
    LEGEND_DIST, LEGEND_SPD, LEGEND_DT_SEG, LEGEND_DT_CUM,
)

# seconds gained per kg of fuel burned — track-dependent in reality, so report a range
# (rule of thumb across F1 22 circuits) instead of one false-precise number.
FUEL_S_PER_KG_LOW = 0.03
FUEL_S_PER_KG_HIGH = 0.05


def _interp_laptime(lap: Lap, dist_query: float) -> float:
    dist = lap.ch.get('LapDistance', [])
    lt = lap.ch.get('LapTime', [])
    if not dist or not lt:
        return 0.0
    if dist_query <= dist[0]:
        return lt[0]
    if dist_query >= dist[-1]:
        return lt[-1]
    i = bisect.bisect_left(dist, dist_query)
    x0, x1 = dist[i - 1], dist[i]
    y0, y1 = lt[i - 1], lt[i]
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (dist_query - x0) / (x1 - x0)


def _header_table(laps: list[Lap]) -> str:
    headers = ['Metric'] + [f'Lap {i+1}' for i in range(len(laps))]
    def _fuel_start(l: Lap) -> str:
        raw = l.track.get('Fuel at Start', '?')
        try:
            return f'{float(raw):.2f}'
        except (ValueError, TypeError):
            return raw

    fields = [
        ('Laptime', lambda l: f'{laptime_s(l):.3f}'),
        ('S1', lambda l: f'{sector_times(l)[0]:.3f}'),
        ('S2', lambda l: f'{sector_times(l)[1]:.3f}'),
        ('S3', lambda l: f'{sector_times(l)[2]:.3f}'),
        ('Tyre', lambda l: l.track.get('Tyre', '?')),
        ('Fuel start kg', _fuel_start),
        ('Wear FL%', lambda l: _delta_wear(l, 'TyreWearFrontLeft')),
        ('Wear FR%', lambda l: _delta_wear(l, 'TyreWearFrontRight')),
        ('Wear RL%', lambda l: _delta_wear(l, 'TyreWearRearLeft')),
        ('Wear RR%', lambda l: _delta_wear(l, 'TyreWearRearRight')),
        ('Weather', lambda l: l.track.get('Weather', '?')),
    ]
    rows = []
    for label, fn in fields:
        rows.append([label] + [fn(lap) for lap in laps])
    return md_table(headers, rows)


def _delta_wear(lap: Lap, key: str) -> str:
    v = lap.ch.get(key, [])
    if len(v) >= 2:
        return f'{v[-1]-v[0]:.2f}'
    return '?'


def _corner_table(laps: list[Lap], corners: list[Corner]) -> str:
    n = len(laps)
    # build column labels for each non-reference lap
    seg_headers = [f'Δt seg L{k+1}−L1' for k in range(1, n)]
    cum_headers = [f'Δt cum L{k+1}−L1' for k in range(1, n)]
    headers = ['T'] + [f'Vmin L{i+1}' for i in range(n)] + \
              [f'time L{i+1}' for i in range(n)] + \
              seg_headers + cum_headers

    rows = []
    for c in corners:
        row = [str(c.number)]
        vmins = []
        seg_times: list[float | None] = []
        for lap in laps:
            d = lap.ch.get('LapDistance', [])
            spd = lap.ch.get('Speed', [])
            idxs = [i for i, v in enumerate(d) if c.start_m <= v <= c.end_m]
            if idxs and spd:
                spds = [spd[i] for i in idxs if i < len(spd)]
                vmins.append(f'{min(spds):.0f}')
            else:
                vmins.append('—')
            if lap.ch.get('LapDistance') and lap.ch.get('LapTime'):
                t = _interp_laptime(lap, c.end_m) - _interp_laptime(lap, c.start_m)
                seg_times.append(t)
            else:
                seg_times.append(None)

        times = [f'{t:.2f}' if t is not None else '—' for t in seg_times]
        row += vmins + times

        lap_a = laps[0]
        seg_a = seg_times[0]

        # per-segment Δt
        for k in range(1, n):
            if seg_times[k] is not None and seg_a is not None:
                row.append(f'{seg_times[k] - seg_a:+.3f}')
            else:
                row.append('—')

        # cumulative Δt at corner end
        ta_end = _interp_laptime(lap_a, c.end_m)
        for k in range(1, n):
            lap_k = laps[k]
            if lap_k.ch.get('LapDistance') and lap_k.ch.get('LapTime'):
                tk_end = _interp_laptime(lap_k, c.end_m)
                row.append(f'{tk_end - ta_end:+.3f}')
            else:
                row.append('—')

        rows.append(row)

    return md_table(headers, rows)


def _fuel_start(lap: Lap) -> float | None:
    raw = lap.track.get('Fuel at Start', lap.track.get('FuelAtStart', ''))
    raw = raw.strip().split()[0] if raw.strip() else ''
    try:
        return float(raw)
    except ValueError:
        return None


def _seg_time(lap: Lap, c: Corner) -> float | None:
    if not (lap.ch.get('LapDistance') and lap.ch.get('LapTime')):
        return None
    return _interp_laptime(lap, c.end_m) - _interp_laptime(lap, c.start_m)


def _vmin(lap: Lap, c: Corner) -> float | None:
    d = lap.ch.get('LapDistance', [])
    spd = lap.ch.get('Speed', [])
    idxs = [i for i, v in enumerate(d) if c.start_m <= v <= c.end_m and i < len(spd)]
    return min(spd[i] for i in idxs) if idxs else None


def _verdict(laps: list[Lap], corners: list[Corner]) -> str:
    # deterministic comparison of each non-reference lap vs lap A (lap 1)
    lap_a = laps[0]
    lines: list[str] = []
    for k in range(1, len(laps)):
        lap_k = laps[k]
        dt_total = laptime_s(lap_k) - laptime_s(lap_a)
        fa, fk = _fuel_start(lap_a), _fuel_start(lap_k)

        lines.append(f'### L{k + 1} vs L1')
        lines.append(f'- Итоговая Δ laptime: **{dt_total:+.3f} с** (L{k + 1} − L1)')
        if fa is not None and fk is not None:
            d_fuel = fa - fk
            fuel_lo = d_fuel * FUEL_S_PER_KG_LOW
            fuel_hi = d_fuel * FUEL_S_PER_KG_HIGH
            # residual = laptime delta minus fuel benefit; wider fuel benefit → lower residual
            res_lo = dt_total - max(fuel_lo, fuel_hi)
            res_hi = dt_total - min(fuel_lo, fuel_hi)
            lines.append(
                f'- Топливо: L1 {fa:.1f} кг / L{k + 1} {fk:.1f} кг → '
                f'поправка ~{min(fuel_lo, fuel_hi):+.3f}…{max(fuel_lo, fuel_hi):+.3f} с '
                f'(0.03–0.05 с/кг). '
                f'**Остаток (не топливо): {res_lo:+.3f}…{res_hi:+.3f} с**'
            )

        deltas: list[tuple[float, int, float | None, float | None]] = []
        for c in corners:
            ta, tk = _seg_time(lap_a, c), _seg_time(lap_k, c)
            if ta is None or tk is None:
                continue
            deltas.append((tk - ta, c.number, _vmin(lap_a, c), _vmin(lap_k, c)))

        losses = sorted([d for d in deltas if d[0] > 0], key=lambda x: -x[0])[:5]
        gains = sorted([d for d in deltas if d[0] < 0], key=lambda x: x[0])[:3]

        if losses:
            lines.append(f'- **Где L{k + 1} теряет** (топ |Δt seg|):')
            for dt, num, va, vk in losses:
                vm = f' | Vmin {va:.0f}→{vk:.0f}' if (va is not None and vk is not None) else ''
                lines.append(f'  - T{num}: {dt:+.3f} с{vm}')
        if gains:
            lines.append(f'- **Где L{k + 1} быстрее**:')
            for dt, num, va, vk in gains:
                vm = f' | Vmin {va:.0f}→{vk:.0f}' if (va is not None and vk is not None) else ''
                lines.append(f'  - T{num}: {dt:+.3f} с{vm}')
        lines.append('')

    return '\n'.join(lines).rstrip()


def _delta_trace(laps: list[Lap], corners: list[Corner]) -> tuple[str, list[float]]:
    lap_a = laps[0]
    dists = adaptive_points(lap_a, corners)
    if not dists:
        return '', []

    spds = [sample_at(lap, 'Speed', dists) for lap in laps]

    header_parts = ['dist'] + [f'spd_L{i+1}' for i in range(len(laps))] + \
                   [f'Δt_L{i+1}' for i in range(1, len(laps))]
    header = ','.join(header_parts)

    final_deltas: list[float] = []
    rows_str: list[str] = []
    for j, d in enumerate(dists):
        parts = [f'{d:.0f}']
        for i, lap in enumerate(laps):
            parts.append(f'{spds[i][j]:.0f}')
        deltas = []
        for k in range(1, len(laps)):
            ta = _interp_laptime(lap_a, d)
            tk = _interp_laptime(laps[k], d)
            deltas.append(f'{tk - ta:+.3f}')
        parts += deltas
        rows_str.append(','.join(parts))
        if j == len(dists) - 1:
            for k in range(1, len(laps)):
                ta = _interp_laptime(lap_a, d)
                tk = _interp_laptime(laps[k], d)
                final_deltas.append(tk - ta)

    block = '```\n' + header + '\n' + '\n'.join(rows_str) + '\n```'
    return block, final_deltas


def generate(laps: list[Lap], out_path: str, lang: str = 'ru', include_prompt: bool = True) -> tuple[str, int]:
    lap_a = laps[0]
    corners = detect_corners(lap_a)

    head_table = _header_table(laps)
    corner_table = _corner_table(laps, corners)
    verdict = _verdict(laps, corners)
    delta_block, final_deltas = _delta_trace(laps, corners)

    for k in range(1, len(laps)):
        lt_diff = laptime_s(laps[k]) - laptime_s(lap_a)
        final_dt = final_deltas[k - 1] if (k - 1) < len(final_deltas) else float('nan')
        print(f'Sanity L{k+1} vs L1: laptime diff={lt_diff:+.3f}s  final cumulative dt={final_dt:+.3f}s')

    parts = [
        '# Lap Comparison\n',
        head_table,
        '\n## Verdict (вычислено детерминированно)',
        verdict,
        '\n## Corners',
        corner_table,
        '\n## Delta trace',
        delta_block,
        '\n' + legend([LEGEND_DIST, LEGEND_SPD, LEGEND_DT_SEG, LEGEND_DT_CUM]),
    ]
    text = '\n'.join(parts)
    if include_prompt:
        prompt = load_prompt('compare', lang)
        if prompt:
            text += '\n\n---\n\n' + prompt
    return write_report(out_path, text)
