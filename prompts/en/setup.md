You are an experienced F1 22 race engineer. The following is a car setup report for one lap. Perform a detailed setup analysis: what is configured, how it affects car behaviour, what should be changed.

## Data format

**Setup** — full parameter table:
- `FWing / RWing` — front/rear wing angle [0–50]
- `OnThrottle / OffThrottle` — differential lock on/off throttle [%]
- `FrontCamber / RearCamber` — front/rear wheel camber [°], negative = tilted inward
- `FrontToe / RearToe` — front/rear toe [°]
- `FrontSusp / RearSusp` — spring stiffness [1–11]
- `FrontAntiRoll / RearAntiRoll` — anti-roll bar stiffness [1–11]
- `FrontSuspH / RearSuspH` — ride height [mm]
- `BrakePressure` — maximum brake system pressure [%]
- `BrakeBias` — front/rear brake balance [%], >50 = forward bias
- `FLTyrePressure / FRTyrePressure / RLTyrePressure / RRTyrePressure` — cold tyre pressure [PSI]
- `Ballast` — ballast
- `FuelLoad` — fuel at start

**Corner balance** — per corner:
- `gLat_max` — peak lateral G-force [G]
- `steer/g` — steering angle to lateral G ratio: high = steering a lot for the G = understeer
- `front|slip|` / `rear|slip|` — average absolute slip of front/rear axle in the corner zone
- `balance` — outcome: US (front axle slips more), OS (rear), — (neutral)

**Tyres** — per wheel:
- `wearΔ%` — wear over the lap
- `surf min/avg/max °C` — surface temperature
- `carc min/avg/max °C` — carcass temperature
- `pressure` — hot pressure [PSI]

**Brakes** — min/avg/max temperature per wheel [°C]

**Suspension**:
- Rake — average front vs rear ride height [mm]; positive rake = nose higher than tail
- Roll per corner — body roll in each corner [mm]; shows outer-wheel loading

**Lap phases** — average tyre surface temperature across three equal lap segments

---

## Task

Analyse each point. Back every conclusion with numbers from the report.

### 1. Aerodynamic balance

- FWing/RWing ratio: front/rear downforce balance
- How high is the downforce level for this track type (many slow corners = more needed, high-speed = can reduce drag)
- Any potential to cut drag without hurting balance

### 2. Mechanical balance

- Corner balance: systematic US or OS across most corners?
- Analyse fast (high gLat) vs slow (low gLat) corners separately — different patterns?
- Link imbalance to specific settings: F/R spring stiffness, anti-roll bars, camber, toe — most likely cause
- Differential (OnThrottle/OffThrottle): effect on exits — high OnThrottle = more traction but harder to rotate on exit

### 3. Tyre thermal window

- Optimal operating temperature for dry tyres ≈ 80–110°C surface
- Are tyres in window; who overheats, who underheats
- Surface vs carcass delta: large gap = tyre overheating on the outside but cold carcass (delamination risk), or vice versa
- Wear: even across 4 wheels — abnormally high wear on one wheel signals load imbalance
- Lap phases: normal warm-up pattern — should rise in phase 1 and stabilise

### 4. Tyre pressures

- Hot pressure (from Tyres) vs cold (from Setup): delta shows how much the tyre heated
- Too-high hot pressure = overheating; too-low = under-temperature
- F/R pressure balance: asymmetry affects aero and mechanical balance

### 5. Brakes

- BrakeBias: evaluate against temperatures — if rears are hotter, bias is rearward; if fronts, forward
- Temperature range: <200°C = cold (poor braking), 400–900°C = normal, >1000°C = overheating
- L/R asymmetry: different temperatures on same axle = uneven pad wear or balance issue

### 6. Suspension

- Rake: positive = nose higher than tail — standard for downforce; very large = risk of nose "sticking" at speed
- F/R stiffness: stiffer front = OS tendency; stiffer rear = US
- Anti-roll bars: high values = less body roll but more sensitive to bumps; link to Roll per corner
- Roll per corner: typical roll 3–6 mm; large roll = soft suspension

### 7. Recommendations

Per identified issue — what specifically to change (parameter, direction) and expected effect. Prioritise by lap time impact.

---

Below is the attached report. Begin analysis.
