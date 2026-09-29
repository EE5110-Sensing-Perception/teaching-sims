"""Scripted lecture scenarios for attitude fusion (CF, KF, Mahony)."""

from __future__ import annotations

from dataclasses import dataclass

from teaching_sims.topics.complementary.mahony import MahonyParams
from teaching_sims.topics.complementary.physics import ComplementaryParams, PitchMotion

MODE_1DOF = "1-DOF pitch: CF vs KF"
MODE_3D = "3-D Mahony"


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    teaching_point: str
    params: ComplementaryParams | None = None
    notes: str = ""
    mode: str = MODE_1DOF
    mparams: MahonyParams | None = None


SCENARIOS: dict[str, Scenario] = {
    "balanced_sine": Scenario(
        id="balanced_sine",
        title="Balanced sine pitch",
        teaching_point="alpha 0.98 (tau 0.5 s): gyro carries fast motion, accel removes slow drift.",
        params=ComplementaryParams(alpha=0.98, gyro_bias_dps=0.8, surge_mps2=0.0),
        notes="Bode: the motion (0.25 Hz) sits above f_c, so the gyro path dominates it.",
    ),
    "trust_gyro": Scenario(
        id="trust_gyro",
        title="Trust the gyro",
        teaching_point="alpha -> 1 (tau 10 s): smooth, but the bias walks the angle away before accel can pull it back.",
        params=ComplementaryParams(alpha=0.999, gyro_bias_dps=1.2),
    ),
    "trust_accel": Scenario(
        id="trust_accel",
        title="Trust the accelerometer",
        teaching_point="alpha 0.5 (tau 0.01 s): no drift, but all the accel noise passes straight through.",
        params=ComplementaryParams(alpha=0.5, gyro_bias_dps=1.0, accel_noise_mps2=0.4),
    ),
    "step_pitch": Scenario(
        id="step_pitch",
        title="Step pitch",
        teaching_point="A step is where tuning shows: the gyro path follows instantly, the accel path over ~tau.",
        params=ComplementaryParams(motion=PitchMotion.STEP, amp_deg=30.0, alpha=0.97),
    ),
    "kalman_bias": Scenario(
        id="kalman_bias",
        title="Kalman filter estimates the bias",
        teaching_point="State [theta, b]: the KF learns the gyro bias online, and its covariance shows its confidence.",
        params=ComplementaryParams(alpha=0.98, gyro_bias_dps=1.0, duration_s=40.0, kf_r_deg=1.5,
                                   kf_q_bias_dps_rts=0.01),
        notes="KF bias tab: estimate converges to 1 deg/s and the band shrinks. KF steady state = a CF with tau_eq.",
    ),
    "kalman_tuning": Scenario(
        id="kalman_tuning",
        title="Kalman tuning: Q vs R",
        teaching_point="R too small trusts the noisy accel; R too large trusts the drifting gyro. Q sets how fast bias may move.",
        params=ComplementaryParams(alpha=0.98, gyro_bias_dps=1.0, duration_s=30.0, kf_r_deg=0.3,
                                   kf_q_bias_dps_rts=0.05, accel_noise_mps2=0.3),
        notes="Sweep 'KF R' from 0.3 to 20 deg and watch alpha_eq / tau_eq in the block diagram.",
    ),
    "surge_spoofs_accel": Scenario(
        id="surge_spoofs_accel",
        title="Surge spoofs the accel",
        teaching_point="4 s of forward acceleration reads as nose-up; both filters are dragged toward it.",
        params=ComplementaryParams(motion=PitchMotion.SINE, amp_deg=10.0, alpha=0.98, surge_mps2=4.0,
                                   surge_start_s=4.0, surge_dur_s=4.0, gyro_bias_dps=0.2),
        notes="The KF is hit hardest: its R assumes white noise, and it even corrupts its bias estimate. Try gating.",
    ),
    "surge_gated": Scenario(
        id="surge_gated",
        title="Gate the accel during surge",
        teaching_point="Skip accel updates when | |f| - g | is large: the gyro coasts through the manoeuvre.",
        params=ComplementaryParams(motion=PitchMotion.SINE, amp_deg=10.0, alpha=0.98, surge_mps2=4.0,
                                   surge_start_s=4.0, surge_dur_s=4.0, gyro_bias_dps=0.2, gate_accel=True,
                                   gate_threshold_mps2=0.2),
        notes="Surge tab: red marks = gated samples. Some spoofed samples pass: tilt can cancel the norm change.",
    ),
    "mahony_no_mag": Scenario(
        id="mahony_no_mag",
        title="3-D Mahony without magnetometer",
        teaching_point="Gravity fixes roll and pitch (and their gyro biases); yaw and b_z are unobservable and drift.",
        mode=MODE_3D,
        mparams=MahonyParams(use_mag=False),
        notes="Yaw error grows ~linearly with the uncorrected z bias. Solid box = estimate, ghost = truth.",
    ),
    "mahony_with_mag": Scenario(
        id="mahony_with_mag",
        title="3-D Mahony with magnetometer",
        teaching_point="Adding a horizontal reference (magnetic north) makes yaw and b_z observable.",
        mode=MODE_3D,
        mparams=MahonyParams(use_mag=True),
        notes="All three bias estimates converge. Try Ki = 0: no bias estimate, so a steady error remains.",
    ),
    "mahony_surge": Scenario(
        id="mahony_surge",
        title="3-D: acceleration during a manoeuvre",
        teaching_point="10 s of 3 m/s^2 surge tilts the Mahony estimate; gating trades that for gyro-only coasting.",
        mode=MODE_3D,
        mparams=MahonyParams(use_mag=True, surge_mps2=3.0, surge_start_s=20.0, surge_dur_s=10.0),
        notes="Tick 'Gate accel' and compare the pitch error during 20-30 s.",
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
