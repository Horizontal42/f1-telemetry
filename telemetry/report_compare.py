import bisect

from .parser import Lap, laptime_s, sector_times
from .segments import detect_corners, Corner
from .resample import adaptive_points, sample_at
from .report_common import (
    legend, md_table, write_report, token_estimate, load_prompt,
    LEGEND_DIST, LEGEND_SPD, LEGEND_DT_SEG, LEGEND_DT_CUM,
)


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


def generate(laps: list[Lap], out_path: str, lang: str = 'ru') -> tuple[str, int]:
    lap_a = laps[0]
    corners = detect_corners(lap_a)

    head_table = _header_table(laps)
    corner_table = _corner_table(laps, corners)
    delta_block, final_deltas = _delta_trace(laps, corners)

    for k in range(1, len(laps)):
        lt_diff = laptime_s(laps[k]) - laptime_s(lap_a)
        final_dt = final_deltas[k - 1] if (k - 1) < len(final_deltas) else float('nan')
        print(f'Sanity L{k+1} vs L1: laptime diff={lt_diff:+.3f}s  final cumulative dt={final_dt:+.3f}s')

    parts = [
        '# Lap Comparison\n',
        head_table,
        '\n## Corners',
        corner_table,
        '\n## Delta trace',
        delta_block,
        '\n' + legend([LEGEND_DIST, LEGEND_SPD, LEGEND_DT_SEG, LEGEND_DT_CUM]),
    ]
    text = '\n'.join(parts)
    prompt = load_prompt('compare', lang)
    if prompt:
        text += '\n\n---\n\n' + prompt
    return write_report(out_path, text)
