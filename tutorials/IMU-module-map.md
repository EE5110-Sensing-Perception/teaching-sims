# IMU track — module map (MSc Robotics)

The IMU / inertial-navigation module is organised into six sections. Every topic below has at least:

- one frame in the lecture deck (`make slides` → `slides/build/imu.pdf`)
- one demo scenario (`teaching-sims demo <demo> --scenario <id>`)
- one tutorial section with experiments and check-your-understanding questions

## Suggested order

| # | Block | Demo | Tutorial | Deck section |
| --- | --- | --- | --- | --- |
| 1 | Frames and rotations | `attitude` | [10](10-attitude.md) | Frames |
| 2 | MEMS accelerometer | `mems-accel` | [14](14-mems-accel.md) | Sensors |
| 3 | MEMS gyroscope | `mems-gyro` | [16](16-mems-gyro.md) | Sensors |
| 4 | Accelerometer: specific force, errors, calibration | `accelerometer` | [08](08-accelerometer.md) | Sensors, Errors, Practice |
| 5 | Gyroscope: error models, Allan variance | `gyroscope` | [09](09-gyroscope.md) | Errors, Practice |
| 6 | Magnetometer: heading, calibration | `magnetometer` | [12](12-magnetometer.md) | Sensors, Errors |
| 7 | Attitude fusion: CF, KF, Mahony | `complementary` | [11](11-complementary.md) | Attitude |
| 8 | Strapdown INS and aiding | `ins` | [13](13-ins.md) | Navigation, Practice |

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

## Assessment ideas

- **Lab report:** pick an IMU datasheet. Build its error model, compute the Allan curve, and predict the heading drift and INS position error over 10 s and 60 s. Check the predictions in the `gyroscope` and `ins` demos.
- **Design question:** a warehouse robot has wheel odometry at 50 Hz and a consumer IMU. Which states would you put in its EKF, and which measurement makes each one observable?
- **Debugging exercise:** give students a ROS bag in which the IMU is mounted upside-down and yaw is reported in NED. Ask them to find and fix the frame errors.
