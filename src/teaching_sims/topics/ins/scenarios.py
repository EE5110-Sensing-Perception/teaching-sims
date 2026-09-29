"""Scripted lecture scenarios for strapdown INS."""

from __future__ import annotations

from dataclasses import dataclass

from teaching_sims.topics.ins.physics import Aiding, INSParams, PathProfile, ZuptDetector, params_for_grade


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    teaching_point: str
    params: INSParams
    notes: str = ""


_QUIET = dict(
    perfect_attitude=True,
    gyro_bias_dps=0.0,
    accel_bias_x_mps2=0.0,
    accel_bias_y_mps2=0.0,
    accel_noise_mps2=0.0,
    gyro_noise_dps=0.0,
)


SCENARIOS: dict[str, Scenario] = {
    "perfect_circle": Scenario(
        id="perfect_circle",
        title="Perfect sensors (circle)",
        teaching_point="With tiny errors and perfect attitude, the dead-reckoned path hugs truth.",
        params=INSParams(profile=PathProfile.CIRCLE, duration_s=50.0,
                         **(_QUIET | dict(accel_noise_mps2=0.001, gyro_noise_dps=0.001))),
        notes="Mechanisation: rotate f to nav, remove g, integrate twice. Nothing to correct here.",
    ),
    "accel_bias_straight": Scenario(
        id="accel_bias_straight",
        title="Accel bias: t^2",
        teaching_point="Constant accel bias -> velocity ramp -> position error b t^2 / 2.",
        params=INSParams(profile=PathProfile.STRAIGHT, duration_s=30.0, **(_QUIET | dict(accel_bias_x_mps2=0.08))),
        notes="Log-log error plot: slope 2, on top of the analytic reference line.",
    ),
    "tilt_leaks_gravity": Scenario(
        id="tilt_leaks_gravity",
        title="0.1 deg tilt = 1.7 mg bias",
        teaching_point="A pitch misalignment leaks g sin(theta) into the horizontal: 0.1 deg acts like 1.7 mg.",
        params=INSParams(profile=PathProfile.STRAIGHT, duration_s=60.0, **(_QUIET | dict(tilt0_deg=0.1))),
        notes="Same t^2 slope as an accel bias. Alignment accuracy matters as much as the accelerometer.",
    ),
    "pitch_gyro_cubic": Scenario(
        id="pitch_gyro_cubic",
        title="Pitch gyro bias: t^3",
        teaching_point="A pitch-gyro bias grows the tilt linearly, so gravity leakage grows position as t^3.",
        params=INSParams(profile=PathProfile.STRAIGHT, duration_s=60.0,
                         **(_QUIET | dict(gyro_pitch_bias_dps=0.01))),
        notes="36 deg/h of pitch bias -> ~60 m in one minute. Slope 3 on the log-log plot.",
    ),
    "gyro_bias_circle": Scenario(
        id="gyro_bias_circle",
        title="Yaw gyro bias on a circle",
        teaching_point="Heading drift points the velocity vector the wrong way: the path spirals away.",
        params=INSParams(profile=PathProfile.CIRCLE, perfect_attitude=False, gyro_bias_dps=0.4,
                         accel_bias_x_mps2=0.0, accel_bias_y_mps2=0.0, duration_s=50.0),
    ),
    "error_budget": Scenario(
        id="error_budget",
        title="Error budget (all terms)",
        teaching_point="Different terms dominate at different times: t early, t^2 mid, t^3 late.",
        params=INSParams(profile=PathProfile.STRAIGHT, perfect_attitude=False, gyro_bias_dps=0.02,
                         accel_bias_x_mps2=0.01, tilt0_deg=-0.05, gyro_pitch_bias_dps=-0.005,
                         init_vel_err_mps=0.05, accel_noise_mps2=0.01, gyro_noise_dps=0.01, duration_s=120.0),
        notes="Signs chosen so all terms add. Flip one (e.g. tilt) and the terms can cancel for a while.",
    ),
    "stop_and_go": Scenario(
        id="stop_and_go",
        title="Stop-and-go (unaided)",
        teaching_point="During stops, accel bias still integrates: a parked vehicle 'drifts' in an unaided INS.",
        params=INSParams(profile=PathProfile.STOP_AND_GO, duration_s=45.0,
                         **(_QUIET | dict(accel_bias_x_mps2=0.06, accel_noise_mps2=0.01))),
    ),
    "zupt": Scenario(
        id="zupt",
        title="Zero-velocity updates",
        teaching_point="When stationary, velocity is known to be zero: resetting it stops the drift.",
        params=INSParams(profile=PathProfile.STOP_AND_GO, duration_s=45.0, aiding=Aiding.ZUPT,
                         zupt_detector=ZuptDetector.ORACLE,
                         **(_QUIET | dict(accel_bias_x_mps2=0.06, accel_noise_mps2=0.01))),
        notes="Foot-mounted INS uses ZUPT every step: metres of error over kilometres.",
    ),
    "zupt_false_detection": Scenario(
        id="zupt_false_detection",
        title="ZUPT detector fooled by cruise",
        teaching_point="At constant velocity the IMU reads 'nothing happening' - exactly like a stop.",
        params=INSParams(profile=PathProfile.STOP_AND_GO, duration_s=45.0, aiding=Aiding.ZUPT,
                         zupt_detector=ZuptDetector.IMU,
                         **(_QUIET | dict(accel_bias_x_mps2=0.06, accel_noise_mps2=0.02, gyro_noise_dps=0.05))),
        notes="Green marks = detected stops. Vehicles need wheel speed or vision to confirm stops.",
    ),
    "position_fixes": Scenario(
        id="position_fixes",
        title="Position fixes (GNSS / odometry)",
        teaching_point="Periodic position fixes, fused by a small Kalman filter, turn unbounded drift into a sawtooth.",
        params=INSParams(profile=PathProfile.CIRCLE, perfect_attitude=False, gyro_bias_dps=0.4,
                         accel_bias_x_mps2=0.05, duration_s=60.0, aiding=Aiding.POSITION, fix_interval_s=5.0,
                         fix_sigma_m=2.0),
        notes="Peaks still creep up: this [p, v] filter never corrects heading. An error-state KF with attitude "
              "and gyro-bias states would. Try a 20 s fix interval.",
    ),
    "grade_consumer": Scenario(
        id="grade_consumer",
        title="Consumer IMU, one minute unaided",
        teaching_point="Datasheet -> residual biases -> error budget: a calibrated consumer IMU coasts for seconds.",
        params=params_for_grade(INSParams(profile=PathProfile.STRAIGHT, perfect_attitude=False, duration_s=60.0),
                                "consumer"),
        notes="Switch the IMU grade to Tactical and compare the one-minute error.",
    ),
}


def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError as exc:
        known = ", ".join(SCENARIOS)
        raise KeyError(f"unknown scenario {scenario_id!r}; choose from: {known}") from exc
