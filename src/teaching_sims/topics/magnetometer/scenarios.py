"""Scripted lecture scenarios for magnetometer / heading."""

from __future__ import annotations

from dataclasses import dataclass

from teaching_sims.topics.magnetometer.physics import MagParams


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    teaching_point: str
    params: MagParams
    notes: str = ""
    auto_calibrate: bool = False


SCENARIOS: dict[str, Scenario] = {
    "level_sweep": Scenario(
        id="level_sweep",
        title="Level yaw sweep",
        teaching_point="On a level platform, raw atan2(-by, bx) tracks magnetic heading.",
        params=MagParams(pitch_deg=0.0, roll_deg=0.0, tilt_compensate=True),
    ),
    "pitched_needs_tc": Scenario(
        id="pitched_needs_tc",
        title="Pitch needs tilt compensation",
        teaching_point="Without tilt compensation, pitch couples the vertical field into heading error.",
        params=MagParams(pitch_deg=25.0, roll_deg=0.0, tilt_compensate=False, yaw_deg=0.0),
        notes="Enable tilt compensation and watch RMS error drop.",
    ),
    "pitched_with_tc": Scenario(
        id="pitched_with_tc",
        title="Tilt-compensated pitch",
        teaching_point="Tilt compensation rotates the field back to the horizontal before heading.",
        params=MagParams(pitch_deg=25.0, roll_deg=0.0, tilt_compensate=True),
    ),
    "bank_and_pitch": Scenario(
        id="bank_and_pitch",
        title="Bank + pitch",
        teaching_point="Both roll and pitch require compensation for a usable heading.",
        params=MagParams(pitch_deg=15.0, roll_deg=20.0, tilt_compensate=True),
    ),
    "hard_iron": Scenario(
        id="hard_iron",
        title="Hard-iron offset",
        teaching_point="A constant body bias shifts the polar plot off-center and biases heading.",
        params=MagParams(hard_x_ut=8.0, hard_y_ut=-5.0, pitch_deg=0.0, tilt_compensate=True),
        notes="The (bx, by) locus is a circle not centered at the origin.",
    ),
    "soft_iron": Scenario(
        id="soft_iron",
        title="Soft-iron distortion",
        teaching_point="Anisotropic soft-iron scales turn the locus into an ellipse - heading error varies with yaw.",
        params=MagParams(soft_xx=1.3, soft_yy=0.75, soft_xy=0.15, pitch_deg=0.0),
        notes="Press 'Compass swing + fit' to calibrate.",
    ),
    "iron_calibrated": Scenario(
        id="iron_calibrated",
        title="Compass swing calibration",
        teaching_point="A level 360 deg swing traces the ellipse; fitting it recovers hard and soft iron.",
        params=MagParams(hard_x_ut=8.0, hard_y_ut=-5.0, soft_xx=1.2, soft_yy=0.85, soft_xy=0.1, pitch_deg=0.0),
        notes="Fitted ellipse, its centre, and the corrected circle overlay the raw locus. Toggle Apply.",
        auto_calibrate=True,
    ),
    "dip_side_view": Scenario(
        id="dip_side_view",
        title="Why pitch hurts: the dip angle",
        teaching_point="At 66 deg dip the vertical field is 2x the horizontal: a little pitch leaks a lot into bx.",
        params=MagParams(yaw_deg=0.0, pitch_deg=10.0, tilt_compensate=False),
        notes="Side view: the field vector, its horizontal part, and body x. Try inclination 20 deg vs 75 deg.",
    ),
    "declination": Scenario(
        id="declination",
        title="Magnetic vs true north",
        teaching_point="The magnetometer finds magnetic north; add the local declination for true heading.",
        params=MagParams(declination_deg=-12.0, apply_declination=False, pitch_deg=0.0),
        notes="Constant 12 deg error at every heading. Tick 'Apply declination'. (Cork ~ -3 deg; Seattle ~ +15 deg.)",
    ),
    "steel_disturbance": Scenario(
        id="steel_disturbance",
        title="Local disturbance (steel, motors)",
        teaching_point="A world-fixed field distortion is not iron calibration: detect it via |B| and dip, then gate it.",
        params=MagParams(dist_e_ut=8.0, dist_d_ut=-6.0, pitch_deg=0.0),
        notes="Field check reports REJECT. Calibration cannot help: the error is outside the sensor.",
        auto_calibrate=True,
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
