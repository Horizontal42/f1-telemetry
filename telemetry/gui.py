import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk

from .parser import load_lap
from .report_common import report_path
from . import report_technique, report_setup, report_compare, report_race
from .rename import rename_unprocessed

# project root = parent of the tool\ dir
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
_RACES_DIR = os.path.join(_PROJECT_ROOT, 'races')


def _race_output_path(race_dir: str) -> str:
    dirname = os.path.basename(race_dir.rstrip('/\\'))
    return os.path.join(race_dir, 'reports', dirname + '_race.md')


class _App:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        root.title('F1 Telemetry Analyzer')
        root.resizable(True, True)

        self._mode = tk.StringVar(value='technique')
        self._lang = tk.StringVar(value='ru')
        self._selection: list[str] = []
        self._last_dir: dict[str, str] = {}
        self._log_queue: queue.Queue[str | None] = queue.Queue()
        self._busy = False

        self._build_ui()
        self._poll_log()

    def _build_ui(self) -> None:
        pad = {'padx': 8, 'pady': 4}

        mode_frame = ttk.LabelFrame(self._root, text='Mode')
        mode_frame.pack(fill='x', **pad)
        for label, value in [('Technique', 'technique'), ('Setup', 'setup'),
                              ('Compare', 'compare'), ('Race', 'race')]:
            ttk.Radiobutton(mode_frame, text=label, variable=self._mode,
                            value=value).pack(side='left', padx=6, pady=4)

        lang_frame = ttk.LabelFrame(self._root, text='Prompt language / Язык промпта')
        lang_frame.pack(fill='x', **pad)
        ttk.Radiobutton(lang_frame, text='RU', variable=self._lang,
                        value='ru').pack(side='left', padx=6, pady=4)
        ttk.Radiobutton(lang_frame, text='EN', variable=self._lang,
                        value='en').pack(side='left', padx=6, pady=4)

        input_frame = ttk.LabelFrame(self._root, text='Input')
        input_frame.pack(fill='x', **pad)
        self._path_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self._path_var,
                  state='readonly', width=60).pack(side='left', fill='x',
                                                   expand=True, padx=(6, 2), pady=4)
        ttk.Button(input_frame, text='Browse…',
                   command=self._browse).pack(side='left', padx=(2, 6), pady=4)

        btn_frame = ttk.Frame(self._root)
        btn_frame.pack(fill='x', **pad)
        self._btn_generate = ttk.Button(btn_frame, text='Generate report',
                                        command=self._on_generate)
        self._btn_generate.pack(side='left', padx=(0, 4))
        self._btn_rename = ttk.Button(btn_frame, text='Rename unprocessed (add lap #)',
                                      command=self._on_rename)
        self._btn_rename.pack(side='left', padx=4)
        ttk.Button(btn_frame, text='Open races folder',
                   command=self._open_reports).pack(side='left', padx=4)

        log_frame = ttk.LabelFrame(self._root, text='Log')
        log_frame.pack(fill='both', expand=True, **pad)
        self._log = scrolledtext.ScrolledText(log_frame, state='disabled',
                                              wrap='word', height=16)
        self._log.pack(fill='both', expand=True, padx=4, pady=4)

    def _browse(self) -> None:
        mode = self._mode.get()
        init = self._last_dir.get(mode, _RACES_DIR)
        if mode == 'race':
            d = filedialog.askdirectory(title='Select race folder', initialdir=init)
            if d:
                self._selection = [d]
                self._path_var.set(d)
                self._last_dir[mode] = d
        elif mode == 'compare':
            files = filedialog.askopenfilenames(
                title='Select 2+ CSV files', initialdir=init,
                filetypes=[('CSV', '*.csv')])
            if files:
                self._selection = list(files)
                self._path_var.set('  |  '.join(os.path.basename(f) for f in files))
                self._last_dir[mode] = os.path.dirname(files[0])
        else:
            f = filedialog.askopenfilename(
                title='Select CSV file', initialdir=init,
                filetypes=[('CSV', '*.csv')])
            if f:
                self._selection = [f]
                self._path_var.set(f)
                self._last_dir[mode] = os.path.dirname(f)

    def _validate_selection(self) -> str | None:
        mode = self._mode.get()
        sel = self._selection
        if not sel:
            return 'No file selected'
        if mode in ('technique', 'setup') and len(sel) != 1:
            return f'{mode} requires exactly 1 file'
        if mode == 'compare' and len(sel) < 2:
            return 'compare requires 2+ files'
        if mode == 'race' and (len(sel) != 1 or not os.path.isdir(sel[0])):
            return 'race requires a directory'
        return None

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = 'disabled' if busy else 'normal'
        self._btn_generate.configure(state=state)
        self._btn_rename.configure(state=state)

    def _log_append(self, text: str) -> None:
        self._log.configure(state='normal')
        self._log.insert('end', text + '\n')
        self._log.see('end')
        self._log.configure(state='disabled')

    def _poll_log(self) -> None:
        while True:
            try:
                msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if msg is None:
                self._set_busy(False)
            else:
                self._log_append(msg)
        self._root.after(100, self._poll_log)

    def _push(self, msg: str) -> None:
        self._log_queue.put(msg)

    def _on_generate(self) -> None:
        err = self._validate_selection()
        if err:
            self._log_append(f'✗ {err}')
            return
        mode = self._mode.get()
        sel = list(self._selection)
        lang = self._lang.get()
        self._set_busy(True)
        threading.Thread(target=self._worker_generate, args=(mode, sel, lang),
                         daemon=True).start()

    def _worker_generate(self, mode: str, sel: list[str], lang: str) -> None:
        try:
            if mode == 'technique':
                lap = load_lap(sel[0])
                out = report_path(sel[0], 'technique')
                abs_path, tokens = report_technique.generate(lap, out, lang)
                self._push(f'✓ {abs_path}  (~{tokens} tokens)')

            elif mode == 'setup':
                lap = load_lap(sel[0])
                out = report_path(sel[0], 'setup')
                abs_path, tokens = report_setup.generate(lap, out, lang)
                self._push(f'✓ {abs_path}  (~{tokens} tokens)')

            elif mode == 'compare':
                laps = [load_lap(f) for f in sel]
                stem_b = os.path.splitext(os.path.basename(sel[1]))[0]
                out = report_path(sel[0], 'compare', stem_b)
                abs_path, tokens = report_compare.generate(laps, out, lang)
                self._push(f'✓ {abs_path}  (~{tokens} tokens)')

            elif mode == 'race':
                race_dir = os.path.abspath(sel[0])
                csv_files = sorted(
                    f for f in os.listdir(race_dir) if f.lower().endswith('.csv')
                )
                if not csv_files:
                    self._push(f'✗ No CSV files found in {race_dir}')
                    return
                laps = [load_lap(os.path.join(race_dir, f)) for f in csv_files]
                out = _race_output_path(race_dir)
                abs_path, tokens = report_race.generate(laps, out, lang)
                self._push(f'✓ {abs_path}  (~{tokens} tokens)')

        except Exception as e:
            self._push(f'✗ {e}')
        finally:
            self._log_queue.put(None)

    def _on_rename(self) -> None:
        init = self._last_dir.get('rename', os.path.expanduser('~'))
        d = filedialog.askdirectory(title='Select folder with CSV files', initialdir=init)
        if not d:
            return
        self._last_dir['rename'] = d
        self._set_busy(True)
        threading.Thread(target=self._worker_rename, args=(d,), daemon=True).start()

    def _worker_rename(self, d: str) -> None:
        try:
            results = rename_unprocessed([d], races_dir=_RACES_DIR)
            if not results:
                self._push('No CSV files found')
            for r in results:
                if r.status == 'renamed':
                    new_display = os.path.relpath(r.new, _RACES_DIR) if r.new and r.new.startswith(_RACES_DIR) else r.new
                    self._push(f'renamed: {r.old} -> {new_display}')
                elif r.status == 'skipped':
                    self._push(f'skipped: {r.old} ({r.detail})')
                else:
                    self._push(f'error: {r.old} ({r.detail})')
        except Exception as e:
            self._push(f'✗ {e}')
        finally:
            self._log_queue.put(None)

    def _open_reports(self) -> None:
        target = _RACES_DIR if os.path.isdir(_RACES_DIR) else _PROJECT_ROOT
        os.startfile(target)


def main() -> None:
    root = tk.Tk()
    _App(root)
    root.mainloop()
