import argparse
import os
import sys

from .parser import load_lap
from .report_common import report_path
from . import report_technique, report_setup, report_compare, report_race, report_profile
from .rename import rename_unprocessed

_RACES_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'races'))


def is_fresh(report: str, sources: list[str]) -> bool:
    if not os.path.isfile(report):
        return False
    try:
        r_mtime = os.path.getmtime(report)
        return all(os.path.getmtime(s) <= r_mtime for s in sources if os.path.isfile(s))
    except OSError:
        return False


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
    parser.add_argument('mode', choices=['technique', 'setup', 'compare', 'race', 'profile', 'rename', 'gui'])
    parser.add_argument('files', nargs='*')
    parser.add_argument('--lang', choices=['ru', 'en'], default='ru')
    parser.add_argument('--game', choices=['auto', 'f1', 'acc'], default='auto',
                        help='override game detection (default: auto, from the Game field)')
    parser.add_argument('--no-prompt', action='store_true',
                        help='omit the embedded analysis prompt (for agent pipelines)')
    parser.add_argument('--force', action='store_true',
                        help='regenerate even if a fresh report already exists')
    args = parser.parse_args()

    mode: str = args.mode
    files: list[str] = args.files
    lang: str = args.lang
    game: str | None = None if args.game == 'auto' else args.game
    include_prompt: bool = not args.no_prompt
    force: bool = args.force

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
    if mode in ('race', 'profile') and len(files) != 1:
        print(f'Error: {mode} requires exactly 1 directory', file=sys.stderr)
        sys.exit(2)

    def _emit(out: str, sources: list[str], gen) -> None:
        if not force and is_fresh(out, sources):
            print(os.path.abspath(out))
            print('cached (up to date) — use --force to regenerate')
            return
        _print_result(*gen())

    if mode == 'technique':
        out = report_path(files[0], 'technique')
        _emit(out, [files[0]],
              lambda: report_technique.generate(load_lap(files[0]), out, lang, include_prompt, game))

    elif mode == 'setup':
        out = report_path(files[0], 'setup')
        _emit(out, [files[0]],
              lambda: report_setup.generate(load_lap(files[0]), out, lang, include_prompt, game))

    elif mode == 'compare':
        stem_b = os.path.splitext(os.path.basename(files[1]))[0]
        out = report_path(files[0], 'compare', stem_b)
        _emit(out, files,
              lambda: report_compare.generate([load_lap(f) for f in files], out, lang, include_prompt, game))

    elif mode in ('race', 'profile'):
        race_dir = os.path.abspath(files[0])
        csv_paths = sorted(
            os.path.join(race_dir, f) for f in os.listdir(race_dir) if f.lower().endswith('.csv')
        )
        if not csv_paths:
            print(f'Error: no CSV files found in {race_dir}', file=sys.stderr)
            sys.exit(2)
        dirname = os.path.basename(race_dir.rstrip('/\\'))
        suffix = '_race.md' if mode == 'race' else '_profile.md'
        out = os.path.join(race_dir, 'reports', dirname + suffix)
        if mode == 'race':
            _emit(out, csv_paths,
                  lambda: report_race.generate([load_lap(p) for p in csv_paths], out, lang, include_prompt, game))
        else:
            _emit(out, csv_paths,
                  lambda: report_profile.generate([load_lap(p) for p in csv_paths], out, lang, include_prompt))


if __name__ == '__main__':
    main()
