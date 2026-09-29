"""Scripted lecture scenarios for the accelerometer demo."""

from __future__ import annotations

from dataclasses import dataclass

from teaching_sims.topics.accelerometer.physics import AccelParams


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    teaching_point: str
    params: AccelParams
    notes: str = ""


SCENARIOS: dict[str, Scenario] = {
    "level_plate": Scenario(
        id="level_plate",
        title="Level plate",
        teaching_point="At rest and level, specific force is ~ -g along body Z.",
        params=AccelParams(roll_deg=0.0, pitch_deg=0.0, noise_mps2=0.01),
        notes="Read fx~0, fy~0, fz~-9.81 m/s^2.",
    ),
    "static_tilt": Scenario(
        id="static_tilt",
        title="Static tilt",
        teaching_point="Tilt maps gravity into fx/fy; arctan recovers roll/pitch when static.",
        params=AccelParams(yaw_deg=25.0, roll_deg=20.0, pitch_deg=-12.0, noise_mps2=0.02),
        notes="Enable the 3D window - yaw rotates the cube but not the accel tilt estimate.",
    ),
    "bias_tilts_estimate": Scenario(
        id="bias_tilts_estimate",
        title="Bias looks like tilt",
        teaching_point="A constant accel bias is indistinguishable from a static attitude error.",
        params=AccelParams(roll_deg=0.0, pitch_deg=0.0, bias_x_mps2=0.5, noise_mps2=0.01),
        notes="Level truth, but the apparent level line tilts. The error curve is atan(b/g): 0.1 m/s^2 ~ 0.6 deg.",
    ),
    "surge_contaminates": Scenario(
        id="surge_contaminates",
        title="Linear accel contamination",
        teaching_point="Accelerometers sense specific force: real linear accel spoofs tilt.",
        params=AccelParams(roll_deg=0.0, pitch_deg=0.0, ax_mps2=1.5, noise_mps2=0.02),
        notes="Forward acceleration reads as nose-UP (the pilots' somatogravic illusion). Same curve as bias.",
    ),
    "vibration_average": Scenario(
        id="vibration_average",
        title="Vibration vs averaging",
        teaching_point="High-frequency vibration jitters instantaneous tilt; a mean recovers the static pose.",
        params=AccelParams(
            roll_deg=8.0,
            pitch_deg=5.0,
            vibe_amp_mps2=2.0,
            vibe_hz=30.0,
            noise_mps2=0.05,
        ),
    ),
    "large_pitch": Scenario(
        id="large_pitch",
        title="Large pitch",
        teaching_point="Near vertical pitch, horizontal axes swap roles - tilt formulas get fragile.",
        params=AccelParams(roll_deg=5.0, pitch_deg=60.0, noise_mps2=0.02),
    ),
    "scale_misalignment": Scenario(
        id="scale_misalignment",
        title="Scale factor and misalignment",
        teaching_point="Scale and cross-axis errors only show when an axis sees g: harmless level, wrong when tilted.",
        params=AccelParams(roll_deg=0.0, pitch_deg=0.0, scale_z_pct=3.0, scale_x_pct=-2.0, mis_xz_mrad=15.0,
                           noise_mps2=0.01),
        notes="Level: a small pitch error from x<-z coupling. Now pitch to 40 deg and watch the error change.",
    ),
    "six_position_cal": Scenario(
        id="six_position_cal",
        title="Six-position calibration",
        teaching_point="Tumble through +/-x, +/-y, +/-z: least squares recovers bias, scale and misalignment.",
        params=AccelParams(roll_deg=15.0, pitch_deg=-20.0, bias_x_mps2=0.25, bias_y_mps2=-0.15, bias_z_mps2=0.3,
                           scale_x_pct=1.5, scale_y_pct=-1.0, scale_z_pct=2.0, mis_xy_mrad=6.0, mis_xz_mrad=-8.0,
                           mis_yz_mrad=5.0, noise_mps2=0.03),
        notes="Open the calibration tab, run it, then tick Apply: the tilt error collapses.",
    ),
    "lever_arm_spin": Scenario(
        id="lever_arm_spin",
        title="Lever arm: spinning robot",
        teaching_point="An IMU 0.5 m from the spin axis feels w^2 r toward the centre: a level robot looks tilted.",
        params=AccelParams(roll_deg=0.0, pitch_deg=0.0, lever_x_m=0.5, yaw_rate_dps=120.0, noise_mps2=0.02),
        notes="About 12 deg of fake nose-down. Tick 'Compensate lever arm' (needs the gyro rate and r).",
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
