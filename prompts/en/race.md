You are a race engineer analysing full-race telemetry in F1 22. The report covers all laps: lap times, stints, tyre wear, thermals, and ERS. Perform a detailed race analysis.

## Data format

**Lap times** — per lap:
- `Lap` — lap number
- `Time` — lap time `M:SS.mmm`
- `S1 / S2 / S3` — sector times [s]
- `Tyre` — compound (C1–C5, I, W)
- `Age` — laps on this set (1 = first lap on fresh set)
- `Fuel kg` — fuel at lap start [kg]
- `Note` — flags: `FAST` = fastest valid lap, `PIT` = in-lap, `INV` = invalidated

**Stint summary** — per stint:
- `Stint` — stint number
- `Laps` — laps in stint
- `Tyre` — compound
- `Laps on tyre` — total laps on this set
- `Avg pace` — average pace (excluding pit laps and invalidated)
- `Best / Worst` — best and worst lap in stint
- `Deg s/lap` — degradation slope per tyre age lap (positive = slowing, negative = improving)

**Tyre wear per lap** — `FL / FR / RL / RR` — wear % at end of each lap

**Thermal summary per lap**:
- `Tf avg°C` — average peak front tyre temperature for the lap
- `Tr avg°C` — rear
- `Brk FL max°C` — peak front-left brake temperature
- `Brk RR max°C` — peak rear-right brake temperature

**ERS per lap**:
- `ERS MJ` — total energy from ERS over the lap (cumulative deployed at lap end)
- `MGU-K MJ` — MGU-K recovery
- `MGU-H MJ` — MGU-H recovery

---

## Task

Analyse each point. Back every conclusion with specific numbers from the tables.

### 1. Race overview

- How did pace evolve through the race: progression or degradation?
- Were there outliers (abnormally slow or fast laps) — name the lap numbers and reason (PIT, INV, safety car?)
- Compare best vs average pace: how large is the gap?
- One-sentence overall race assessment

### 2. Stint analysis

Per stint from `Stint summary`:
- Average pace and relative quality (best/worst stint?)
- `Best–Worst` spread: large spread = inconsistent pace, small = consistent
- Compare stints: where was the driver faster and why (tyre, fuel, track condition?)
- Was the pit stop timed well: not too early/late given degradation trend

### 3. Tyre degradation

From `Deg s/lap` and `Tyre wear`:
- Which stint has the most/least degradation?
- Compare `Deg s/lap` vs actual wear increment per lap — consistent?
- When did the tyre "die": identify the lap where pace dropped sharply
- Wear evenness: FL/FR or RL/RR asymmetry?

### 4. Fuel effect

- For the first (or long) stint: correlate `Fuel kg` and `Time` per lap
- How much does fuel effect explain early-stint pace improvement? (typical ≈ 0.03–0.05 s/kg)
- If early-stint pace is poor — tyre warm-up or fuel load?
- Were early-stint laps too slow relative to the fuel correction

### 5. Thermal management

From `Thermal summary`:
- How do tyre temps evolve through each stint: warm-up, stable, overheating?
- Signs of overheating (sharp `Tf` or `Tr` rise with simultaneous pace drop)?
- Brake temps: rising through the race distance or stable? FL vs RR asymmetry?
- Which laps had critical thermal conditions?

### 6. Best and worst laps

- `FAST` lap: which stint, what tyre age, what fuel load?
- Why did the best lap happen when it did — track rubber, late braking, cool air?
- Worst valid lap (not INV, not PIT): reason — degradation, traffic, driver error?
- Patterns: "out lap" always slow, "in lap" pace dip?

### 7. Summary and recommendations

- **What worked**: strategy and driving that was executed well
- **Main losses**: specific laps and zones where the most time was lost
- **Strategic recommendations**: pit timing, compound choice, stint length
- **Driving technique**: if degradation is abnormal — what to change in driving style

---

Below is the attached race report. Begin analysis.
