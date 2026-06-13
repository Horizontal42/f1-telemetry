import re
from dataclasses import dataclass


def _strip_unit(name: str) -> str:
    return re.sub(r'\s*[\[({][^\]})]*[\]})]\s*$', '', name).strip()


def _parse_header_row(line: str) -> list[str]:
    return [_strip_unit(h) for h in line.rstrip('\n').split(',')]


def _parse_value_row(line: str) -> list[str]:
    return line.rstrip('\n').split(',')


@dataclass(frozen=True)
class Lap:
    session: dict[str, str]
    track: dict[str, str]
    setup: dict[str, str]
    ch: dict[str, list[float]]
    n: int


def load_lap(path: str) -> Lap:
    with open(path, encoding='utf-8') as f:
        raw = f.readlines()

    session_keys = _parse_header_row(raw[1])
    session_vals = _parse_value_row(raw[2])
    session = dict(zip(session_keys, session_vals))

    track_keys = _parse_header_row(raw[3])
    track_vals = _parse_value_row(raw[4])
    track = dict(zip(track_keys, track_vals))

    setup_keys = _parse_header_row(raw[5])
    setup_vals = _parse_value_row(raw[6])
    # drop trailing empty from the trailing comma
    setup_vals = [v for v in setup_vals if v.strip() != '']
    setup = dict(zip(setup_keys[:len(setup_vals)], setup_vals))

    tel_keys = _parse_header_row(raw[7])
    n_cols = len(tel_keys)

    columns: dict[str, list[float]] = {k: [] for k in tel_keys}
    for line in raw[8:]:
        line = line.rstrip('\n')
        if not line.strip():
            continue
        parts = line.split(',')
        if len(parts) < n_cols:
            continue
        try:
            vals = [float(parts[i]) for i in range(n_cols)]
        except ValueError:
            continue
        for k, v in zip(tel_keys, vals):
            columns[k].append(v)

    # drop all-zero channels
    ch = {k: v for k, v in columns.items() if any(x != 0.0 for x in v)}

    return Lap(session=session, track=track, setup=setup, ch=ch, n=len(next(iter(columns.values()), [])))


def laptime_s(lap: Lap) -> float:
    return float(lap.session.get('laptime', 0.0))


def sector_times(lap: Lap) -> tuple[float, float, float]:
    s1 = float(lap.session.get('S1', 0.0))
    s2 = float(lap.session.get('S2', 0.0))
    s3 = float(lap.session.get('S3', 0.0))
    return s1, s2, s3
