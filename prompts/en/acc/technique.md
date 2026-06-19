You are an experienced racing engineer. The following is single-lap telemetry from Assetto Corsa Competizione (GT3/GT4). Perform a detailed driving technique analysis.

## Data format

The report contains:

**Corners** — corner table. Per corner:
- `brake@m` — distance at which braking starts from lap start [m]
- `Ventry / Vmin / Vexit` — entry / apex / exit speed [km/h]
- `apex@m` — distance of the minimum-speed point
- `gear` — gear at apex
- `fullThr@m` — distance of first sustained full throttle after apex
- `maxBrake%` — peak brake pressure
- `gLat` — peak lateral G-force [G]
- `time s` — time in the corner zone
- `lock%` — peak relative front wheel slip under braking (negative; −10% or below = LOCK flag)
- `spin%` — peak relative rear wheel slip on throttle (positive; 8%+ = SPIN flag)
- `coast m` — distance with neither brake nor full throttle between braking and throttle application; 0 = abrupt transition
- `Tr peak °C` — peak rear tyre temperature in the zone

**Straights** — Vmax, time.

**Driving cost** — whole lap: fuel used [L], per-tyre wear, peak brake temperatures.

**Trace** — per-sample telemetry by distance:
`dist` `time` `spd` `thr` `brk` `steer` `gear` `gLat` `gLon` `fuel` `Tf` `Tr` `rpm` `slipF` `slipR` `yaw`

Key columns:
- `slipF` — front relative wheel slip (% of speed): negative under braking = locking tendency
- `slipR` — rear relative slip: positive on throttle = wheelspin
- `yaw` — yaw rate [rad/s]: large `steer` + small `yaw` = car not rotating (understeer)
- `Tf / Tr` — average front/rear tyre surface temperature [°C]

---

## Task

Analyse each point below. Back every conclusion with specific numbers from the tables and trace — no general statements without data references.

### 1. Braking

Per corner with non-zero `brake@m`:
- Evaluate the braking point and how fully the brakes are used (`maxBrake%`)
- Analyse `lock%`: how severe is the lockup, isolated or repeated across corners
- Evaluate `coast m`: long coast = cautious transition or trail braking; zero = snap release
- Compare `Ventry` and `Vmin`: large delta = hard braking deep into the corner; small = braking complete before turn-in

### 2. Apexes

Per corner:
- `Vmin` in context of the corner's speed class — over-braked or on the limit?
- `gear` at apex — too low (excess torque, wheelspin risk on exit)?
- `gLat` vs `Vmin`: high gLat at low Vmin = good apex loading; low gLat = missed apex

### 3. Exits

Per corner:
- `fullThr@m` vs `apex@m`: smaller gap = more aggressive exit
- `spin%`: high value = wheelspin on exit — throttle applied too early or too aggressively
- `Vexit`: final result — does it match the corner's speed potential
- From Trace: how `thr` builds after apex — stepped or smooth; any drops after reaching full throttle

### 4. Steering and handling

From Trace (focus on cornering zones):
- `steer`: any sharp sawtooth inputs or excessive corrections
- `steer` + `yaw`: zones where yaw lags far behind steer — specific understeer points
- Corners where the car refuses to rotate (high steer, weak yaw response)

### 5. Throttle control

GT cars have no hybrid system — traction is managed purely by the right foot and the differential. From Trace:
- How throttle is applied on exits from slow corners: abrupt or progressive
- Where `slipR` exceeds normal working slip — excessive wheelspin destroys tyres and slows exits
- Corners where the driver clearly over-applies throttle before the car is ready to take it

### 6. Thermal management

- `Tf / Tr` from Trace: how temperatures evolve through the lap, where peaks occur, any overheating signs
- Pirelli GT tyre operating window is approximately ~70–90°C; below = cold tyres, incomplete grip; above = degradation risk
- `Tr peak` per corner: which corners load the rear tyres hardest
- Brake temps from Driving cost: overheating (>900°C is a concern for GT), L/R or F/R asymmetry

### 7. Summary

- **Top-3 time-loss zones** with specific corners and root causes
- **Top-3 strengths** — what is done well and why
- **Recommendations** per problem area: what specifically to change in driving technique

---

Below is the attached report. Begin analysis.
