# IMU track — module map (MSc Robotics)

The IMU / inertial-navigation module is organised into six sections. Every topic below has at least:

- one or more frames in the lecture decks (IMU Parts 1-3, distributed with the course)
- one demo scenario (`teaching-sims demo <demo> --scenario <id>`)
- one tutorial section with experiments and check-your-understanding questions

## Suggested order

| # | Block | Demo | Tutorial | Deck |
| --- | --- | --- | --- | --- |
| 1 | MEMS accelerometer | `mems-accel` | [14](14-mems-accel.md) | Part 1 |
| 2 | Accelerometer: specific force and tilt | `accelerometer` | [08](08-accelerometer.md) | Part 1 |
| 3 | MEMS gyroscope | `mems-gyro` | [16](16-mems-gyro.md) | Part 1 |
| 4 | Magnetometer: heading | `magnetometer` | [12](12-magnetometer.md) | Part 1 |
| 5 | Gyroscope: error models, Allan variance | `gyroscope` | [09](09-gyroscope.md) | Part 2 |
| 6 | Calibration and lever arm | `accelerometer`, `magnetometer` | [08](08-accelerometer.md), [12](12-magnetometer.md) | Part 2 |
| 7 | Frames and rotations | `attitude` | [10](10-attitude.md) | Part 3 |
| 8 | Attitude fusion: CF, KF, Mahony | `complementary` | [11](11-complementary.md) | Part 3 |
| 9 | Strapdown INS and aiding | `ins` | [13](13-ins.md) | Part 3 |

The decks are IMU Part 1 (how inertial sensors work), Part 2 (errors, noise and calibration)
and Part 3 (attitude, fusion and inertial navigation). They are not part of this repository. Frames titled **Demo** give the command, what to do, what to observe and
a question. Frames titled **Background** cover prerequisites.

## Coverage

### Frames and rotations

| Topic | Demo | Scenarios |
| --- | --- | --- |
| Sensor/body/navigation frames; NED/FRD vs ENU/FLU (ROS REP-103) | attitude | `ned_vs_ros` |
| DCM, Euler, quaternion, axis-angle; q ≡ −q | attitude | `level_heading`, `pitch_nose_up`, `quat_double_cover` |
| Composition order; intrinsic vs extrinsic | attitude | `sequence_intrinsic`, `intrinsic_vs_extrinsic`, `order_matters` |
| Gimbal lock as a coordinate singularity | attitude | `gimbal_lock_scan` |
| Kinematics, integration, renormalisation, coning | attitude | `dcm_drift`, `dcm_renormalized`, `coning` |

### Sensors

| Topic | Demo | Scenarios |
| --- | --- | --- |
| MEMS accelerometer dynamics; sensitivity vs bandwidth vs noise | mems-accel | `constant_accel`, `impulse_ring`, `soft_vs_stiff`, `vibration_above_bw` |
| Specific force, static tilt, yaw unobservable | accelerometer | `level_plate`, `static_tilt`, `bias_tilts_estimate`, `surge_contaminates`, `vibration_average` |
| Coriolis vibratory gyro; quadrature; mode matching | mems-gyro | `coriolis_step`, `quadrature_rejected`, `quadrature_bias`, `mode_matched`, `mode_split` |
| Magnetometer heading, tilt compensation, dip, declination, disturbances | magnetometer | `pitched_needs_tc`, `dip_side_view`, `declination`, `steel_disturbance` |

### Errors and calibration

| Topic | Demo | Scenarios |
| --- | --- | --- |
| Bias, scale factor, misalignment (and their physical origins) | accelerometer, gyroscope, mems-gyro | `scale_misalignment`, `scale_factor`, `quadrature_bias` |
| ARW/VRW, bias instability, RRW, and their growth laws | gyroscope | `angle_random_walk`, `bias_instability` |
| Allan variance; datasheet ↔ model | gyroscope | `allan_industrial` |
| Six-position accelerometer calibration; magnetometer ellipse fit | accelerometer, magnetometer | `six_position_cal`, `iron_calibrated` |

### Attitude estimation

| Topic | Demo | Scenarios |
| --- | --- | --- |
| Complementary filter as a frequency split; τ and α | complementary | `balanced_sine`, `trust_gyro`, `trust_accel`, `step_pitch` |
| Mahony nonlinear complementary filter | complementary | `mahony_with_mag` |
| Kalman filter with bias state; covariance; observability | complementary | `kalman_bias`, `kalman_tuning`, `mahony_no_mag` |
| Failure of the gravity assumption; gating | complementary, accelerometer | `surge_spoofs_accel`, `surge_gated`, `mahony_surge` |

### Inertial navigation

| Topic | Demo | Scenarios |
| --- | --- | --- |
| Strapdown mechanisation; gravity leakage | ins | `perfect_circle`, `tilt_leaks_gravity` |
| Error growth t, t², t³ | ins | `accel_bias_straight`, `pitch_gyro_cubic`, `gyro_bias_circle`, `error_budget` |
| Aiding: ZUPT, position fixes | ins | `stop_and_go`, `zupt`, `zupt_false_detection`, `position_fixes` |

### Practice

| Topic | Demo | Scenarios |
| --- | --- | --- |
| Choosing an IMU grade; coast time | gyroscope, ins | `grade_one_minute`, `grade_consumer` |
| Lever arm | accelerometer | `lever_arm_spin` |

## Learning outcomes and where they are covered

| Learning outcome | Deck | Demo | Status |
| --- | --- | --- | --- |
| Dead reckoning; what inertial sensors can and cannot measure; IMU/AHRS/INS | Part 1 | — | covered |
| MEMS accelerometer dynamics; sensitivity vs bandwidth vs noise; readout | Part 1 | `mems-accel` | covered |
| Specific force; tilt from gravity; tilt/bias/acceleration ambiguity | Part 1 | `accelerometer` | covered |
| Coriolis force; vibratory gyroscope; quadrature; mode matching | Part 1 | `mems-gyro` | covered |
| Magnetometer heading, tilt compensation, disturbances | Part 1 | `magnetometer` | covered |
| Thermal noise, noise density, resolution | Part 2 | — | covered (no demo) |
| Measurement model; turn-on vs in-run bias | Part 2 | `accelerometer` | covered |
| Error growth laws; ARW, bias instability, RRW, VRW | Part 2 | `gyroscope` | covered |
| Allan variance; datasheet units; IMU grades | Part 2 | `gyroscope` | covered |
| Six-position, gyroscope and magnetometer calibration | Part 2 | `accelerometer`, `magnetometer` | covered |
| Lever arm, vibration, timing, `sensor_msgs/Imu`, extrinsic calibration | Part 2 | `accelerometer` | partial (lever arm only in demo) |
| Frames; NED/FRD vs ROS ENU/FLU | Part 3 | `attitude` | covered |
| DCM, Euler angles, quaternions; gimbal lock | Part 3 | `attitude` | covered |
| Attitude kinematics, exact update, coning | Part 3 | `attitude` | covered |
| Complementary, Kalman and Mahony filters; observability; gating | Part 3 | `complementary` | covered |
| Strapdown mechanisation; initial alignment; error growth | Part 3 | `ins` | covered (alignment: slides only) |
| Aiding: ZUPT, position fixes, error-state KF | Part 3 | `ins` | covered |
| GNSS/INS coupling, odometry, VIO/LIO, preintegration | Part 3 | — | overview slide only |

## Assessment ideas

- **Lab report:** pick an IMU datasheet. Build its error model, compute the Allan curve, and predict the heading drift and INS position error over 10 s and 60 s. Check the predictions in the `gyroscope` and `ins` demos.
- **Design question:** a warehouse robot has wheel odometry at 50 Hz and a consumer IMU. Which states would you put in its EKF, and which measurement makes each one observable?
- **Debugging exercise:** give students a ROS bag in which the IMU is mounted upside-down and yaw is reported in NED. Ask them to find and fix the frame errors.
