# Tutorial 09 — Gyroscopes: integration, error models and Allan variance

**Demo:** `teaching-sims demo gyroscope`  
**Prerequisites:** [10 — Frames and rotations](10-attitude.md), [08 — Accelerometers](08-accelerometer.md); optional [16 — MEMS gyroscope](16-mems-gyro.md) for where bias comes from  
**Learning outcomes:** LP10, LP11, LP12, LP21 (see [IMU learning outcomes](IMU-learning-outcomes.md))  
**Slides:** sections C and F of the IMU deck

By the end you should be able to:

- predict how each gyro error term grows when integrated to heading
- explain why calibrating the turn-on bias is not enough
- compute an Allan deviation and read ARW, bias instability and RRW from it
- convert datasheet numbers into a simulation model and choose an IMU grade for a task

---

## 1. Principles

### 1.1 Rate to angle

\[
\hat\theta(t)=\int_0^t \tilde\omega(\tau)\,d\tau,\qquad
\tilde\omega = (1+s)\,\omega + b_0 + b_{\mathrm{BI}}(t) + b_{\mathrm{RW}}(t) + n(t).
\]

### 1.2 How each term grows (LP10, LP11)

| Term | Datasheet unit | Heading error |
| --- | --- | --- |
| Turn-on bias \(b_0\) | deg/h | \(b_0\,t\), a ramp. Removable by calibration at start-up |
| Scale factor \(s\) | ppm | \(s\times\) (angle turned); zero when stationary |
| ARW \(N\) (white rate noise) | deg/√h | \(N\sqrt t\), a random walk |
| Bias instability \(B\) (flicker) | deg/h | about \(B\,t\) while correlated; *not* removed by start-up calibration |
| Rate random walk \(K\) | deg/h/√h | \(K\,t^{3/2}/\sqrt3\) |

**Unit traps:**

- ARW in deg/√h ÷ 60 gives deg/√s, which equals deg/s/√Hz.
- The per-sample noise std at rate \(f_s\) is \(\sigma = N\sqrt{f_s}\).
- deg/h ÷ 3600 gives deg/s.

### 1.3 Allan variance (LP12)

Record at rest. For each cluster length \(\tau\), average the rate over consecutive clusters and compute

\[
\sigma_A^2(\tau)=\tfrac12\big\langle(\bar\omega_{k+1}-\bar\omega_k)^2\big\rangle.
\]

On a log-log plot:

- **slope −½**: white noise. \(N=\sigma_A(1\,\mathrm s)\).
- **slope 0**: bias instability. The floor is \(0.664\,B\).
- **slope +½**: rate random walk. \(K=\sigma_A(3\,\mathrm s)\) on that line.

Trust \(\tau\lesssim T/10\), where \(T\) is the record length. A constant bias is invisible to Allan variance. Expect about ±20 % scatter on \(B\) from a single record of a few hours. Better IMUs need *longer* records, because their floor emerges later.

### 1.4 Choosing a grade (LP21)

Ask two questions: how long must the system coast between aiding updates, and which term dominates over that horizon? Figures are representative, per datasheet class.

| | Consumer | Industrial | Tactical |
| --- | --- | --- | --- |
| Turn-on bias | ~1°/s | ~180°/h | ~1°/h |
| ARW | 0.3°/√h | 0.15°/√h | 0.05°/√h |
| Bias instability | 20°/h | 3°/h | 0.5°/h |

---

## 2. UI map

| Element | Role |
| --- | --- |
| Heading dial | Truth vs gyro-integrated heading at the playback time |
| Integrated angle | Truth vs estimate with time cursor |
| Angle error tab | This run (red), ±N√t ARW envelope (grey), and optional Monte Carlo ensemble with a ±2σ band |
| Rate tab | True vs measured rate |
| Allan deviation tab | Record at rest (10–240 min); log-log σ_A with N, B, K reference lines; model vs read-off table in datasheet units |
| IMU grade | Loads consumer / industrial / tactical datasheet values |
| Compensate turn-on bias | Subtracts \(b_0\) only; in-run terms remain |
| 3D window | Optional matplotlib truth vs gyro cubes |

---

## 3. Guided walkthrough

### Experiment A — Clean integration and bias ramp (~5 min)

1. Load **Clean step turn**. The estimate tracks the 90° turn.
2. Load **Bias -> angle ramp**. After the turn stops, the dial's gyro needle keeps turning.
3. Load **Bias compensated**. Same bias, but the error is now about 0.

### Experiment B — ARW is a random walk (~5 min)

1. Load **Angle random walk**, with the ensemble shown.
2. A single run looks like drift. The ensemble shows a zero-mean spread growing as \(N\sqrt t\) (the grey envelope).
3. Press **Resample noise** a few times.

### Experiment C — Bias instability defeats calibration (~5 min)

1. Load **Bias instability: calibration decays**. The turn-on bias is compensated, but runs drift apart within a minute.
2. Discuss: this is why EKFs carry a gyro-bias state (see [11 — Attitude fusion](11-complementary.md)).

### Experiment D — Scale factor (~3 min)

1. Load **Scale-factor error**. A 1 % error gives 0.9° after the 90° turn, and nothing more after that.

### Experiment E — Allan deviation (~10 min)

1. Load **Allan deviation (industrial MEMS)**. Read off N and B and compare them with the model column.
2. Switch the **IMU grade** to Consumer, then Tactical. The whole curve shifts down.
3. With Tactical, try 10 min vs 240 min records. The short record never reaches the floor.

### Experiment F — Grade and task (~5 min)

1. Load **Consumer IMU, 60 s heading hold**. Without compensation it drifts by about 60°.
2. Tick **Compensate turn-on bias**. The remaining drift is from bias instability and ARW.
3. Switch to **Tactical**. The drift becomes invisible on this timescale.

---

## 4. Lab sheet

| Trial | Setting | Observation |
| --- | --- | --- |
| 1 | Bias 1.5°/s, 8 s | Final error ≈ ____ (compare \(b\,t\)) |
| 2 | ARW 0.4°/√s, 16 s, ensemble | σ at 4 s ____, at 16 s ____ (ratio ≈ 2?) |
| 3 | Allan, industrial, 60 min | N read ____ vs 0.15; B read ____ vs 3 |
| 4 | Allan, tactical, 10 vs 240 min | B read ____ / ____ |
| 5 | Consumer, 60 s, compensated | Final error ____ |

---

## 5. Check your understanding

1. Why can't a gyro alone hold heading forever?
2. What does calibrating the turn-on bias buy you, and what does it miss?
3. A datasheet gives an ARW of 0.2°/√h. What per-sample noise std do you simulate at 400 Hz?
4. Why does the Allan curve not show a constant bias?
5. Your robot gets visual updates at 20 Hz but may lose them for 10 s. Which gyro terms matter, and which grade is sufficient?

---

## 6. Next

Continue with [12 — Magnetometer](12-magnetometer.md) for absolute heading, then [11 — Attitude fusion](11-complementary.md).
