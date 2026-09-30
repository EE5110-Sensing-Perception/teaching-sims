# Tutorial 08 — Accelerometers: specific force, errors, calibration and lever arm

**Demo:** `teaching-sims demo accelerometer`  
**Prerequisites:** [10 — Frames and rotations](10-attitude.md); optional [14 — MEMS comb-drive](14-mems-accel.md) for sensor internals  
**Slides:** sections “Inertial sensors”, “Sensor errors and calibration” and “In practice” of the IMU deck

By the end you should be able to:

- state what an accelerometer measures, and recover static roll and pitch from it
- explain why bias, linear acceleration and lever-arm effects all look like tilt
- write the deterministic error model (bias, scale factor, misalignment), and calibrate it with a six-position test
- compute and compensate the lever-arm acceleration of an off-centre IMU

---

## 1. Principles

### 1.1 Specific force

An accelerometer measures **specific force** \(\mathbf f=\mathbf a-\mathbf g\), the non-gravitational acceleration, resolved in body axes:

\[
\mathbf f^b = R^b_n(\mathbf a^n-\mathbf g^n).
\]

At rest and level in NED/FRD, \(\mathbf f^b\approx[0,\,0,\,-g]\): the sensor "feels" the support force pushing *up*. In free fall it reads zero.

### 1.2 Static tilt

For a quasi-static platform (\(\mathbf a\approx0\)):

\[
\phi=\operatorname{atan2}(-f_y,\,-f_z),\qquad
\theta=\operatorname{atan2}\!\big(f_x,\ \sqrt{f_y^2+f_z^2}\big).
\]

Nose-up pitch gives \(f_x=+g\sin\theta\). **Yaw is unobservable**, because gravity does not change when you rotate about the vertical.

### 1.3 Things that look like tilt

For a static accelerometer, any extra specific force along x is indistinguishable from a pitch of \(\operatorname{atan}(d/g)\approx d/g\):

| Source | Size | Pitch error |
| --- | --- | --- |
| Consumer bias | 0.1 m/s² (10 mg) | 0.6° |
| Car accelerating | 1 m/s² | 5.8° (nose-*up*: the pilots' somatogravic illusion) |
| IMU 0.5 m from the spin axis at 120°/s | \(\omega^2 r\approx2.2\) m/s² | −12.6° |

Vibration is different: it is zero-mean, so averaging recovers the static pose. Bias, sustained acceleration and lever-arm terms do *not* average out.

### 1.4 Deterministic error model

\[
\tilde{\mathbf f} = (I+S)\,M\,\mathbf f + \mathbf b + \mathbf n
\]

- \(S\) = scale-factor errors (%)
- \(M\) = small non-orthogonality / misalignment terms (mrad)
- \(\mathbf b\) = bias

Scale and misalignment errors grow with the signal. A level sensor mostly hides them, and a tilted one reveals them.

### 1.5 Six-position calibration

1. Place each axis up and then down. The true specific force is then \(\pm g\,\mathbf e_k\).
2. Average each pose, then solve \(\bar{\mathbf y}_k = G\,\mathbf f_k + \mathbf b\) by linear least squares. There are 18 equations and 12 unknowns.
3. Correct live data with \(\hat{\mathbf f}=\hat G^{-1}(\tilde{\mathbf y}-\hat{\mathbf b})\).

### 1.6 Lever arm

An IMU at offset \(\mathbf r\) from the rotation centre measures an extra

\[
\boldsymbol\omega\times(\boldsymbol\omega\times\mathbf r)+\dot{\boldsymbol\omega}\times\mathbf r .
\]

Compensate it with the gyro rate and a known \(\mathbf r\), or mount the IMU near the centre of rotation.

---

## 2. UI map

| Element | Role |
| --- | --- |
| Side / rear views | Body block (pink dot = nose), body axes, gravity \(g\), measured \(\mathbf f\) (green) and the non-gravity part (red). Grey = true level; yellow = the level the accelerometer *believes* |
| Pitch error plot | \(\operatorname{atan}\) curve of pitch error vs extra x specific force. The marker is the current operating point: bias, surge and lever arm share one curve |
| Specific force plot | Noisy \(f_x, f_y, f_z\) |
| Tilt tab | Instantaneous and moving-average roll/pitch vs truth |
| Six-position calibration tab | Run the tumble test; table and bar chart of true vs estimated bias/scale/misalignment; **Apply calibration** corrects the live data |
| 3D window checkbox | External matplotlib cube; yaw rotates it but not the tilt estimate |
| Presenter mode | Hides the extra error, motion and advanced sliders |

---

## 3. Guided walkthrough

### Experiment A — Level plate and static tilt (~5 min)

1. Load **Level plate**. \(f_z\approx-9.81\), and \(\mathbf f\) points straight up.
2. Load **Static tilt**. The body tilts but \(\mathbf f\) still points up, and the estimate matches the truth.
3. Enable the 3D window and move **Yaw**. The cube turns, but nothing in the accelerometer changes.

### Experiment B — Bias, surge and lever arm (~8 min)

1. Load **Bias looks like tilt**. The yellow "apparent level" line tilts away from true level.
2. Load **Linear accel contamination**. Forward acceleration reads as nose-*up*, and the marker lies on the same curve.
3. Load **Lever arm: spinning robot**. There is about 12.6° of fake nose-down. Tick **Compensate lever arm**.

### Experiment C — Vibration (~4 min)

1. Load **Vibration vs averaging**. The instantaneous tilt jitters by ±10°, and the 1 s moving average sits on the truth.
2. Change **Average window** (Advanced) to see the noise vs lag trade.

### Experiment D — Scale and misalignment (~5 min)

1. Load **Scale factor and misalignment**. Level, the error is small.
2. Drag **Pitch** to 40° and **Roll** to 30°. The error changes, because the errors scale with the gravity components.

### Experiment E — Six-position calibration (~8 min)

1. Load **Six-position calibration** and open the calibration tab.
2. Press **Run six-position calibration**. Compare the true and estimated bias, scale and misalignment.
3. Tick **Apply calibration**. The tilt error drops from degrees to hundredths of a degree.
4. Reduce **Samples per pose** to 10 and rerun. Noise now limits the estimates.

---

## 4. Lab sheet

| Trial | Setting | Observation |
| --- | --- | --- |
| 1 | Level | \(f_z\approx-g\) |
| 2 | Bias X = 0.5 m/s² | Pitch error ≈ ____° (compare \(\operatorname{atan}(0.5/g)\)) |
| 3 | Surge 2 m/s² | Pitch error ≈ ____°, sign ____ |
| 4 | Lever arm 0.5 m, 120°/s | Fake pitch ____°; with compensation ____° |
| 5 | Six-position, 200 samples | Bias error ____ mg, scale error ____ % |
| 6 | Six-position, 10 samples | Bias error ____ mg |

---

## 5. Check your understanding

1. Why doesn't a parked car's accelerometer read zero? What would it read in free fall?
2. Can you tell a bias from a true tilt with only an accelerometer at one orientation? What does the six-position test add?
3. Why does a car's accelerometer-only tilt estimate pitch *up* when the car accelerates?
4. When is averaging tilt estimates valid, and when does it fail?
5. You mount an IMU on a robot arm's end effector. Which lever-arm terms appear when the arm moves?

---

## 6. Next

Continue with [09 — Gyroscopes](09-gyroscope.md).
