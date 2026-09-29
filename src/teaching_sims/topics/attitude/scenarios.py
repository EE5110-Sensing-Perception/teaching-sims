"""Scripted lecture scenarios for frames, rotations and attitude kinematics."""

from __future__ import annotations

from dataclasses import dataclass

from teaching_sims.topics.attitude.physics import AttitudeParams, Convention, Integrator, Sequence


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    teaching_point: str
    params: AttitudeParams
    notes: str = ""
    mode: str = "Pose"  # Pose | Rotation sequence | Rate integration


SCENARIOS: dict[str, Scenario] = {
    "level_heading": Scenario(
        id="level_heading",
        title="Level heading",
        teaching_point="Yaw rotates body x/y in the horizontal plane; body z stays along Down.",
        params=AttitudeParams(yaw_deg=45.0, pitch_deg=0.0, roll_deg=0.0),
        notes="DCM column 1 = body x in NED = [cos45, sin45, 0].",
    ),
    "pitch_nose_up": Scenario(
        id="pitch_nose_up",
        title="Nose-up pitch",
        teaching_point="Pitch tips body x out of the horizontal. DCM columns are the body axes in nav coordinates.",
        params=AttitudeParams(yaw_deg=0.0, pitch_deg=30.0, roll_deg=0.0),
        notes="Read column 1: body x has a -Down (up) component of sin30.",
    ),
    "ned_vs_ros": Scenario(
        id="ned_vs_ros",
        title="NED/FRD vs ROS ENU/FLU",
        teaching_point="Same vehicle, same physics: REP-103 relabels axes, flips y/z, and measures yaw from East.",
        params=AttitudeParams(yaw_deg=30.0, pitch_deg=10.0, roll_deg=15.0, convention=Convention.ENU_FLU),
        notes="Toggle the convention: the body does not move, but every number changes. R_ros = T R T_b.",
    ),
    "sequence_intrinsic": Scenario(
        id="sequence_intrinsic",
        title="Build ZYX: yaw, pitch, roll",
        teaching_point="Intrinsic Z-Y'-X'': each rotation is about the body's *current* axis (highlighted).",
        params=AttitudeParams(yaw_deg=60.0, pitch_deg=30.0, roll_deg=40.0, sequence=Sequence.INTRINSIC_ZYX),
        mode="Rotation sequence",
        notes="Press Play. The highlighted axis moves with the body.",
    ),
    "intrinsic_vs_extrinsic": Scenario(
        id="intrinsic_vs_extrinsic",
        title="Extrinsic X-Y-Z = intrinsic Z-Y'-X''",
        teaching_point="Rotating about *fixed* axes in reverse order reaches the same pose by a different path.",
        params=AttitudeParams(yaw_deg=60.0, pitch_deg=30.0, roll_deg=40.0, sequence=Sequence.EXTRINSIC_XYZ),
        mode="Rotation sequence",
        notes="The highlighted axis now stays fixed in the nav frame. Final pose = ghost of the ZYX result.",
    ),
    "order_matters": Scenario(
        id="order_matters",
        title="Order matters",
        teaching_point="Same three angles, roll-first body order: a different attitude. Rotations do not commute.",
        params=AttitudeParams(yaw_deg=60.0, pitch_deg=30.0, roll_deg=40.0, sequence=Sequence.INTRINSIC_XYZ),
        mode="Rotation sequence",
        notes="Ghost = ZYX pose. Status shows the angle between the two results.",
    ),
    "gimbal_lock_scan": Scenario(
        id="gimbal_lock_scan",
        title="Gimbal lock",
        teaching_point="Near pitch +/-90 deg a tiny rotation swings extracted yaw and roll by ~1/cos(pitch).",
        params=AttitudeParams(yaw_deg=30.0, pitch_deg=85.0, roll_deg=20.0, pitch_scan_deg=89.5),
        notes="Push pitch toward 90 and watch the sensitivity marker climb. The body itself is fine.",
    ),
    "quat_double_cover": Scenario(
        id="quat_double_cover",
        title="Quaternion: q and -q",
        teaching_point="q and -q are the same rotation. Axis-angle reads the rotation directly off q.",
        params=AttitudeParams(yaw_deg=150.0, pitch_deg=20.0, roll_deg=-120.0),
        notes="Status: DCM(q) and DCM(-q) agree. Filters must handle the sign when averaging/comparing q.",
    ),
    "dcm_drift": Scenario(
        id="dcm_drift",
        title="First-order DCM integration",
        teaching_point="R <- R(I + [w]x dt) is not a rotation: orthonormality error grows every step.",
        params=AttitudeParams(
            yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0, wz_dps=90.0, wx_dps=20.0,
            int_dt_s=0.05, integrator=Integrator.DCM_EULER, renormalize=False,
        ),
        mode="Rate integration",
        notes="Watch ||R^T R - I|| climb and the body box shear. Then tick Renormalize.",
    ),
    "dcm_renormalized": Scenario(
        id="dcm_renormalized",
        title="Renormalized DCM",
        teaching_point="Renormalising restores a valid rotation but not accuracy - the first-order error stays.",
        params=AttitudeParams(
            yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0, wz_dps=90.0, wx_dps=20.0,
            int_dt_s=0.05, integrator=Integrator.DCM_EULER, renormalize=True,
        ),
        mode="Rate integration",
        notes="Switch to Quaternion exp-map: exact for constant rate.",
    ),
    "coning": Scenario(
        id="coning",
        title="Coning error",
        teaching_point="Rates that rotate within a step (coning) break 'constant w per step': net drift appears.",
        params=AttitudeParams(
            yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0, wz_dps=0.0, coning_amp_dps=60.0, coning_hz=2.0,
            int_dt_s=0.05, integrator=Integrator.QUAT_EXP, renormalize=True,
        ),
        mode="Rate integration",
        notes="Shrink dt: error falls fast. Real IMUs integrate coning/sculling at kHz internally.",
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
