"""Scripted lecture scenarios for the gyroscope demo."""

from __future__ import annotations

from dataclasses import dataclass

from teaching_sims.topics.gyroscope.physics import GyroParams, MotionProfile


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    teaching_point: str
    params: GyroParams
    notes: str = ""
    tab: str = ""  # tab_err | tab_rate | tab_allan
    show_mc: bool = False


SCENARIOS: dict[str, Scenario] = {
    "clean_step_turn": Scenario(
        id="clean_step_turn",
        title="Clean step turn",
        teaching_point="Integrating rate recovers angle when bias and noise are tiny.",
        params=GyroParams(
            profile=MotionProfile.STEP_TURN,
            bias_dps=0.0,
            arw_deg_per_sqrt_s=0.0,
            rate_dps=40.0,
        ),
    ),
    "bias_ramp": Scenario(
        id="bias_ramp",
        title="Bias -> angle ramp",
        teaching_point="A constant rate bias integrates to a linear angle error (unbounded drift).",
        params=GyroParams(
            profile=MotionProfile.STEP_TURN,
            bias_dps=1.5,
            arw_deg_per_sqrt_s=0.0,
            compensate_bias=False,
        ),
        notes="Enable bias compensation to reset the ramp. In 3D, truth stops; the gyro cube keeps turning.",
    ),
    "bias_compensated": Scenario(
        id="bias_compensated",
        title="Bias compensated",
        teaching_point="Subtracting a calibrated bias restores the turn - until the bias changes.",
        params=GyroParams(
            profile=MotionProfile.STEP_TURN,
            bias_dps=1.5,
            arw_deg_per_sqrt_s=0.0,
            compensate_bias=True,
        ),
    ),
    "angle_random_walk": Scenario(
        id="angle_random_walk",
        title="Angle random walk",
        teaching_point="White rate noise integrates to a random-walk angle error (grows like sqrt(t)).",
        params=GyroParams(
            profile=MotionProfile.CONSTANT,
            rate_dps=0.0,
            bias_dps=0.0,
            arw_deg_per_sqrt_s=0.4,
            duration_s=20.0,
        ),
        notes="The ensemble shows the spread: std grows as N sqrt(t). One run looks like a random drift.",
        tab="tab_err",
        show_mc=True,
    ),
    "sine_tracking": Scenario(
        id="sine_tracking",
        title="Sine rate tracking",
        teaching_point="Gyro follows oscillatory motion; bias still adds a slow ramp underneath.",
        params=GyroParams(
            profile=MotionProfile.SINE,
            rate_dps=45.0,
            sine_hz=0.4,
            bias_dps=0.6,
            arw_deg_per_sqrt_s=0.05,
        ),
    ),
    "noisy_turn": Scenario(
        id="noisy_turn",
        title="Noisy turn",
        teaching_point="Bias and ARW together: ramp plus wandering residual after the motion stops.",
        params=GyroParams(
            profile=MotionProfile.STEP_TURN,
            bias_dps=0.8,
            arw_deg_per_sqrt_s=0.15,
        ),
    ),
    "bias_instability": Scenario(
        id="bias_instability",
        title="Bias instability: calibration decays",
        teaching_point="Turn-on bias is subtracted, but the in-run bias wanders: heading drifts again within a minute.",
        params=GyroParams(
            profile=MotionProfile.CONSTANT,
            rate_dps=0.0,
            bias_dps=1.0,
            compensate_bias=True,
            arw_deg_per_sqrt_s=0.02,
            bias_instability_dps=0.1,
            bi_corr_time_s=20.0,
            duration_s=90.0,
        ),
        notes="Resample: each run drifts differently. This is why filters *estimate* bias online.",
        tab="tab_err",
        show_mc=True,
    ),
    "scale_factor": Scenario(
        id="scale_factor",
        title="Scale-factor error",
        teaching_point="A 1% scale error costs 0.9 deg on a 90 deg turn - and nothing when stationary.",
        params=GyroParams(
            profile=MotionProfile.STEP_TURN,
            rate_dps=30.0,
            bias_dps=0.0,
            arw_deg_per_sqrt_s=0.0,
            scale_ppm=10000.0,
        ),
        notes="Error appears only during the turn, then stays constant.",
    ),
    "allan_industrial": Scenario(
        id="allan_industrial",
        title="Allan deviation (industrial MEMS)",
        teaching_point="Record at rest, compute sigma_A(tau): read ARW at tau=1 s and bias instability at the floor.",
        params=GyroParams(
            profile=MotionProfile.CONSTANT,
            rate_dps=0.0,
            bias_dps=0.05,
            arw_deg_per_sqrt_s=0.0025,
            bias_instability_dps=3.0 / 3600.0,
            bi_corr_time_s=300.0,
            rrw_dps_per_sqrt_s=1.0 / 216000.0,
            duration_s=60.0,
        ),
        notes="Compare model vs read-off (+/-20% from one record is normal). Tactical needs longer records: its floor "
              "only emerges from the white noise after ~100 s.",
        tab="tab_allan",
    ),
    "grade_one_minute": Scenario(
        id="grade_one_minute",
        title="Consumer IMU, 60 s heading hold",
        teaching_point="Datasheet numbers -> heading drift. Consumer MEMS drifts tens of deg per minute uncompensated.",
        params=GyroParams(
            profile=MotionProfile.CONSTANT,
            rate_dps=0.0,
            bias_dps=1.0,
            arw_deg_per_sqrt_s=0.005,
            bias_instability_dps=20.0 / 3600.0,
            bi_corr_time_s=30.0,
            rrw_dps_per_sqrt_s=5.0 / 216000.0,
            duration_s=60.0,
        ),
        notes="Tick 'Compensate turn-on bias', then switch the grade to Tactical: drift becomes invisible here.",
        show_mc=True,
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
