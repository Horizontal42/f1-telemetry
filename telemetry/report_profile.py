# Cheap full-field aggregate: scans every lap (corner tables only, no trace) to surface
# chronic driver tendencies and auto-pick laps worth a deep dive. Track-agnostic:
# corners are clustered by apex distance (not index) and tendencies are relative to the
# session, so it works on any track / compound without per-track calibration.
from .parser import Lap, laptime_s
from .segments import detect_corners, Corner, merge_gap_for
from .report_common import md_table, write_report, load_prompt
from .report_race import _dedup_laps, _sort_laps

# Corners are clustered across laps by apex distance. The gap reuses the detector's own
# track-adaptive merge gap (merge_gap_for), so the cluster count stays aligned with per-lap
# corner numbers (profile Tn == technique Tn) on chicanes and long circuits alike.

MIN_LAPS_PER_COMPOUND = 3
# chronic = relative outlier vs the rest of the session's corners, with a physics floor
# so a benign track never raises false alarms.
COAST_REL, COAST_FLOOR = 1.5, 35.0
SPIN_REL, SPIN_FLOOR = 1.7, 4.0
LOCK_REL, LOCK_FLOOR = 1.7, 5.0
TR_MARGIN, TR_FLOOR = 8.0, 100.0


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _is_valid(lap: Lap) -> bool:
    return lap.track.get('Valid', 'true').lower() != 'false'


def _is_pit(lap: Lap) -> bool:
    return lap.track.get('Pitlap', 'false').lower() == 'true'


def _lap_no(lap: Lap) -> str:
    return lap.track.get('Lap', '?')


def _clean_laps(laps: list[Lap]) -> list[Lap]:
    return [l for l in laps if _is_valid(l) and not _is_pit(l) and laptime_s(l) > 0]


def _by_compound(laps: list[Lap]) -> list[tuple[str, list[Lap]]]:
    groups: dict[str, list[Lap]] = {}
    for l in laps:
        groups.setdefault(l.track.get('Tyre', '?'), []).append(l)
    return sorted(groups.items(), key=lambda kv: -len(kv[1]))


def _cluster_corners(per: list[tuple[Lap, list[Corner]]], gap: float) -> list[list[Corner]]:
    # group corners across laps by apex location, robust to a lap detecting one extra/fewer
    flat = sorted(
        ((c.apex_m, c) for _, cs in per for c in cs),
        key=lambda x: x[0],
    )
    if not flat:
        return []

    clusters: list[list[Corner]] = [[flat[0][1]]]
    last_apex = flat[0][0]
    for apex, c in flat[1:]:
        if apex - last_apex > gap:
            clusters.append([c])
        else:
            clusters[-1].append(c)
        last_apex = apex

    min_support = max(2, len(per) // 2)
    return [cl for cl in clusters if len(cl) >= min_support]


def _aggregate_compound(laps: list[Lap]) -> tuple[str, list[str]]:
    per = [(l, detect_corners(l)) for l in laps]
    clusters = _cluster_corners(per, merge_gap_for(laps[0]))
    if not clusters:
        return '', []

    agg = []
    for num, cl in enumerate(clusters, 1):
        agg.append({
            'num': num,
            'vmin': _median([c.v_min for c in cl]),
            'coast': _median([c.coast_m for c in cl]),
            'lock': _median([c.lock_pct for c in cl]),
            'spin': _median([c.spin_pct for c in cl]),
            'tr': _median([c.rear_tyre_temp_peak for c in cl]),
            'lock_freq': sum(1 for c in cl if c.lockup) / len(cl) * 100,
            'spin_freq': sum(1 for c in cl if c.wheelspin) / len(cl) * 100,
        })

    med_coast = _median([a['coast'] for a in agg])
    med_spin = _median([a['spin'] for a in agg])
    med_lockmag = _median([abs(a['lock']) for a in agg])
    med_tr = _median([a['tr'] for a in agg])

    rows, chronic = [], []
    for a in agg:
        rows.append([
            f"T{a['num']}", f"{a['vmin']:.0f}", f"{a['coast']:.0f}",
            f"{a['lock']:.1f}", f"{a['spin']:.1f}",
            f"{a['lock_freq']:.0f}", f"{a['spin_freq']:.0f}", f"{a['tr']:.0f}",
        ])
        if a['coast'] >= max(COAST_REL * med_coast, COAST_FLOOR):
            chronic.append(f"T{a['num']}: длинный медианный coast {a['coast']:.0f} м — осторожный переход тормоз→газ")
        if a['spin'] >= max(SPIN_REL * med_spin, SPIN_FLOOR) or a['spin_freq'] >= 25:
            chronic.append(f"T{a['num']}: склонность к пробуксовке на выходе (медиана spin {a['spin']:.1f}%) — ранний/резкий газ")
        if abs(a['lock']) >= max(LOCK_REL * med_lockmag, LOCK_FLOOR) or a['lock_freq'] >= 25:
            chronic.append(f"T{a['num']}: склонность к блокировке на входе (медиана lock {a['lock']:.1f}%) — поздняя/жёсткая педаль")
        if a['tr'] >= med_tr + TR_MARGIN and a['tr'] >= TR_FLOOR:
            chronic.append(f"T{a['num']}: высокая нагрузка на задние шины (медиана Tr {a['tr']:.0f}°C) — тепловой риск в длинном стинте")

    table = md_table(
        ['T', 'Vmin', 'coast m', 'lock%', 'spin%', 'LOCK %laps', 'SPIN %laps', 'Tr peak °C'],
        rows,
    )
    return table, chronic


def _recommend_laps(all_clean: list[Lap]) -> str:
    def rear_peak(l: Lap) -> float:
        rl = l.ch.get('TyreTemperatureRearLeft', [])
        rr = l.ch.get('TyreTemperatureRearRight', [])
        return max((max(rl) if rl else 0), (max(rr) if rr else 0))

    def worst_corner(l: Lap, attr: str, sign: float) -> float:
        cs = detect_corners(l)
        return max((sign * getattr(c, attr) for c in cs), default=0.0)

    picks = [
        ('быстрейший валидный', min(all_clean, key=laptime_s)),
        ('худший валидный', max(all_clean, key=laptime_s)),
        ('тепловой пик (задние)', max(all_clean, key=rear_peak)),
        ('макс. пробуксовка', max(all_clean, key=lambda l: worst_corner(l, 'spin_pct', 1.0))),
        ('макс. блокировка', max(all_clean, key=lambda l: worst_corner(l, 'lock_pct', -1.0))),
    ]

    seen: dict[str, str] = {}
    tyre: dict[str, str] = {}
    for reason, lap in picks:
        key = _lap_no(lap)
        seen[key] = (seen.get(key, '') + '; ' + reason).lstrip('; ')
        tyre[key] = lap.track.get('Tyre', '?')

    rows = [[f'L{k}', tyre[k], seen[k]] for k in seen]
    return md_table(['Круг', 'Состав', 'Почему интересен'], rows)


def generate(laps: list[Lap], out_path: str, lang: str = 'ru', include_prompt: bool = True) -> tuple[str, int]:
    laps = _sort_laps(_dedup_laps(laps))
    clean = _clean_laps(laps)

    if not clean:
        return write_report(out_path, '_Нет валидных кругов для профилирования._')

    first = laps[0]
    breakdown = {}
    for l in clean:
        t = l.track.get('Tyre', '?')
        breakdown[t] = breakdown.get(t, 0) + 1
    breakdown_str = ', '.join(f'{k}: {v}' for k, v in breakdown.items())

    parts = [
        f'**Track:** {first.session.get("track", "?")}  ',
        f'**Car:** {first.session.get("car", "?")}  ',
        f'**Валидных кругов:** {len(clean)} из {len(laps)}  ',
        f'**Составы (валидные круги):** {breakdown_str}  ',
    ]

    profiled = False
    for comp, claps in _by_compound(clean):
        if len(claps) < MIN_LAPS_PER_COMPOUND:
            continue
        table, chronic = _aggregate_compound(claps)
        if not table:
            continue
        profiled = True
        parts.append(f'\n## Тенденции по поворотам — состав {comp} ({len(claps)} кругов)')
        parts.append(table)
        parts.append(f'\n### Хронические паттерны — {comp} (авто-детект, относительно сессии)')
        parts.append('\n'.join(f'- {c}' for c in chronic) if chronic
                     else '- Явных хронических паттернов не выявлено.')

    if not profiled:
        parts.append(f'\n_Недостаточно кругов на один состав для агрегации (нужно ≥{MIN_LAPS_PER_COMPOUND}).')

    parts += [
        '\n## Рекомендованные круги для детального разбора',
        _recommend_laps(clean),
        '\n## Легенда',
        '- `coast m` = медианный накат без тормоза и полного газа (большой = осторожный переход)',
        '- `LOCK %laps` / `SPIN %laps` = доля кругов с флагом блокировки / пробуксовки в этом повороте',
        '- Повороты кластеризуются по дистанции апекса (а не по индексу) — устойчиво к разному числу детектируемых поворотов',
        '- Хроника считается ОТНОСИТЕЛЬНО медианы поворотов сессии (адаптивно к трассе) с физическим порогом-полом',
    ]
    text = '\n'.join(parts)
    if include_prompt:
        prompt = load_prompt('profile', lang)
        if prompt:
            text += '\n\n---\n\n' + prompt
    return write_report(out_path, text)
