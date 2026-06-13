import os
import re
from dataclasses import dataclass

from .parser import _parse_header_row, _parse_value_row


def lap_token_present(stem: str) -> bool:
    return any(re.fullmatch(r'L\d+', t) for t in stem.split('_'))


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


@dataclass(frozen=True)
class RenameResult:
    old: str
    new: str | None
    status: str   # 'renamed' | 'skipped' | 'error'
    detail: str


def rename_unprocessed(targets: list[str]) -> list[RenameResult]:
    paths: list[str] = []
    for t in targets:
        t = os.path.abspath(t)
        if os.path.isdir(t):
            for name in os.listdir(t):
                if name.lower().endswith('.csv'):
                    paths.append(os.path.join(t, name))
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
        if lap_token_present(stem):
            results.append(RenameResult(name, None, 'skipped', 'already has lap number'))
            continue
        try:
            lap = read_lap_number(p)
        except Exception as e:
            results.append(RenameResult(name, None, 'error', str(e)))
            continue
        new_name = insert_lap_token(name, lap)
        dest = os.path.join(os.path.dirname(p), new_name)
        if os.path.exists(dest):
            results.append(RenameResult(name, new_name, 'error', 'target exists'))
            continue
        try:
            os.rename(p, dest)
        except OSError as e:
            results.append(RenameResult(name, new_name, 'error', str(e)))
            continue
        results.append(RenameResult(name, new_name, 'renamed', ''))
    return results
