# Tutorial 12 — Magnetometer heading, calibration and disturbances

**Demo:** `teaching-sims demo magnetometer`  
**Prerequisites:** [08 — Accelerometers](08-accelerometer.md) (tilt from gravity), [10 — Frames and rotations](10-attitude.md)  
**Learning outcomes:** LP9, LP13 (see [IMU learning outcomes](IMU-learning-outcomes.md))  
**Slides:** sections B and C of the IMU deck

By the end you should be able to:

- compute magnetic and true heading from a body-frame field measurement
- explain why tilt compensation is essential at high dip angles
- calibrate hard and soft iron with a compass swing and ellipse fit
- recognise world-fixed disturbances and gate them with field-magnitude and dip checks

---

## 1. Principles

### 1.1 The Earth field (LP9)

With total intensity \(F\), inclination (dip) \(I\) and declination \(D\):

\[
\mathbf b^n = F\,[\cos I\cos D,\ \cos I\sin D,\ \sin I]^\top .
\]

At mid latitudes \(I\approx60\)–\(70^\circ\), so the vertical component is about twice the horizontal one.

### 1.2 Heading

- **Level:** \(\psi_m = \operatorname{atan2}(-b_y,\,b_x)\).
- **Tilted:** first rotate the body field back to the local level plane using roll and pitch, typically from the accelerometer:

\[
x_h = b_x\cos\theta + b_y\sin\phi\sin\theta + b_z\cos\phi\sin\theta,\qquad
y_h = b_y\cos\phi - b_z\sin\phi .
\]

- **True heading** \(=\psi_m + D\). The declination comes from a model such as the WMM.
- **Error chain:** errors in the accelerometer tilt feed straight into heading through the large vertical field.

### 1.3 Hard and soft iron (LP13)

\[
\tilde{\mathbf b} = S\,\mathbf b + \mathbf h
\]

- **Hard iron** \(\mathbf h\) (magnetised parts on the robot) shifts the level-swing locus off the origin.
- **Soft iron** \(S\) (ferrous material distorting the field) stretches the locus into an ellipse.
- Both are body-fixed, so both can be calibrated.

**Compass swing:**

1. Rotate the vehicle through 360° while level.
2. Fit the conic \(ax^2+bxy+cy^2+dx+ey=1\) by linear least squares.
3. The centre gives \(\mathbf h\). The shape gives the matrix \(W\) that maps the ellipse onto a circle.
4. Correct with \(W(\tilde{\mathbf b}-\mathbf c)\).

A full 3-D (ellipsoid) calibration requires tumbling through all orientations.

### 1.4 Disturbances

World-fixed distortions, such as steel structures, rebar and cars, are not part of the sensor. No calibration removes them. Detect them instead:

\[
\big|\|\mathbf b\|-F\big| < 5\%,\qquad |\hat I - I| < 3^\circ,
\]

and reject the sample if either check fails, letting the gyro coast.

---

## 2. UI map

| Element | Role |
| --- | --- |
| Compass | Truth, tilt-compensated and raw heading needles for the snapshot pose; magnetic-north line when declination ≠ 0; field check (\|B\|, dip) with OK / REJECT |
| Side view | Earth field B with its horizontal part H, the pitched body x axis, and the resulting bx |
| Locus plot | (bx, by) during a yaw sweep; fitted ellipse, centre and calibrated circle after the compass swing |
| Heading plots | Heading and heading error vs true heading for raw, tilt-compensated and calibrated estimates |
| Compass swing + ellipse fit | Runs a level 360° swing with the current iron and fits the calibration |
| Advanced | Dip, soft iron, hard-iron z, world-fixed disturbance, noise |

---

## 3. Guided walkthrough

### Experiment A — Level heading and declination (~5 min)

1. Load **Level yaw sweep**. The error is about 0 everywhere.
2. Load **Magnetic vs true north**. There is a constant 12° offset at every heading. Tick **Apply declination**.

### Experiment B — Why pitch hurts (~8 min)

1. Load **Why pitch hurts: the dip angle**. In the side view, 10° of pitch changes bx from 20 to about 12 µT.
2. Load **Pitch needs tilt compensation**. The error is largest at east/west headings.
3. Tick **Tilt-compensated heading**. The error collapses.
4. In Advanced, set **Inclination** to 20° and then 80°. How does the uncompensated error change?

### Experiment C — Iron calibration (~8 min)

1. Load **Hard-iron offset**. The locus is a shifted circle.
2. Load **Soft-iron distortion**. The locus is a tilted ellipse, and the error varies with heading.
3. Load **Compass swing calibration**. The fitted ellipse, the centre at (8, −5) µT and the calibrated circle appear, and the RMS error falls from about 20° to under 1°.
4. Untick **Apply calibration** to compare.

### Experiment D — Disturbances (~5 min)

1. Load **Local disturbance (steel, motors)**. Calibration is applied, but the error remains, because the disturbance is in the world, not the sensor.
2. The compass panel shows the field check failing (\|B\| and dip off). This is how a filter should gate magnetometer updates.

---

## 4. Lab sheet

| Trial | Setting | Observation |
| --- | --- | --- |
| 1 | Pitch 25°, no tilt comp | Max error ____° at heading ____ |
| 2 | Same, tilt comp on | RMS ____° |
| 3 | Hard iron (8, −5) | Locus centre ____ |
| 4 | Compass swing, apply | RMS before ____ / after ____ |
| 5 | Disturbance E 8 µT, D −6 µT | Field check ____; RMS ____ |

---

## 5. Check your understanding

1. Why is heading error from pitch largest at east/west headings?
2. Why must the compass swing be performed level?
3. What can calibration fix, and what can it never fix?
4. Your robot drives past a parked car. What should the attitude filter do with the magnetometer?
5. Why is yaw usually the weakest state in an indoor VIO system?

---

## 6. Next

Continue with [11 — Attitude fusion](11-complementary.md).
