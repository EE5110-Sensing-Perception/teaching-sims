# Tutorial 13 — Strapdown INS: mechanisation, error growth and aiding

**Demo:** `teaching-sims demo ins`  
**Prerequisites:** Tutorials 08–12 (especially [09 — Gyroscopes](09-gyroscope.md) and [11 — Attitude fusion](11-complementary.md))  
**Slides:** IMU Part 3 (`06_IMU_pt3`): “Strapdown inertial navigation”, “How inertial navigation errors grow” and “Aiding”

By the end you should be able to:

- write the strapdown mechanisation, and explain why attitude errors leak gravity
- predict the growth law (\(t\), \(t^2\), \(t^3\)) of each error source, and read them off a log-log plot
- explain how ZUPT and position fixes bound the error, and where each can fail
- estimate how long an IMU of a given grade can coast unaided

---

## 1. Principles

### 1.1 Mechanisation

\[
\dot{\mathbf R}=\mathbf R[\boldsymbol\omega]_\times,\qquad
\dot{\mathbf v}^n=\mathbf R\,\mathbf f^b+\mathbf g^n,\qquad
\dot{\mathbf p}^n=\mathbf v^n .
\]

The demo is planar: heading comes from the yaw gyro, with an added **tilt channel**. A pitch error \(\delta\theta\) resolves part of gravity into the horizontal:

\[
\delta a \approx -g\,\delta\theta \quad\Rightarrow\quad 0.1^\circ \text{ of tilt} \equiv 1.7\text{ mg of accelerometer bias}.
\]

Full navigation-grade mechanisation adds Earth rate, transport rate, Coriolis and the unstable vertical channel. These don't matter over robotics time scales and distances, but they do for long-range navigation.

### 1.2 Unaided error growth

| Source | Position error |
| --- | --- |
| Initial velocity error \(\delta v\) | \(\delta v\,t\) |
| Accel bias \(b_a\) | \(\tfrac12 b_a t^2\) |
| Initial tilt \(\delta\theta\) | \(\tfrac12 g\,\delta\theta\,t^2\) |
| Yaw gyro bias \(\varepsilon\) at speed \(v\) (straight path) | \(\tfrac12 v\,\varepsilon\,t^2\) (cross-track) |
| Pitch/roll gyro bias \(b_g\) | \(\tfrac16 g\,b_g\,t^3\) |

On a log-log plot each source is a straight line with slope 1, 2 or 3. Whichever is highest dominates at that time. Over hours, Schuler feedback turns the tilt terms into an 84-minute oscillation.

### 1.3 Aiding

- **Zero-velocity update (ZUPT).** When stationary, \(\mathbf v=0\) is a measurement.
  - Foot-mounted INS applies it at every stance phase.
  - The *detector* matters. At constant velocity the IMU reads "nothing happening", exactly like a stop. Vehicles confirm stops with wheel speed or vision.
- **Position or velocity fixes** (GNSS, odometry, VIO) fused in a Kalman filter turn unbounded drift into a bounded sawtooth.
  - The demo's filter has states \([p, v]\) per axis only, so heading error is never corrected and the peaks still creep up.
  - A full **error-state KF** estimates \(\delta\mathbf p,\delta\mathbf v,\delta\boldsymbol\theta,\mathbf b_a,\mathbf b_g\). This is the core of GNSS/INS, VIO and LIO.

### 1.4 Coasting

Take the residual biases after calibration (bias instability, ARW, VRW) and read off the time until the error exceeds your tolerance. That time sets the minimum aiding rate.

---

## 2. UI map

| Element | Role |
| --- | --- |
| Path | Truth vs INS track; markers and heading arrows at the playback time; position fixes (yellow) and ZUPT samples (green) |
| Position error (log-log) | Simulated error vs the analytic reference line for each non-zero source |
| Mechanisation diagram | Gyro → attitude → rotate f → +g → ∫v → ∫p. Shows the live tilt error with its equivalent leaked acceleration, the heading error, and the aiding block lighting up when active |
| Velocity error / heading tabs | Supporting time series |
| IMU grade | Loads residual biases and noise for consumer, industrial or tactical (calibrated or not) |
| Aiding / ZUPT detector | None, ZUPT (oracle or IMU thresholds), position fixes |

---

## 3. Guided walkthrough

### Experiment A — Mechanisation (~5 min)

1. Load **Perfect sensors (circle)**. The paths overlap.
2. Load **0.1 deg tilt = 1.7 mg bias**. The error follows \(\tfrac12 g\delta\theta t^2\), about 30 m after one minute.

### Experiment B — Growth laws (~10 min)

1. Load **Accel bias: t^2**, then **Pitch gyro bias: t^3**. Check the slope on the log-log plot.
2. Load **Yaw gyro bias on a circle**. The path spirals.
3. Load **Error budget (all terms)**. Identify which term dominates at 1 s, 10 s and 100 s.

### Experiment C — Aiding (~10 min)

1. Load **Stop-and-go (unaided)**. After parking at 30 s, the position keeps drifting.
2. Load **Zero-velocity updates**. The drift stops while parked.
3. Load **ZUPT detector fooled by cruise**. False stops during cruise wreck the solution.
4. Load **Position fixes (GNSS / odometry)**. The error becomes a sawtooth. Change the **Fix interval** from 1 s to 20 s.

### Experiment D — Grades (~5 min)

1. Load **Consumer IMU, one minute unaided**. Note the error at 60 s.
2. Switch the **IMU grade** to Industrial, then Tactical. Untick **calibrated** to see the effect of uncompensated turn-on bias.

---

## 4. Lab sheet

| Trial | Setting | Observation |
| --- | --- | --- |
| 1 | Tilt 0.1°, 60 s | Error ____ m (theory \(\tfrac12 g\delta\theta t^2\) = ____ ) |
| 2 | Pitch bias 0.01°/s, 30 s vs 60 s | Ratio ____ (theory 8) |
| 3 | Stop-and-go, unaided vs ZUPT | Drift while parked ____ / ____ m |
| 4 | Fixes every 1 / 5 / 20 s | Peak error ____ / ____ / ____ m |
| 5 | Consumer / industrial / tactical, 60 s | ____ / ____ / ____ m |

---

## 5. Check your understanding

1. Why does a 0.1° alignment error matter as much as a 1.7 mg accelerometer bias?
2. Which error source gives \(t^3\) growth, and why?
3. A parked robot's unaided INS drifts. Why? What single measurement stops it?
4. Why can't a car rely on IMU-only stationarity detection for ZUPT?
5. GNSS arrives at 1 Hz. Estimate the peak error between fixes for a consumer IMU.
6. List the states of an error-state KF for GNSS/INS, and say which measurement makes each observable.

---

## 6. Where to go next

Review the full outcome map in [IMU module map](IMU-module-map.md). Natural extensions: an error-state EKF with bias states, VIO/LIO (camera or LiDAR as the aiding sensor), and long-range effects (Earth rate, Schuler).
