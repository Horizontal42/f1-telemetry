import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk

from .parser import load_lap
from .report_common import game_of, report_path
from . import report_technique, report_setup, report_compare, report_race, report_profile
from .rename import rename_unprocessed

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
_RACES_DIR = os.path.join(_PROJECT_ROOT, 'races')

# Maps tab id → display name used in mismatch warnings.
_TAB_GAME = {'f1': 'F1 22', 'acc': 'ACC'}


class _TabState:
    """All mutable state that belongs to one tab."""
    def __init__(self) -> None:
        self.mode = tk.StringVar(value='technique')
        self.lang = tk.StringVar(value='ru')
        self.include_prompt = tk.BooleanVar(value=True)
        self.path_var = tk.StringVar()
        self.selection: list[str] = []
        self.last_dir: dict[str, str] = {}
        self.log_queue: queue.Queue[str | None] = queue.Queue()
        self.busy = False
        # widgets set by _build_panel
        self.log_widget: scrolledtext.ScrolledText | None = None
        self.btn_generate: ttk.Button | None = None
        self.btn_rename: ttk.Button | None = None


class _App:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        root.title('Telemetry Analyzer (F1 22 / ACC)')
        root.resizable(True, True)

        self._tabs: dict[str, _TabState] = {
            'f1': _TabState(),
            'acc': _TabState(),
        }

        self._build_ui()
        self._poll_all_logs()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        nb = ttk.Notebook(self._root)
        nb.pack(fill='both', expand=True, padx=6, pady=6)

        for tab_id, label in [('f1', 'F1 22'), ('acc', 'ACC')]:
            frame = ttk.Frame(nb)
            nb.add(frame, text=label)
            self._build_panel(frame, tab_id)

    def _build_panel(self, parent: ttk.Frame, tab_id: str) -> None:
        st = self._tabs[tab_id]
        pad = {'padx': 8, 'pady': 4}

        mode_frame = ttk.LabelFrame(parent, text='Mode')
        mode_frame.pack(fill='x', **pad)
        for label, value in [('Technique', 'technique'), ('Setup', 'setup'),
                              ('Compare', 'compare'), ('Race', 'race'),
                              ('Profile', 'profile')]:
            ttk.Radiobutton(mode_frame, text=label, variable=st.mode,
                            value=value).pack(side='left', padx=6, pady=4)

        lang_frame = ttk.LabelFrame(parent, text='Prompt language / Язык промпта')
        lang_frame.pack(fill='x', **pad)
        ttk.Radiobutton(lang_frame, text='RU', variable=st.lang,
                        value='ru').pack(side='left', padx=6, pady=4)
        ttk.Radiobutton(lang_frame, text='EN', variable=st.lang,
                        value='en').pack(side='left', padx=6, pady=4)
        ttk.Checkbutton(lang_frame, text='Включить промпт в отчёт / Include prompt',
                        variable=st.include_prompt).pack(side='left', padx=16, pady=4)

        input_frame = ttk.LabelFrame(parent, text='Input')
        input_frame.pack(fill='x', **pad)
        ttk.Entry(input_frame, textvariable=st.path_var,
                  state='readonly', width=60).pack(side='left', fill='x',
                                                   expand=True, padx=(6, 2), pady=4)
        ttk.Button(input_frame, text='Browse…',
                   command=lambda: self._browse(tab_id)).pack(side='left', padx=(2, 6), pady=4)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', **pad)
        st.btn_generate = ttk.Button(btn_frame, text='Generate report',
                                     command=lambda: self._on_generate(tab_id))
        st.btn_generate.pack(side='left', padx=(0, 4))
        st.btn_rename = ttk.Button(btn_frame, text='Rename unprocessed (add lap #)',
                                   command=lambda: self._on_rename(tab_id))
        st.btn_rename.pack(side='left', padx=4)
        ttk.Button(btn_frame, text='Open races folder',
                   command=self._open_reports).pack(side='left', padx=4)

        log_frame = ttk.LabelFrame(parent, text='Log')
        log_frame.pack(fill='both', expand=True, **pad)
        st.log_widget = scrolledtext.ScrolledText(log_frame, state='disabled',
                                                  wrap='word', height=16)
        st.log_widget.pack(fill='both', expand=True, padx=4, pady=4)

    # ── Browse ───────────────────────────────────────────────────────────────

    def _browse(self, tab_id: str) -> None:
        st = self._tabs[tab_id]
        mode = st.mode.get()
        init = st.last_dir.get(mode, _RACES_DIR)

        if mode in ('race', 'profile'):
            d = filedialog.askdirectory(title='Select race folder', initialdir=init)
            if d:
                st.selection = [d]
                st.path_var.set(d)
                st.last_dir[mode] = d
        elif mode == 'compare':
            files = filedialog.askopenfilenames(
                title='Select 2+ CSV files', initialdir=init,
                filetypes=[('CSV', '*.csv')])
            if files:
                st.selection = list(files)
                st.path_var.set('  |  '.join(os.path.basename(f) for f in files))
                st.last_dir[mode] = os.path.dirname(files[0])
        else:
            f = filedialog.askopenfilename(
                title='Select CSV file', initialdir=init,
                filetypes=[('CSV', '*.csv')])
            if f:
                st.selection = [f]
                st.path_var.set(f)
                st.last_dir[mode] = os.path.dirname(f)

    # ── Validation / busy state / logging ────────────────────────────────────

    def _validate_selection(self, tab_id: str) -> str | None:
        st = self._tabs[tab_id]
        mode = st.mode.get()
        sel = st.selection
        if not sel:
            return 'No file selected'
        if mode in ('technique', 'setup') and len(sel) != 1:
            return f'{mode} requires exactly 1 file'
        if mode == 'compare' and len(sel) < 2:
            return 'compare requires 2+ files'
        if mode in ('race', 'profile') and (len(sel) != 1 or not os.path.isdir(sel[0])):
            return f'{mode} requires a directory'
        return None

    def _set_busy(self, tab_id: str, busy: bool) -> None:
        st = self._tabs[tab_id]
        st.busy = busy
        state = 'disabled' if busy else 'normal'
        st.btn_generate.configure(state=state)
        st.btn_rename.configure(state=state)

    def _log_append(self, tab_id: str, text: str) -> None:
        w = self._tabs[tab_id].log_widget
        w.configure(state='normal')
        w.insert('end', text + '\n')
        w.see('end')
        w.configure(state='disabled')

    def _push(self, tab_id: str, msg: str) -> None:
        self._tabs[tab_id].log_queue.put(msg)

    def _poll_all_logs(self) -> None:
        for tab_id, st in self._tabs.items():
            while True:
                try:
                    msg = st.log_queue.get_nowait()
                except queue.Empty:
                    break
                if msg is None:
                    self._set_busy(tab_id, False)
                else:
                    self._log_append(tab_id, msg)
        self._root.after(100, self._poll_all_logs)

    # ── Generate ─────────────────────────────────────────────────────────────

    def _on_generate(self, tab_id: str) -> None:
        err = self._validate_selection(tab_id)
        if err:
            self._log_append(tab_id, f'✗ {err}')
            return
        st = self._tabs[tab_id]
        mode = st.mode.get()
        sel = list(st.selection)
        lang = st.lang.get()
        inc = st.include_prompt.get()
        self._set_busy(tab_id, True)
        threading.Thread(target=self._worker_generate,
                         args=(tab_id, mode, sel, lang, inc),
                         daemon=True).start()

    def _worker_generate(self, tab_id: str, mode: str, sel: list[str],
                         lang: str, inc: bool) -> None:
        try:
            self._check_game_mismatch(tab_id, mode, sel)

            if mode == 'technique':
                lap = load_lap(sel[0])
                out = report_path(sel[0], 'technique')
                abs_path, tokens = report_technique.generate(lap, out, lang, inc)
                self._push(tab_id, f'✓ {abs_path}  (~{tokens} tokens)')

            elif mode == 'setup':
                lap = load_lap(sel[0])
                out = report_path(sel[0], 'setup')
                abs_path, tokens = report_setup.generate(lap, out, lang, inc)
                self._push(tab_id, f'✓ {abs_path}  (~{tokens} tokens)')

            elif mode == 'compare':
                laps = [load_lap(f) for f in sel]
                stem_b = os.path.splitext(os.path.basename(sel[1]))[0]
                out = report_path(sel[0], 'compare', stem_b)
                abs_path, tokens = report_compare.generate(laps, out, lang, inc)
                self._push(tab_id, f'✓ {abs_path}  (~{tokens} tokens)')

            elif mode in ('race', 'profile'):
                race_dir = os.path.abspath(sel[0])
                csv_files = sorted(
                    f for f in os.listdir(race_dir) if f.lower().endswith('.csv')
                )
                if not csv_files:
                    self._push(tab_id, f'✗ No CSV files found in {race_dir}')
                    return
                laps = [load_lap(os.path.join(race_dir, f)) for f in csv_files]
                dirname = os.path.basename(race_dir.rstrip('/\\'))
                suffix = '_race.md' if mode == 'race' else '_profile.md'
                out = os.path.join(race_dir, 'reports', dirname + suffix)
                gen_mod = report_race if mode == 'race' else report_profile
                abs_path, tokens = gen_mod.generate(laps, out, lang, inc)
                self._push(tab_id, f'✓ {abs_path}  (~{tokens} tokens)')

        except Exception as e:
            self._push(tab_id, f'✗ {e}')
        finally:
            self._tabs[tab_id].log_queue.put(None)

    def _check_game_mismatch(self, tab_id: str, mode: str, sel: list[str]) -> None:
        """Warn (but don't block) when the file's game doesn't match the active tab."""
        try:
            if mode in ('race', 'profile'):
                race_dir = os.path.abspath(sel[0])
                csv_files = sorted(
                    f for f in os.listdir(race_dir) if f.lower().endswith('.csv')
                )
                if not csv_files:
                    return
                probe = os.path.join(race_dir, csv_files[0])
            else:
                probe = sel[0]
            detected = game_of(load_lap(probe))
        except Exception:
            return  # if probe fails, let the main worker surface the real error

        tab_game = tab_id  # 'f1' or 'acc'
        if detected != tab_game:
            tab_label = _TAB_GAME[tab_id]
            file_label = _TAB_GAME.get(detected, detected.upper())
            self._push(tab_id,
                       f'⚠ Selected file is {file_label}, but you are on the '
                       f'{tab_label} tab — proceeding anyway.')

    # ── Rename ───────────────────────────────────────────────────────────────

    def _on_rename(self, tab_id: str) -> None:
        st = self._tabs[tab_id]
        init = st.last_dir.get('rename', os.path.expanduser('~'))
        d = filedialog.askdirectory(title='Select folder with CSV files', initialdir=init)
        if not d:
            return
        st.last_dir['rename'] = d
        self._set_busy(tab_id, True)
        threading.Thread(target=self._worker_rename, args=(tab_id, d),
                         daemon=True).start()

    def _worker_rename(self, tab_id: str, d: str) -> None:
        try:
            results = rename_unprocessed([d], races_dir=_RACES_DIR)
            if not results:
                self._push(tab_id, 'No CSV files found')
            for r in results:
                if r.status == 'renamed':
                    new_display = (os.path.relpath(r.new, _RACES_DIR)
                                   if r.new and r.new.startswith(_RACES_DIR) else r.new)
                    self._push(tab_id, f'renamed: {r.old} -> {new_display}')
                elif r.status == 'skipped':
                    self._push(tab_id, f'skipped: {r.old} ({r.detail})')
                else:
                    self._push(tab_id, f'error: {r.old} ({r.detail})')
        except Exception as e:
            self._push(tab_id, f'✗ {e}')
        finally:
            self._tabs[tab_id].log_queue.put(None)

    # ── Misc ─────────────────────────────────────────────────────────────────

    def _open_reports(self) -> None:
        target = _RACES_DIR if os.path.isdir(_RACES_DIR) else _PROJECT_ROOT
        os.startfile(target)


def main() -> None:
    root = tk.Tk()
    _App(root)
    root.mainloop()
