import os
import tempfile

from .parser import Lap, laptime_s, sector_times


def game_of(lap: Lap) -> str:
    return 'acc' if lap.session.get('Game', '').upper().startswith('ACC') else 'f1'


def header_block(lap: Lap) -> str:
    s = lap.session
    t = lap.track
    lt = laptime_s(lap)
    s1, s2, s3 = sector_times(lap)
    lap_n = t.get('Lap', '?')
    laps_total = t.get('LapsInRace', '?')
    fuel_start = t.get('Fuel at Start', '?')
    try:
        fuel_start = f'{float(fuel_start):.2f} kg'
    except (ValueError, TypeError):
        pass

    lines = [
        f'**Track:** {s.get("track", "?")}  ',
        f'**Car:** {s.get("car", "?")}  ',
        f'**Event:** {s.get("event", "?")}  ',
        f'**Laptime:** {lt:.3f} s  (S1 {s1:.3f} / S2 {s2:.3f} / S3 {s3:.3f})  ',
        f'**Tyre:** {t.get("Tyre", "?")}  ',
        f'**Weather:** {t.get("Weather", "?")}  ',
        f'**Track temp:** {t.get("TrackTemp", "?")} °C  **Air:** {t.get("AmbientTemp", "?")} °C  ',
        f'**Lap:** {lap_n} / {laps_total}  ',
        f'**Fuel at start:** {fuel_start}  ',
    ]
    return '\n'.join(lines)


def setup_summary(lap: Lap) -> str:
    s = lap.setup
    return (
        f'FWing {s.get("FWing","?")} / RWing {s.get("RWing","?")} | '
        f'BrakeBias {s.get("BrakeBias","?")}% | '
        f'FL {s.get("FLTyrePressure","?")} FR {s.get("FRTyrePressure","?")} '
        f'RL {s.get("RLTyrePressure","?")} RR {s.get("RRTyrePressure","?")} PSI'
    )


LEGEND_DIST = '- `dist` = LapDistance [m]'
LEGEND_TIME = '- `time` = elapsed LapTime [s]'
LEGEND_SPD = '- `spd` = Speed [km/h]'
LEGEND_THR_BRK = '- `thr` / `brk` = ThrottlePercentage / BrakePercentage [0–100 %]'
LEGEND_STEER = '- `steer` = steering lock [%], negative = left, positive = right'
LEGEND_GEAR = '- `gear` = selected gear (2–8)'
LEGEND_DRS = '- `drs` = DRS active (0 = off, 1 = on)'
LEGEND_GLAT = '- `gLat` = lateral G-force [G], positive = right corner'
LEGEND_GLON = '- `gLon` = longitudinal G-force [G], negative = braking, positive = acceleration'
LEGEND_FUEL = '- `fuel` = FuelRemaining [kg]'
LEGEND_ERS = '- `ers` = ERSSpent [MJ], cumulative energy deployed from ERS'
LEGEND_LOCK = '- LOCK flag = front relative slip (slip km/h / speed km/h × 100) < −10 % while braking (severe lockup only)'
LEGEND_SPIN = '- SPIN flag = rear relative slip > +8 % while on throttle (severe wheelspin only)'
LEGEND_TF = '- `Tf` / `Tr` = surface tyre temperature front/rear average [°C]'
LEGEND_RPM = '- `rpm` = engine revs (rounded to nearest 100)'
LEGEND_SLIP = '- `slipF` / `slipR` = relative wheel slip front/rear [%], negative front = locking tendency, positive rear = wheelspin tendency'
LEGEND_YAW = '- `yaw` = yaw rate [rad/s] (LocalAngularVelocityY); large steer + small yaw = understeer'
LEGEND_SUSP = '- Suspension positions in mm; rake = front avg − rear avg; roll = left avg − right avg per corner (positive = left side compressed)'
LEGEND_DT_SEG = '- `Δt seg` = per-segment time delta (positive = lap X slower in that zone)'
LEGEND_DT_CUM = '- `Δt cum` = cumulative delta at zone end vs lap A [s], negative = lap X faster up to that point'
LEGEND_STEER_G_CAVEAT = '- steer/g and slip balance are speed-dependent — only compare corners of similar Vmin'


def legend(entries: list[str]) -> str:
    return '## Legend\n' + '\n'.join(entries)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    sep = ['---'] * len(headers)
    lines = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(sep) + ' |',
    ]
    for row in rows:
        lines.append('| ' + ' | '.join(str(c) for c in row) + ' |')
    return '\n'.join(lines)


def token_estimate(text: str) -> int:
    return int(len(text) / 3.5)


def write_report(path: str, text: str) -> tuple[str, int]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_ = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix='.tmp')
    try:
        # close the raw fd so we can open in text mode (platform newlines, UTF-8)
        os.close(fd)
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    tokens = token_estimate(text)
    return os.path.abspath(path), tokens


def load_prompt(mode: str, lang: str, game: str = 'f1') -> str:
    here = os.path.dirname(__file__)
    base = os.path.join(here, '..', 'prompts', lang)
    # ACC gets its own prompt set, falling back to the F1 prompt when absent.
    candidates = []
    if game == 'acc':
        candidates.append(os.path.normpath(os.path.join(base, 'acc', f'{mode}.md')))
    candidates.append(os.path.normpath(os.path.join(base, f'{mode}.md')))
    for p in candidates:
        try:
            with open(p, encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return ''


def report_path(input_path: str, mode: str, other_stem: str = '') -> str:
    d = os.path.dirname(os.path.abspath(input_path))
    reports_dir = os.path.join(d, 'reports')
    stem = os.path.splitext(os.path.basename(input_path))[0]
    if mode == 'compare' and other_stem:
        fname = f'compare_{stem}_vs_{other_stem}.md'
    else:
        fname = f'{stem}_{mode}.md'
    return os.path.join(reports_dir, fname)
