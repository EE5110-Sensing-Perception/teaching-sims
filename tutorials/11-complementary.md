# Tutorial 11 — Attitude fusion: complementary, Kalman and Mahony filters

**Demo:** `teaching-sims demo complementary`  
**Prerequisites:** [08 — Accelerometers](08-accelerometer.md), [09 — Gyroscopes](09-gyroscope.md), [12 — Magnetometer](12-magnetometer.md); [10 — Frames and rotations](10-attitude.md) for the 3-D part  
**Slides:** section “Attitude estimation” of the IMU deck

By the end you should be able to:

- explain a complementary filter as a frequency split, and choose τ (then α) for a loop rate
- formulate the two-state [angle, bias] Kalman filter, and relate its steady state to a complementary filter
- write the Mahony filter update, and explain the roles of Kp and Ki
- reason about observability (why yaw needs a heading reference)
- recognise when the gravity assumption fails, and apply gating

---

## 1. Principles

### 1.1 Complementary filter

| | Gyro \(\int\omega\) | Accelerometer tilt |
| --- | --- | --- |
| Fast motion | good | noisy, spoofed by acceleration |
| Slow / DC | drifts with bias | absolute |

\[
\hat\theta_k=\alpha(\hat\theta_{k-1}+\omega_k\Delta t)+(1-\alpha)\theta^{\mathrm{acc}}_k
\quad\Longleftrightarrow\quad
\hat\Theta=\frac{s\tau}{1+s\tau}\Theta_{\mathrm{gyro}}+\frac{1}{1+s\tau}\Theta_{\mathrm{acc}},
\qquad \tau=\frac{\alpha\,\Delta t}{1-\alpha}.
\]

- The two paths sum to one at every frequency and cross at \(f_c=1/(2\pi\tau)\).
- Choose \(\tau\) from the physics: long enough to average accelerometer noise and short manoeuvres, short enough that gyro drift over \(\tau\) stays small.
- Then compute \(\alpha=\tau/(\tau+\Delta t)\). Moving a filter to a different loop rate without recomputing \(\alpha\) changes \(\tau\).

### 1.2 Kalman filter

The state is \(\mathbf x=[\theta,\,b]\), with the gyro as the input:

\[
\theta_k=\theta_{k-1}+(\tilde\omega_k-b_{k-1})\Delta t,\qquad b_k=b_{k-1}+w_b,\qquad z_k=\theta^{\mathrm{acc}}_k=\theta_k+v_k .
\]

- **Q** is the gyro noise plus the bias random walk (how fast the bias may move).
- **R** is the accelerometer-tilt noise.
- The covariance \(P\) tells you how confident the estimate is.
- In steady state the gain \(K_\theta\) is constant, so the angle update *is* a complementary filter with \(\alpha_{\mathrm{eq}}=1-K_\theta\). The Kalman filter adds an online bias estimate and principled tuning.

**Caveat:** the Kalman filter assumes white measurement noise. A sustained surge violates that, and the filter will even learn a wrong bias.

### 1.3 Mahony filter

\[
\dot{\mathbf q}=\tfrac12\mathbf q\otimes[0,\ \tilde{\boldsymbol\omega}-\hat{\mathbf b}+K_p\mathbf e],\qquad
\dot{\hat{\mathbf b}}=-K_i\mathbf e,\qquad
\mathbf e=\hat{\mathbf a}\times\hat R^\top[0,0,-1]^\top+\hat{\mathbf m}\times\hat R^\top\mathbf b_{\mathrm{ref}} .
\]

- The cross product is the small rotation that aligns the predicted and measured directions.
- \(K_p\approx1/\tau\).
- \(K_i\) integrates the persistent error into a gyro-bias estimate.

### 1.4 Observability

- Gravity does not change under rotation about the vertical.
- From gravity alone, roll, pitch and the horizontal gyro biases are observable, but **yaw and the vertical gyro bias are not**.
- A heading reference (magnetometer, GNSS course, vision) is required.

### 1.5 When gravity lies

- All accelerometer corrections assume \(\mathbf f\approx-\mathbf g\).
- **Gating** skips updates when \(\big|\|\mathbf f\|-g\big|>\epsilon\). It is cheap but imperfect: tilt can cancel the change in norm.
- **Better options** are to inflate R adaptively, or to estimate velocity and subtract the true acceleration (full INS, tutorial 13).

---

## 2. UI map

| Element | Role |
| --- | --- |
| **Mode** | *1-DOF pitch: CF vs KF* or *3-D Mahony* |
| Block diagram | CF structure with live α, τ, \(f_c\), and the KF's equivalent \(\alpha_{\mathrm{eq}}\), \(\tau_{\mathrm{eq}}\); the accel path opens when gated |
| Artificial horizon | Truth (sky/ground) vs CF and KF horizon lines at the playback time |
| Bode | Low-pass (accel) and high-pass (gyro) magnitudes, \(f_c\), and the motion frequency |
| Pitch estimates | Truth, gyro-only, accel, CF, KF with ±2σ band |
| Tabs | Errors; KF bias estimate ±2σ; surge profile and gated samples |
| 3-D view | Mahony estimate (solid) vs truth (ghost), with error readout |
| 3-D plots | Euler truth vs estimate, attitude error, gyro-bias estimates vs truth |

---

## 3. Guided walkthrough

### Experiment A — Frequency split (~8 min)

1. Load **Balanced sine pitch**. Note τ = 0.49 s and \(f_c\) = 0.33 Hz, with the 0.25 Hz motion near the crossover.
2. Load **Trust the gyro** (τ ≈ 10 s). The motion is smooth, but the bias drags the angle away before the accelerometer can correct it.
3. Load **Trust the accelerometer** (τ = 0.01 s). There is no drift, but the accelerometer noise passes straight through.
4. Load **Step pitch**. The gyro path follows the step instantly, while the accel path takes about τ.

### Experiment B — Kalman filter (~10 min)

1. Load **Kalman filter estimates the bias**. In the bias tab the estimate converges to 1°/s and the ±2σ band shrinks.
2. Read the block diagram: the Kalman filter's steady state equals a complementary filter with τ_eq ≈ 2.4 s.
3. Load **Kalman tuning: Q vs R**. Sweep **KF R** from 0.3 to 20 and watch α_eq and the noise vs drift trade.

### Experiment C — Acceleration (~8 min)

1. Load **Surge spoofs the accel**. The 4 s surge reads as nose-up, and the KF's bias estimate is corrupted.
2. Load **Gate the accel during surge**. Most surge samples are rejected (red marks), but some pass when the pitch cancels the norm change.

### Experiment D — 3-D and observability (~10 min)

1. Load **3-D Mahony without magnetometer**. Roll and pitch converge within seconds. Yaw drifts about 25° per minute, and \(\hat b_z\) never reaches the true 0.6°/s.
2. Load **3-D Mahony with magnetometer**. Everything converges.
3. Set **Ki = 0**. With no bias estimate, a steady error remains. Set **Kp = 0**, which is gyro-only integration.
4. Load **3-D: acceleration during a manoeuvre** and toggle **Gate accel**.

---

## 4. Lab sheet

| Trial | Setting | Observation |
| --- | --- | --- |
| 1 | α 0.98 at 100 Hz | τ = ____ s, \(f_c\) = ____ Hz |
| 2 | Same α at 400 Hz (compute) | τ = ____ s |
| 3 | KF R = 1.5° | α_eq ____, bias estimate ____ |
| 4 | Surge, no gate / gated | CF RMS ____ / ____ |
| 5 | Mahony, no mag / mag | yaw RMS ____ / ____; \(\hat b_z\) ____ / ____ |

---

## 5. Check your understanding

1. Your loop runs at 400 Hz with α = 0.98. What is τ? What if the same code runs at 100 Hz?
2. Which frequency band does each sensor contribute, and why?
3. How is a steady-state Kalman filter related to a complementary filter? What does it add?
4. Why can't accel + gyro estimate the vertical gyro bias on level ground?
5. Sketch the CF pitch error of a braking car, with and without gating.
6. When would you choose an EKF over Mahony on a robot?

---

## 6. Next

Continue with [13 — Strapdown INS](13-ins.md).
