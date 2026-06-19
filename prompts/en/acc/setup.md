You are an experienced race engineer. The following is a telemetry report for one lap in Assetto Corsa Competizione (GT3/GT4). Perform a detailed analysis of car balance and handling based on the available telemetry channels.

## Important note

ACC does not export car setup parameters to telemetry — the in-game setup table is all zeros and is omitted from the report. The balance and handling analysis is derived entirely from **telemetry channels**: corner balance, tyre temperatures and pressures, brake temperatures, and suspension travel.

## Data format

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

### 1. Mechanical balance

- Corner balance: systematic US or OS across most corners?
- Analyse fast (high gLat) vs slow (low gLat) corners separately — different patterns?
- High `steer/g` = car demands more steering for the load level = understeer tendency; low `steer/g` with high rear slip = oversteer
- GT cars are sensitive to front/rear spring and anti-roll bar balance: abnormal Roll per corner may indicate a soft spring or weak anti-roll bar on one axle

### 2. Differential and traction

- From `spin%` in the corner table: high rear slip on exit indicates an aggressive on-throttle differential lock or premature throttle application
- If `spin%` is consistently high in slow corners but modest in fast corners — on-throttle differential setting is the likely cause
- Check whether rear slip is symmetric across left and right sides — asymmetry suggests a geometry or tyre pressure issue

### 3. Tyre thermal window

- Pirelli GT tyre operating window is approximately ~70–90°C surface; outside this range grip is compromised
- Are tyres in window; who overheats, who underheats
- Surface vs carcass delta: large gap = tyre overheating on the outside but cold carcass (delamination risk), or vice versa
- Wear: even across 4 wheels — abnormally high wear on one wheel signals load imbalance
- Lap phases: normal warm-up pattern — should rise in phase 1 and stabilise

### 4. Tyre pressures

- Hot pressure (from Tyres): too high = overheating and loss of contact patch; too low = under-temperature, tyre wanders
- F/R pressure balance: asymmetry affects mechanical balance
- L/R pressure difference on the same axle — sign of asymmetric heating or incorrect cold starting pressure

### 5. Brakes

- Temperature range: <200°C = cold (poor braking), 350–800°C = normal GT working range, >900°C = dangerous overheating
- L/R asymmetry: different temperatures on same axle = uneven pad wear or brake balance issue
- If rears are consistently hotter than fronts — bias is too far rearward; if fronts dominate — bias is forward; both reduce braking stability

### 6. Suspension

- Rake: moderate positive rake is standard for GT; very high rake increases rear aerodynamic load but can cause a lazy front on turn-in
- Roll per corner: typical roll 3–8 mm; large roll = soft suspension or weak anti-roll bars; small = stiff, sensitive to bumps
- L/R roll asymmetry in the same corner indicates uneven suspension travel or load distribution

### 7. Recommendations

Per identified issue — what specifically to change (direction of adjustment) and expected effect. Prioritise by lap time impact.

---

Below is the attached report. Begin analysis.
