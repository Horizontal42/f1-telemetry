from .parser import Lap, laptime_s, sector_times
from .report_common import md_table, write_report, load_prompt


def _fmt_laptime(s: float) -> str:
    mins = int(s) // 60
    secs = s - mins * 60
    return f'{mins}:{secs:06.3f}'


def _fmt_sector(s: float) -> str:
    return f'{s:.3f}'


def _fuel_start(lap: Lap) -> float:
    raw = lap.track.get('Fuel at Start', lap.track.get('FuelAtStart', '0'))
    raw = raw.strip().split()[0] if raw.strip() else '0'
    try:
        return float(raw)
    except ValueError:
        pass
    v = lap.ch.get('FuelRemaining', [0.0])
    return v[0] if v else 0.0


def _dedup_laps(laps: list[Lap]) -> list[Lap]:
    def lap_num(lap: Lap) -> int:
        try:
            return int(lap.track.get('Lap', '0'))
        except ValueError:
            return 0

    # Only dedup laps that carry a real positive lap number. Laps without one (export
    # missing the field → all parse to 0) are kept verbatim, so a missing 'Lap' column
    # can never silently collapse the whole race to a single lap.
    numbered = [l for l in laps if lap_num(l) > 0]
    unnumbered = [l for l in laps if lap_num(l) <= 0]

    best: dict[int, Lap] = {}
    for lap in numbered:
        n = lap_num(lap)
        cur = best.get(n)
        if cur is None:
            best[n] = lap
            continue
        lap_valid = lap.track.get('Valid', 'true').lower() != 'false'
        cur_valid = cur.track.get('Valid', 'true').lower() != 'false'
        if lap_valid != cur_valid:
            if lap_valid:
                best[n] = lap
            continue
        if laptime_s(lap) < laptime_s(cur):
            best[n] = lap
    return list(best.values()) + unnumbered


def _sort_laps(laps: list[Lap]) -> list[Lap]:
    def lap_num(lap: Lap) -> int:
        try:
            return int(lap.track.get('Lap', '0'))
        except ValueError:
            return 0
    return sorted(laps, key=lap_num)


def _assign_stints(laps: list[Lap]) -> tuple[list[int], list[int]]:
    stints: list[int] = []
    ages: list[int] = []
    stint = 1
    age = 1
    prev_tyre = ''
    prev_was_pit = False

    for i, lap in enumerate(laps):
        tyre = lap.track.get('Tyre', '')
        if i > 0 and (prev_was_pit or tyre != prev_tyre):
            stint += 1
            age = 1

        stints.append(stint)
        ages.append(age)

        prev_tyre = tyre
        prev_was_pit = lap.track.get('Pitlap', 'false').lower() == 'true'
        age += 1

    return stints, ages


def _header(laps: list[Lap]) -> str:
    if not laps:
        return ''
    first = laps[0]
    s = first.session
    t = first.track
    track = s.get('track', '?')
    car = s.get('car', '?')
    total = len(laps)
    weather = t.get('Weather', '?')
    track_temp = t.get('TrackTemp', '?')
    air_temp = t.get('AmbientTemp', '?')
    lines = [
        f'**Track:** {track}  ',
        f'**Car:** {car}  ',
        f'**Total laps:** {total}  ',
        f'**Weather:** {weather}  ',
        f'**Track temp:** {track_temp} °C  **Air:** {air_temp} °C  ',
    ]
    return '\n'.join(lines)


def _race_pos(lap: Lap) -> str:
    pos = lap.ch.get('RacePosition', [])
    if not pos:
        return '—'
    v = int(pos[-1])
    return str(v) if v > 0 else '—'


def _lap_times_table(laps: list[Lap], stints: list[int], ages: list[int]) -> str:
    # find fastest valid lap time
    best_time = None
    for lap in laps:
        valid = lap.track.get('Valid', 'true').lower() != 'false'
        pit = lap.track.get('Pitlap', 'false').lower() == 'true'
        if valid and not pit:
            lt = laptime_s(lap)
            if lt > 0 and (best_time is None or lt < best_time):
                best_time = lt

    rows = []
    for i, lap in enumerate(laps):
        lap_n = lap.track.get('Lap', str(i + 1))
        lt = laptime_s(lap)
        s1, s2, s3 = sector_times(lap)
        tyre = lap.track.get('Tyre', '?')
        age = ages[i]
        fuel = _fuel_start(lap)
        valid = lap.track.get('Valid', 'true').lower() != 'false'
        pit = lap.track.get('Pitlap', 'false').lower() == 'true'

        notes = []
        if pit:
            notes.append('PIT')
        if not valid:
            notes.append('INV')
        if valid and not pit and best_time is not None and lt == best_time:
            notes.append('FAST')

        rows.append([
            lap_n,
            _race_pos(lap),
            _fmt_laptime(lt) if lt > 0 else '—',
            _fmt_sector(s1) if s1 > 0 else '—',
            _fmt_sector(s2) if s2 > 0 else '—',
            _fmt_sector(s3) if s3 > 0 else '—',
            tyre,
            str(age),
            f'{fuel:.1f}',
            ' '.join(notes),
        ])

    return md_table(
        ['Lap', 'Pos', 'Time', 'S1', 'S2', 'S3', 'Tyre', 'Age', 'Fuel kg', 'Note'],
        rows,
    )


def _stint_summary(laps: list[Lap], stints: list[int], ages: list[int]) -> str:
    # group by stint
    stint_map: dict[int, list[tuple[Lap, int]]] = {}
    for i, lap in enumerate(laps):
        st = stints[i]
        stint_map.setdefault(st, []).append((lap, ages[i]))

    rows = []
    for st in sorted(stint_map):
        entries = stint_map[st]
        tyre = entries[0][0].track.get('Tyre', '?')
        laps_on = max(age for _, age in entries)
        n_laps = len(entries)

        # exclude pit laps from stats
        valid_entries = [
            (lap, age) for lap, age in entries
            if lap.track.get('Valid', 'true').lower() != 'false'
            and lap.track.get('Pitlap', 'false').lower() != 'true'
        ]
        times = [laptime_s(lap) for lap, _ in valid_entries if laptime_s(lap) > 0]

        if times:
            avg = sum(times) / len(times)
            best = min(times)
            worst = max(times)
            avg_s = _fmt_laptime(avg)
            best_s = _fmt_laptime(best)
            worst_s = _fmt_laptime(worst)
        else:
            avg_s = best_s = worst_s = '—'

        # degradation: slope of lap time vs tyre age
        if len(valid_entries) >= 2:
            first_lap, first_age = valid_entries[0]
            last_lap, last_age = valid_entries[-1]
            ft = laptime_s(first_lap)
            lt = laptime_s(last_lap)
            da = last_age - first_age
            if da > 0 and ft > 0 and lt > 0:
                deg = (lt - ft) / da
                deg_s = f'{deg:+.3f}'
            else:
                deg_s = '—'
        else:
            deg_s = '—'

        rows.append([
            str(st),
            str(n_laps),
            tyre,
            str(laps_on),
            avg_s,
            best_s,
            worst_s,
            deg_s,
        ])

    return md_table(
        ['Stint', 'Laps', 'Tyre', 'Laps on tyre', 'Avg pace', 'Best', 'Worst', 'Deg s/lap'],
        rows,
    )


def _tyre_wear_table(laps: list[Lap]) -> str:
    rows = []
    for i, lap in enumerate(laps):
        lap_n = lap.track.get('Lap', str(i + 1))
        ch = lap.ch
        fl = ch.get('TyreWearFrontLeft', [])
        fr = ch.get('TyreWearFrontRight', [])
        rl = ch.get('TyreWearRearLeft', [])
        rr = ch.get('TyreWearRearRight', [])
        rows.append([
            lap_n,
            f'{fl[-1]:.2f}' if fl else '—',
            f'{fr[-1]:.2f}' if fr else '—',
            f'{rl[-1]:.2f}' if rl else '—',
            f'{rr[-1]:.2f}' if rr else '—',
        ])
    return md_table(['Lap', 'FL%', 'FR%', 'RL%', 'RR%'], rows)


def _thermal_table(laps: list[Lap]) -> str:
    rows = []
    for i, lap in enumerate(laps):
        lap_n = lap.track.get('Lap', str(i + 1))
        ch = lap.ch

        tf_fl = ch.get('TyreTemperatureFrontLeft', [])
        tf_fr = ch.get('TyreTemperatureFrontRight', [])
        tr_rl = ch.get('TyreTemperatureRearLeft', [])
        tr_rr = ch.get('TyreTemperatureRearRight', [])

        tf_avg = ((max(tf_fl) if tf_fl else 0) + (max(tf_fr) if tf_fr else 0)) / 2
        tr_avg = ((max(tr_rl) if tr_rl else 0) + (max(tr_rr) if tr_rr else 0)) / 2

        bt_fl = ch.get('BrakeTemperatureFrontLeft', [])
        bt_rr = ch.get('BrakeTemperatureRearRight', [])

        rows.append([
            lap_n,
            f'{tf_avg:.0f}' if tf_fl or tf_fr else '—',
            f'{tr_avg:.0f}' if tr_rl or tr_rr else '—',
            f'{max(bt_fl):.0f}' if bt_fl else '—',
            f'{max(bt_rr):.0f}' if bt_rr else '—',
        ])
    return md_table(['Lap', 'Tf avg°C', 'Tr avg°C', 'Brk FL max°C', 'Brk RR max°C'], rows)


def _ers_table(laps: list[Lap]) -> str:
    rows = []
    for i, lap in enumerate(laps):
        lap_n = lap.track.get('Lap', str(i + 1))
        ch = lap.ch
        ers = ch.get('ERSSpent', [])
        mguk = ch.get('MGUKHarvested', [])
        mguh = ch.get('MGUHHarvested', [])
        rows.append([
            lap_n,
            f'{ers[-1] / 1e6:.3f}' if ers else '—',
            f'{mguk[-1] / 1e6:.3f}' if mguk else '—',
            f'{mguh[-1] / 1e6:.3f}' if mguh else '—',
        ])
    return md_table(['Lap', 'ERS MJ', 'MGU-K MJ', 'MGU-H MJ'], rows)


def generate(laps: list[Lap], out_path: str, lang: str = 'ru', include_prompt: bool = True) -> tuple[str, int]:
    laps = _dedup_laps(laps)
    laps = _sort_laps(laps)
    stints, ages = _assign_stints(laps)

    parts = [
        _header(laps),
        '\n## Lap times',
        _lap_times_table(laps, stints, ages),
        '\n## Stint summary',
        _stint_summary(laps, stints, ages),
        '\n## Tyre wear per lap',
        _tyre_wear_table(laps),
        '\n## Thermal summary per lap',
        _thermal_table(laps),
        '\n## ERS per lap',
        _ers_table(laps),
    ]
    text = '\n'.join(parts)
    if include_prompt:
        prompt = load_prompt('race', lang)
        if prompt:
            text += '\n\n---\n\n' + prompt
    return write_report(out_path, text)
