import argparse
import os
import sys

from .parser import load_lap
from .report_common import report_path
from . import report_technique, report_setup, report_compare, report_race
from .rename import rename_unprocessed

_RACES_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'races'))


def _print_result(abs_path: str, tokens: int) -> None:
    print(abs_path)
    print(f'~{tokens} tokens (budget 60k)')


def _run_rename(targets: list[str]) -> None:
    expanded: list[str] = []
    for t in targets:
        p = os.path.abspath(t)
        if os.path.isdir(p):
            for name in os.listdir(p):
                if name.lower().endswith('.csv'):
                    expanded.append(os.path.join(p, name))
        elif p.lower().endswith('.csv'):
            expanded.append(p)

    if not expanded:
        print('Error: no CSV targets resolved', file=sys.stderr)
        sys.exit(2)

    results = rename_unprocessed(targets, races_dir=_RACES_DIR)
    for r in results:
        if r.status == 'renamed':
            print(f'renamed: {r.old} -> {r.new}')
        elif r.status == 'skipped':
            print(f'skipped: {r.old} (already has lap number)')
        else:
            print(f'error: {r.old} ({r.detail})')


def main() -> None:
    # no args → GUI
    if len(sys.argv) == 1:
        from .gui import main as gui_main
        gui_main()
        return

    parser = argparse.ArgumentParser(prog='python -m telemetry')
    parser.add_argument('mode', choices=['technique', 'setup', 'compare', 'race', 'rename', 'gui'])
    parser.add_argument('files', nargs='*')
    parser.add_argument('--lang', choices=['ru', 'en'], default='ru')
    args = parser.parse_args()

    mode: str = args.mode
    files: list[str] = args.files
    lang: str = args.lang

    if mode == 'gui':
        from .gui import main as gui_main
        gui_main()
        return

    if mode == 'rename':
        if not files:
            print('Error: rename requires at least one file or directory', file=sys.stderr)
            sys.exit(2)
        _run_rename(files)
        return

    if mode in ('technique', 'setup') and len(files) != 1:
        print(f'Error: {mode} requires exactly 1 file', file=sys.stderr)
        sys.exit(2)
    if mode == 'compare' and len(files) < 2:
        print('Error: compare requires 2+ files', file=sys.stderr)
        sys.exit(2)
    if mode == 'race' and len(files) != 1:
        print('Error: race requires exactly 1 directory', file=sys.stderr)
        sys.exit(2)

    if mode == 'technique':
        lap = load_lap(files[0])
        out = report_path(files[0], 'technique')
        _print_result(*report_technique.generate(lap, out, lang))

    elif mode == 'setup':
        lap = load_lap(files[0])
        out = report_path(files[0], 'setup')
        _print_result(*report_setup.generate(lap, out, lang))

    elif mode == 'compare':
        laps = [load_lap(f) for f in files]
        stem_b = os.path.splitext(os.path.basename(files[1]))[0]
        out = report_path(files[0], 'compare', stem_b)
        _print_result(*report_compare.generate(laps, out, lang))

    elif mode == 'race':
        race_dir = os.path.abspath(files[0])
        csv_files = sorted(
            f for f in os.listdir(race_dir) if f.lower().endswith('.csv')
        )
        if not csv_files:
            print(f'Error: no CSV files found in {race_dir}', file=sys.stderr)
            sys.exit(2)
        laps = [load_lap(os.path.join(race_dir, f)) for f in csv_files]
        dirname = os.path.basename(race_dir.rstrip('/\\'))
        out = os.path.join(race_dir, 'reports', dirname + '_race.md')
        _print_result(*report_race.generate(laps, out, lang))


if __name__ == '__main__':
    main()
