[Русский](ARCHITECTURE.ru.md)

# Architecture

A telemetry CSV becomes a Markdown report through a small linear pipeline. Everything is stdlib Python; there is no framework and no global state.

## Files

```
telemetry/
  __main__.py        CLI entry: arg parsing, mode dispatch, stdout. No args -> GUI.
  parser.py          CSV -> Lap (frozen dataclass: session, track, setup, ch, n).
  segments.py        Lap -> corners & straights. Zone detection + numbering.
  corner_metrics.py  Per-zone number crunching: braking point, lock/spin, coast, temps.
  resample.py        Adaptive distance grid + channel interpolation for the trace.
  report_common.py   Header block, legend strings, md_table, token_estimate, load_prompt, atomic write.
  report_technique.py  Driving report (corners, straights, cost, trace).
  report_setup.py    Car report (setup, balance, tyres, brakes, suspension, phases).
  report_compare.py  Two+ laps side by side, per-corner and cumulative delta.
  report_race.py     A folder of laps: lap times (with position), stints, wear, thermals, ERS. Dedups duplicate lap numbers.
  report_profile.py  A folder of laps: cheap cross-lap corner tendencies (median per corner, per dominant compound) + auto-picked deep-dive laps. No trace.
  rename.py          Insert session type + lap number (P1_L7) into filenames; with races_dir, sort into races/<track>/<session>/ and recurse subdirectories.
  gui.py             tkinter window; per-mode browse memory; runs generation/rename on a worker thread.
prompts/             LLM analysis prompts, ru/ and en/ subdirectories, one file per mode. Auto-appended to every report.
tests/               pytest suite + fixture laps.
```

## How a CSV becomes a report

1. **`__main__.main`** parses `<mode> <files…>`, validates arity (technique/setup = 1 file, compare = 2+, race = 1 dir), and dispatches.
2. **`parser.load_lap`** reads the file as UTF-8 and splits it into four meta blocks (session, track, setup) plus the 108-channel telemetry table. Channel names are normalised by stripping the ` [unit]` suffix. Every column that is entirely zero is dropped — the game writes many dead channels (see Gotchas).
3. **`segments.detect_corners`** walks the samples, marks each as "cornering" when `|Steer| > STEER_ON` or `Brake > BRAKE_ON`, merges adjacent zones closer than `MERGE_GAP_M`, drops zones shorter than `MIN_LEN_M`, and numbers what's left T1..Tn by distance. For each zone it calls **`corner_metrics.corner_from_zone`**, which extracts the braking point, apex, gear, full-throttle point, peak brake/gLat, relative lock%/spin%, coast distance, and rear tyre temperature peak. `straights` fills the gaps between corners.
4. **`resample.adaptive_points`** builds a distance grid that is dense inside (and on approach to) corners and sparse on straights — the step sizes default to the lap's own median sample spacing via `auto_steps`, so denser raw telemetry yields a denser trace. **`sample_at`** interpolates each channel onto that grid (nearest-sample for discrete channels like Gear/DRS).
5. The **`report_<mode>.generate(…, lang, include_prompt=True)`** function assembles Markdown from `report_common` helpers (`header_block`, `md_table`, `legend`) and the data above. When `include_prompt` is set it calls **`load_prompt(mode, lang)`** to read the matching prompt from `prompts/<lang>/<mode>.md` and appends it after a `---` separator (CLI `--no-prompt` / GUI checkbox turn this off). Finally **`write_report`** writes atomically (temp file + `os.replace`) and returns `(abs_path, tokens)`. Before generating, `__main__` skips the run via **`is_fresh(report, sources)`** when an up-to-date report exists (override with `--force`).
6. **`__main__`** prints that path and `~N tokens (budget 60k)`. The **GUI** shows the same tuple in its log instead of printing.

## Adding things

**A new report mode.** Create `telemetry/report_x.py` with `generate(lap, out_path) -> tuple[str, int]` (or `generate(laps, out_path)` for multi-lap). Build the text from `report_common` helpers and end with `return write_report(out_path, text)`. In `__main__.py` add `'x'` to the mode choices and a dispatch branch that computes the output path (`report_path(input, 'x')`) and calls your `generate`. Add the mode to the GUI's radio list and `_worker_generate` if you want it in the UI.

**A new trace channel.** Sample it in the report's trace builder via `sample_at(lap, 'ChannelName', dists)`, add it to the trace header and `resample.format_trace_row`, and add a `LEGEND_*` string in `report_common.py` so the column is documented.

**A new corner metric.** Add a field to the `Corner` dataclass in `segments.py` and compute it in `corner_metrics.corner_from_zone`. Because `Corner` is frozen, set it through the constructor.

## Assumptions & tunables

Two kinds of constants. **Detection** thresholds are in telemetry units and uniform across F1 22 — they decide *where* a boundary is, not the conclusion, so they are not track-tuned. **Interpretation** constants encode racing judgment that genuinely varies; reports always print the raw number next to any flag/verdict, so a debatable threshold never hides the data.

| Constant | File | Kind | Basis / sensitivity |
|----------|------|------|---------------------|
| `STEER_ON 6`, `BRAKE_ON 5`, `BRAKE_MARK 20`, `FULL_THROTTLE 98` | `segments` / `corner_metrics` | detection | percent of input range, game-uniform |
| `MERGE_GAP_M 40` + `merge_gap_for` (clamp 28–60) | `segments` | detection | **adaptive**: scales with `Tracklen` around the Zandvoort anchor so chicanes/long circuits self-tune |
| `MIN_LEN_M 15`, `_SAFE_SPEED_FLOOR 30`, `0.3 s` throttle window | `segments` / `corner_metrics` | detection | geometry / divide guard / debounce |
| `resample` dense=median, sparse=8×median | `resample` | detection | self-tunes to sample rate |
| `LOCKUP −10 %`, `SPIN +8 %` | `segments` | interpretation | severe-only flags; raw `lock%`/`spin%` always shown |
| `FUEL 0.03–0.05 s/kg` | `report_compare` | interpretation | track-varying; emitted as a **range** with the rate printed |
| `diff ±0.5` US/OS | `report_setup` | interpretation | relative to the lap's slip baseline; raw front/rear slip shown |
| profile `*_REL` multipliers + `*_FLOOR` / `TR` margins | `report_profile` | interpretation | multipliers are **relative to the session median**; floors are noise gates; medians shown in the table |

If a future track needs a different corner grouping, `merge_gap_for` already adapts by length; only a genuinely unusual layout would want a manual nudge there.

## Gotchas

**Files are UTF-8, the OS default here is cp1251.** `parser.load_lap` always passes `encoding='utf-8'`; opening a telemetry file with the default codec raises `UnicodeDecodeError` on the first non-ASCII byte. `rename.read_lap_number` reads only the first five lines but must use the same encoding.

**Many channels are all-zero in this game version** — `Torque`, `IcePower`, ride heights, suspension loads, the per-section tyre temps, `Clutch`, `Handbrake`, and more. The parser drops any column that is entirely zero, so downstream code must treat a missing channel as "not recorded", not "error".

**`WheelSlip*` is a km/h speed difference, not a ratio.** A front value of −4.5 under braking is normal. Lock/spin are therefore computed as *relative* slip (`slip / max(speed, 30) * 100`) with thresholds at −10 % / +8 %; raw slip values are not comparable across speeds, and front-vs-rear baselines differ.

**`Steer` is a percent (−100..100), not a fraction.** Small values on a straight are still percent.

**The setup row has a trailing comma** (an empty `FuelLoad` tail field in some exports). The parser drops trailing empties so the setup dict has no blank-string key.

**Rename with `races_dir` sorts into folders and walks subdirectories.** `rename_unprocessed(targets, races_dir)` when `races_dir` is set: (1) recursively scans all subdirectories via `os.walk`, (2) reads metadata from each CSV (`read_metadata` → lap, event, track), (3) inserts tokens if absent, (4) creates `races/<track_safe>/Practice|Qualifying|Race|Sprint/` and moves the file there, (5) even already-renamed files are moved if they're in the wrong folder, (6) only skips files that are already in the right place with the right name. Without `races_dir` it works as before — renames in-place in the original folder.

**Reports go next to the input, not next to the program.** `report_path` derives the `reports/` directory from the *input CSV's* folder. `race` mode puts the report inside the race session folder (`<race_dir>/reports/`). Moving the tool does not move where reports land.
