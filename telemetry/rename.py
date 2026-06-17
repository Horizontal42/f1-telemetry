import os
import re
from dataclasses import dataclass

from .parser import _parse_header_row, _parse_value_row

_SESSION_PAT = re.compile(r'^(FP[1-3]|P[1-3]|Q[1-3]|R|Race|Sprint)$', re.IGNORECASE)


def _session_folder(event: str) -> str:
    e = event.upper()
    if re.match(r'^(FP[1-3]|P[1-3])$', e):
        return 'Practice'
    if re.match(r'^(SQ[1-3]|Q[1-3])$', e):
        return 'Qualifying'
    if re.match(r'^SPRINT$', e):
        return 'Sprint'
    if re.match(r'^(R|RACE)$', e):
        return 'Race'
    return 'Other'


def _safe_dirname(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip(' .')


def lap_token_present(stem: str) -> bool:
    return any(re.fullmatch(r'L\d+', t) for t in stem.split('_'))


def session_token_present(stem: str) -> bool:
    return any(_SESSION_PAT.fullmatch(t) for t in stem.split('_'))


def _is_processed(stem: str) -> bool:
    return lap_token_present(stem) and session_token_present(stem)


def insert_tokens(filename: str, session_type: str, lap: int) -> str:
    base, ext = os.path.splitext(filename)
    tokens = base.split('_')
    lap_tok = f'L{lap}'
    for i, t in enumerate(tokens):
        if re.fullmatch(r'\d+(\.\d+)?', t):
            tokens = tokens[:i] + [session_type, lap_tok] + tokens[i:]
            return '_'.join(tokens) + ext
    if len(tokens) >= 2:
        tokens = tokens[:2] + [session_type, lap_tok] + tokens[2:]
    else:
        tokens += [session_type, lap_tok]
    return '_'.join(tokens) + ext


# kept for backward compat (tests + external callers)
def insert_lap_token(filename: str, lap: int) -> str:
    base, ext = os.path.splitext(filename)
    tokens = base.split('_')
    token = f'L{lap}'
    for i, t in enumerate(tokens):
        if re.fullmatch(r'\d+(\.\d+)?', t):
            tokens.insert(i, token)
            return '_'.join(tokens) + ext
    if len(tokens) >= 2:
        tokens.insert(2, token)
    else:
        tokens.append(token)
    return '_'.join(tokens) + ext


def read_lap_number(path: str) -> int:
    with open(path, encoding='utf-8') as f:
        lines = [f.readline() for _ in range(5)]
    keys = _parse_header_row(lines[3])
    vals = _parse_value_row(lines[4])
    track = dict(zip(keys, vals))
    return int(float(track['Lap']))


def read_session_type(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        lines = [f.readline() for _ in range(3)]
    keys = _parse_header_row(lines[1])
    vals = _parse_value_row(lines[2])
    session = dict(zip(keys, vals))
    return session.get('event', '').strip()


def read_metadata(path: str) -> tuple[int, str, str]:
    """Returns (lap_number, event_type, track_name)."""
    with open(path, encoding='utf-8') as f:
        lines = [f.readline() for _ in range(5)]
    sess_keys = _parse_header_row(lines[1])
    sess_vals = _parse_value_row(lines[2])
    session = dict(zip(sess_keys, sess_vals))
    track_keys = _parse_header_row(lines[3])
    track_vals = _parse_value_row(lines[4])
    track = dict(zip(track_keys, track_vals))
    return (
        int(float(track['Lap'])),
        session.get('event', '').strip(),
        session.get('track', '').strip(),
    )


@dataclass(frozen=True)
class RenameResult:
    old: str
    new: str | None
    status: str   # 'renamed' | 'skipped' | 'error'
    detail: str


def rename_unprocessed(targets: list[str], races_dir: str | None = None) -> list[RenameResult]:
    paths: list[str] = []
    for t in targets:
        t = os.path.abspath(t)
        if os.path.isdir(t):
            if races_dir is not None:
                for root, _, files in os.walk(t):
                    for fname in sorted(files):
                        if fname.lower().endswith('.csv'):
                            paths.append(os.path.join(root, fname))
            else:
                for fname in os.listdir(t):
                    if fname.lower().endswith('.csv'):
                        paths.append(os.path.join(t, fname))
        else:
            paths.append(t)

    results: list[RenameResult] = []
    for p in paths:
        name = os.path.basename(p)
        if not os.path.isfile(p):
            results.append(RenameResult(name, None, 'error', 'file not found'))
            continue
        if not name.lower().endswith('.csv'):
            results.append(RenameResult(name, None, 'error', 'not a CSV file'))
            continue
        stem = os.path.splitext(name)[0]

        if races_dir is None:
            if _is_processed(stem):
                results.append(RenameResult(name, None, 'skipped', 'already processed'))
                continue
            try:
                lap, session_type, _ = read_metadata(p)
            except Exception as e:
                results.append(RenameResult(name, None, 'error', str(e)))
                continue
            if not session_type:
                results.append(RenameResult(name, None, 'error', 'session type not found in CSV'))
                continue
            new_name = insert_tokens(name, session_type, lap)
            dest = os.path.join(os.path.dirname(p), new_name)
        else:
            try:
                lap, session_type, track_name = read_metadata(p)
            except Exception as e:
                results.append(RenameResult(name, None, 'error', str(e)))
                continue
            if not session_type:
                results.append(RenameResult(name, None, 'error', 'session type not found in CSV'))
                continue
            new_name = name if _is_processed(stem) else insert_tokens(name, session_type, lap)
            dest_dir = os.path.join(races_dir, _safe_dirname(track_name), _session_folder(session_type))
            dest = os.path.join(dest_dir, new_name)
            if os.path.abspath(p) == os.path.abspath(dest):
                results.append(RenameResult(name, None, 'skipped', 'already in place'))
                continue
            os.makedirs(dest_dir, exist_ok=True)

        if os.path.exists(dest) and os.path.abspath(dest) != os.path.abspath(p):
            results.append(RenameResult(name, dest, 'error', 'target exists'))
            continue
        try:
            os.rename(p, dest)
        except OSError as e:
            results.append(RenameResult(name, dest, 'error', str(e)))
            continue
        results.append(RenameResult(name, dest, 'renamed', ''))
    return results
