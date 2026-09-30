# Tutorial 10 — Frames, rotations and attitude kinematics

**Demo:** `teaching-sims demo attitude`  
**Prerequisites:** linear algebra (orthogonal matrices, cross products)  
**Slides:** IMU Part 3 (`06_IMU_pt3`): “Frames and conventions”, “Representing attitude” and “Attitude from the gyroscope” (`make slides`)

By the end you should be able to:

- convert an attitude between aerospace NED/FRD and ROS REP-103 ENU/FLU
- move between DCM, ZYX Euler, quaternion and axis-angle, and say when each is appropriate
- explain intrinsic vs extrinsic sequences, and why rotation order matters
- explain gimbal lock as a coordinate singularity
- integrate body rates correctly, and recognise first-order and coning errors

---

## 1. Principles

### 1.1 Frames and conventions

| Frame | Aerospace | ROS REP-103 |
| --- | --- | --- |
| Navigation \(n\) | North-East-Down | East-North-Up |
| Body \(b\) | Forward-Right-Down | Forward-Left-Up |

The *same physical attitude* has different numbers in each convention:

\[
R^{\mathrm{ENU}}_{\mathrm{FLU}} = T\,R^{\mathrm{NED}}_{\mathrm{FRD}}\,T_b,\qquad
T=\begin{bmatrix}0&1&0\\1&0&0\\0&0&-1\end{bmatrix},\quad T_b=\mathrm{diag}(1,-1,-1).
\]

In ZYX Euler angles: \(\psi_{\mathrm{ROS}} = 90^\circ-\psi_{\mathrm{NED}}\) (yaw from East, counter-clockwise), \(\theta_{\mathrm{ROS}}=-\theta_{\mathrm{NED}}\), and \(\phi_{\mathrm{ROS}}=\phi_{\mathrm{NED}}\).

### 1.2 Representations

- **DCM** \(R^n_b\) maps body vectors into nav, \(v^n = R^n_b v^b\). Its columns are the body axes expressed in nav. It is orthonormal with \(\det R = +1\).
- **ZYX Euler**: \(R = R_z(\psi)R_y(\theta)R_x(\phi)\).
- **Unit quaternion** (Hamilton, scalar first): \(q = [\cos\frac{\alpha}{2},\ \hat n\sin\frac{\alpha}{2}]\). \(q\) and \(-q\) are the same rotation (double cover).
  - ROS messages store it as `x, y, z, w`. Check the order.

### 1.3 Composition order

- **Intrinsic** Z-Y′-X″: yaw about body z, then pitch about the *new* y, then roll about the *new* x.
- **Extrinsic** X-Y-Z about the *fixed* nav axes gives the same matrix.
- Changing the order (for example roll first about body axes) gives a different pose, because rotations do not commute.

### 1.4 Gimbal lock

\[
\dot\psi = \frac{\sin\phi\,\omega_y+\cos\phi\,\omega_z}{\cos\theta}
\]

At \(\theta=\pm90^\circ\) only \(\psi\mp\phi\) is defined. The Euler rates, and the sensitivity of the extracted angles, grow as \(1/\cos\theta\). The vehicle is fine; it is the parameterisation that fails. This is why filters propagate quaternions or DCMs.

### 1.5 Kinematics

\[
\dot R = R\,[\omega]_\times,\qquad \dot q = \tfrac12\, q\otimes[0,\ \omega].
\]

- **Exp-map step:** \(q_{k+1}=q_k\otimes\exp(\tfrac12\omega\Delta t)\). It is exact if \(\omega\) is constant over the step.
- **First-order DCM:** \(R_{k+1}=R_k(I+[\omega]_\times\Delta t)\). It leaves SO(3), and renormalising fixes orthonormality but not accuracy.
- **Coning:** if \(\omega\) rotates within a step, even the exp-map is wrong. Integrate faster, or use the IMU's internally compensated \(\Delta\theta\) increments.

---

## 2. UI map

| Element | Role |
| --- | --- |
| **Mode** | *Pose* (sliders), *Rotation sequence* (animated build-up), *Rate integration* (kinematics) |
| **Frames** | NED/FRD vs ENU/FLU. The body does not move; the labels, axes and numbers change |
| 3D view | Nav axes (grey), body box (pink = nose), body axes (red/green/blue = x/y/z), yellow = current rotation axis, ghost = reference pose |
| DCM panel | \(R^n_b\) colour-coded by sign/magnitude; quaternion, \(-q\), axis-angle, \(\det R\), \(\lVert R^\top R-I\rVert\) |
| Gimbal lock tab | Change in extracted yaw/roll for a 0.5° body rotation vs pitch; marker = current pitch |
| Rate integration tab | Attitude error vs a fine reference, and orthonormality error, with a time cursor |
| Playback | Play / scrub the sequence or the integration |

---

## 3. Guided walkthrough

Enable **Presenter mode** when projecting.

### Experiment A — Reading a DCM (~5 min)

1. Load **Level heading**. Column x is \([\cos45^\circ, \sin45^\circ, 0]\): body x points north-east.
2. Load **Nose-up pitch**. Body x gains a negative D (upward) component.
3. Ask: which row of \(R\) holds the gravity direction in body axes?

### Experiment B — NED vs ROS (~5 min)

1. Load **NED/FRD vs ROS ENU/FLU**.
2. Switch the **Frames** combo back and forth. The box does not move, but the y/z arrows flip and the DCM entries permute and change sign.
3. Read the status panel: yaw 30° NED is yaw 60° ROS, and pitch changes sign.

### Experiment C — Order matters (~8 min)

1. Load **Build ZYX: yaw, pitch, roll** and press **Play**. The yellow axis moves with the body (intrinsic).
2. Load **Extrinsic X-Y-Z = intrinsic Z-Y'-X''**. The yellow axis stays fixed in nav, and the final pose matches the ghost (0.0° apart).
3. Load **Order matters**. With the same angles in a different order, the status shows the two poses tens of degrees apart.

### Experiment D — Gimbal lock (~5 min)

1. Load **Gimbal lock** (pitch 85°).
2. Drag pitch toward 90°. The marker climbs the \(1/\cos\theta\) curve, and a 0.5° nudge moves the extracted yaw by tens of degrees.
3. At pitch 0 the roll change is zero. Why? (The perturbation is about body z.)

### Experiment E — Quaternion sign (~3 min)

1. Load **Quaternion: q and -q**. Both are listed as giving the same \(R\).
2. Discuss: averaging \(q\) and \(-q\) naively gives zero. Filters must choose a hemisphere.

### Experiment F — Integrating rates (~10 min)

1. Load **First-order DCM integration**. \(\det R\) drifts from 1, the box shears, and \(\lVert R^\top R-I\rVert\) grows.
2. Tick **Renormalize**. Orthonormality is restored, but the attitude error curve is unchanged.
3. Switch to **Quaternion exp-map**. The error is about 0, because the constant rate is integrated exactly.
4. Load **Coning error**. Even the exp-map drifts. Reduce **Step dt** and watch the error fall rapidly.

---

## 4. Lab sheet

| Trial | Setting | Observation |
| --- | --- | --- |
| 1 | Yaw 90°, level, NED | Column x = [0, 1, 0] |
| 2 | Same pose, ROS | Yaw = ____ , column x = ____ |
| 3 | ZYX vs XYZ order, (60, 30, 40) | Poses differ by ____ ° |
| 4 | Pitch 89.5°, perturb 0.5° | Yaw change ≈ ____ ° |
| 5 | DCM first order, 90°/s, dt 50 ms | Error at 10 s ____ °, ‖RᵀR−I‖ ____ |
| 6 | Coning 60°/s, dt 50 → 5 ms | Error ____ → ____ ° |

---

## 5. Check your understanding

1. A ROS node publishes yaw 0. Which way is the robot pointing in NED?
2. What does \(\det R=-1\) describe, and why must it never appear in a filter?
3. Is "rotate 30° about body x, then 90° about body z" the same as the reverse order?
4. Your EKF propagates Euler angles on a quadrotor doing flips. What goes wrong?
5. How should a filter handle \(q\) vs \(-q\) when computing an attitude error?
6. Why does renormalising a DCM not make it accurate?

---

## 6. Next

Continue with [14 — MEMS comb-drive](14-mems-accel.md) and [16 — MEMS gyroscope](16-mems-gyro.md) for sensor physics, then [08 — Accelerometers](08-accelerometer.md).
