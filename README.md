[Русский](README.ru.md)

# F1 Telemetry Analyzer

Turns raw F1 22 lap telemetry into compact Markdown reports you can paste into an LLM for analysis. A full raw lap is ~1M tokens; these reports are 1–35k.

```bash
# from the tool/ folder
python -m telemetry technique "races/Zandvoort/Practice/zandvoort_P1_L7_74.074_ferrari.csv"
# -> races/Zandvoort/Practice/reports/zandvoort_P1_L7_74.074_ferrari_technique.md   (~35k tokens)
```

Or just double-click `run-gui.bat` and click **Generate report**.

## Install

- Python 3.10+ (uses only the standard library — no `pip install`).
- Tk is required for the GUI; it ships with the standard Python installer on Windows/macOS. The CLI works without it.

Download or clone the repository. Keep your telemetry CSVs in the parent folder of `tool/` (see [folder layout](#folder-layout)).

## What it does

Five modes. Four produce reports, one renames files.

| Mode | Input | Use it to analyse |
|------|-------|-------------------|
| `technique` | one lap | **how** you drive — braking points, apex speeds, throttle application, lockups, resource cost |
| `setup` | one lap | **what** is set — balance (US/OS), tyre temps, brakes, suspension rake & roll |
| `compare` | two+ laps | **where** one lap is faster — per-corner and cumulative delta |
| `race` | a folder of laps | the whole race — pace, stint degradation, tyre wear, ERS per lap |
| `rename` | files/folder | insert session type and lap number into each filename (`..._74.074_...` → `..._P1_L7_74.074_...`) |

Reports include a legend explaining every column and have the analysis prompt auto-appended at the end — just drop the file into an LLM. Prompts come in RU and EN; pick with `--lang en` on the CLI or the language radio in the GUI.

### Folder layout

```
Telemetry/
  races/
    Zandvoort/
      Practice/                        <- CSVs go here after renaming
        zandvoort_P1_L7_74.074_ferrari.csv
        reports/                       <- technique/setup/compare reports land here
      Qualifying/
        zandvoort_Q1_L3_74.897_ferrari.csv
        reports/
      Race/
        zandvoort_R_L7_74.152_ferrari.csv
        reports/
          Race_race.md                 <- race mode report
  tool/                                <- this repository
    telemetry/
    prompts/
    run-gui.bat
```

## Handy things

**GUI** — double-click `run-gui.bat` (or `run-gui.pyw` for no console window, or run `python -m telemetry gui`). Pick a mode and language (RU/EN), browse to the file/folder, click Generate. The file browser remembers the last used directory per mode. The **Rename unprocessed** button adds the session type and lap number to files that don't have them yet and leaves the rest alone.

**CLI** — from the `tool/` folder:

```bash
python -m telemetry technique races/Zandvoort/Practice/lap.csv
python -m telemetry setup     races/Zandvoort/Practice/lap.csv
python -m telemetry compare   races/Zandvoort/Practice/lap_a.csv races/Zandvoort/Practice/lap_b.csv
python -m telemetry race      races/Zandvoort/Race
python -m telemetry rename    races/Zandvoort/Practice   # or individual files

# choose prompt language (default: ru)
python -m telemetry technique races/Zandvoort/Practice/lap.csv --lang en
```

Every report run prints the output path and a token estimate:

```
C:\...\Telemetry\reports\lap_technique.md
~33834 tokens (budget 60k)
```

**Rename only touches unprocessed files.** A file is "processed" once its name contains both a session token (`P1`, `Q2`, `R`, …) and an `L<number>` token. Re-running rename on the same folder is safe.

## Input format

F1 22 UDP telemetry exported to CSV (tested with [F1Laps](https://www.f1laps.com)). UTF-8, ~1800 rows per lap (≈29 Hz), 108 channels. One file = one lap. For `race` mode, drop all of a race's lap files into one folder.

## For developers

Pure-stdlib Python. Pipeline: `parser` → `segments` (+ `corner_metrics`) → `resample` → `report_*`. See [ARCHITECTURE.md](ARCHITECTURE.md).

```bash
cd tool
python -m pytest -q        # run the test suite
python -m telemetry gui    # launch the GUI
```

Adding a mode: drop a `telemetry/report_<mode>.py` exposing `generate(...) -> (abs_path, tokens)` and wire one line into `telemetry/__main__.py`. The parser, corner detection, adaptive trace, and shared report blocks are reused.

## Credits

Built for analysing personal F1 22 hotlaps. Telemetry export format from [F1Laps](https://www.f1laps.com).

## License

MIT — see [LICENSE](LICENSE).
