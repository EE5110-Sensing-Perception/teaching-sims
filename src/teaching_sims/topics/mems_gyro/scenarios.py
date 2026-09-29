"""Scripted lecture scenarios for the MEMS Coriolis gyroscope demo."""

from __future__ import annotations

from dataclasses import dataclass

from teaching_sims.topics.mems_gyro.physics import MEMSGyroParams, RateProfile


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    teaching_point: str
    params: MEMSGyroParams
    notes: str = ""


SCENARIOS: dict[str, Scenario] = {
    "no_rotation": Scenario(
        id="no_rotation",
        title="Drive only, no rotation",
        teaching_point="The mass is driven back and forth along x. With no rotation there is no force along y.",
        params=MEMSGyroParams(profile=RateProfile.ZERO),
        notes="The mass traces a straight line. Sense output is zero.",
    ),
    "coriolis_step": Scenario(
        id="coriolis_step",
        title="Rotation creates Coriolis force",
        teaching_point="Rotation gives F = -2m Omega x v along y, in phase with drive velocity: the mass traces an ellipse.",
        params=MEMSGyroParams(profile=RateProfile.STEP, rate_dps=100.0),
        notes="Step to 100 deg/s at 50 ms. The demodulated output follows after the filter settles.",
    ),
    "quadrature_rejected": Scenario(
        id="quadrature_rejected",
        title="Quadrature error (rejected)",
        teaching_point="Fabrication imbalance couples x displacement into y, 90 deg from Coriolis. Correct-phase demod rejects it.",
        params=MEMSGyroParams(profile=RateProfile.ZERO, quadrature_dps=200.0),
        notes="Lissajous tilts into a line (displacement-phase). The rate channel stays at 0; the Q channel shows 200.",
    ),
    "quadrature_bias": Scenario(
        id="quadrature_bias",
        title="Phase error -> bias",
        teaching_point="A few degrees of demodulator phase error leak quadrature into the rate output: bias = -Omega_q sin(phi).",
        params=MEMSGyroParams(profile=RateProfile.ZERO, quadrature_dps=200.0, demod_phase_err_deg=3.0),
        notes="This is a real source of MEMS gyro bias and its temperature drift (the phase drifts with temperature).",
    ),
    "mode_matched": Scenario(
        id="mode_matched",
        title="Mode matched: sensitive but slow",
        teaching_point="Sense frequency = drive frequency: ~Q times more motion per deg/s, but bandwidth shrinks to ~f/(2Q).",
        params=MEMSGyroParams(profile=RateProfile.STEP, rate_dps=100.0, sense_split_hz=0.0, q_sense=200.0,
                              pickoff_noise_pm=20.0),
        notes="Compare pm per deg/s, noise and settling with split mode. At resonance the sense lags 90 deg, so the "
              "Coriolis path is a line: only the demodulator phase separates rate from quadrature.",
    ),
    "mode_split": Scenario(
        id="mode_split",
        title="Mode split: fast but less sensitive",
        teaching_point="Separating the modes by 300 Hz trades sensitivity (and noise) for a wide, flat rate response.",
        params=MEMSGyroParams(profile=RateProfile.STEP, rate_dps=100.0, sense_split_hz=300.0, q_sense=200.0,
                              pickoff_noise_pm=20.0),
        notes="Same pick-off noise as the matched case: the output noise in deg/s is higher.",
    ),
    "sine_rate_bandwidth": Scenario(
        id="sine_rate_bandwidth",
        title="Rate bandwidth",
        teaching_point="A 40 Hz rotation is tracked by the split-mode gyro. Switch to matched (split 0) and it is attenuated.",
        params=MEMSGyroParams(profile=RateProfile.SINE, rate_dps=100.0, rate_hz=40.0, sense_split_hz=300.0,
                              lpf_hz=200.0),
        notes="Marker on the rate-response plot = the input frequency.",
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
