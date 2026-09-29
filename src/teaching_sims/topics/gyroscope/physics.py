"""Gyroscope teaching physics: rate integration, error model, ensembles, Allan variance.

Single-axis (yaw about Down) rate gyro:

    w_meas = (1 + s) w_true + b0 + b_GM(t) + b_RW(t) + n(t)

* ``b0``      constant (turn-on) bias           -> angle error ~ b0 t
* ``b_GM``    bias instability (Gauss-Markov)    -> slowly wandering drift
* ``b_RW``    rate random walk                   -> angle error std ~ K t^1.5 / sqrt(3)
* ``n``       white noise, density N (ARW)       -> angle error std ~ N sqrt(t)
* ``s``       scale factor                       -> error proportional to the angle turned
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

import numpy as np

from teaching_sims.core.allan import allan_deviation, read_noise_terms
from teaching_sims.core.imu import wrap_180
from teaching_sims.core.imu_errors import GRADE_PRESETS, SensorErrorModel


class MotionProfile(str, Enum):
    CONSTANT = "constant"  # constant rate
    SINE = "sine"
    STEP_TURN = "step_turn"


@dataclass(frozen=True)
class GyroParams:
    """Single-axis (Z) gyro experiment for attitude about one axis."""

    profile: MotionProfile = MotionProfile.STEP_TURN
    rate_dps: float = 30.0  # commanded rate magnitude
    sine_hz: float = 0.5
    duration_s: float = 8.0
    fs_hz: float = 100.0
    bias_dps: float = 0.5
    # Angle random walk (deg/sqrt(s)) - white rate noise density
    arw_deg_per_sqrt_s: float = 0.05
    # In-run bias instability (Gauss-Markov sigma, deg/s) and its correlation time
    bias_instability_dps: float = 0.0
    bi_corr_time_s: float = 30.0
    # Rate random walk (deg/s/sqrt(s))
    rrw_dps_per_sqrt_s: float = 0.0
    scale_ppm: float = 0.0
    # Integrate with / without bias compensation (subtract the *turn-on* bias)
    compensate_bias: bool = False
    seed: int = 0

    def __post_init__(self) -> None:
        if self.fs_hz <= 0 or self.duration_s <= 0:
            raise ValueError("fs_hz and duration_s must be positive")
        if self.arw_deg_per_sqrt_s < 0 or self.bias_instability_dps < 0 or self.rrw_dps_per_sqrt_s < 0:
            raise ValueError("noise terms must be >= 0")

    def error_model(self) -> SensorErrorModel:
        return SensorErrorModel(
            bias=self.bias_dps,
            scale_factor_ppm=self.scale_ppm,
            white_density=self.arw_deg_per_sqrt_s,
            bias_instability=self.bias_instability_dps,
            bi_corr_time_s=self.bi_corr_time_s,
            rrw=self.rrw_dps_per_sqrt_s,
        )


def params_for_grade(base: GyroParams, grade: str) -> GyroParams:
    """Load datasheet values for an IMU grade into the (deg/s) working units."""
    m = GRADE_PRESETS[grade].gyro_model()
    return replace(
        base,
        bias_dps=m.bias,
        arw_deg_per_sqrt_s=m.white_density,
        bias_instability_dps=m.bias_instability,
        bi_corr_time_s=m.bi_corr_time_s,
        rrw_dps_per_sqrt_s=m.rrw,
    )


def datasheet_units(p: GyroParams) -> dict[str, float]:
    """Current model expressed in datasheet units."""
    return {
        "bias_dph": p.bias_dps * 3600.0,
        "arw_dpsh": p.arw_deg_per_sqrt_s * 60.0,
        "bi_dph": p.bias_instability_dps * 3600.0,
        "rrw_dphsh": p.rrw_dps_per_sqrt_s * 3600.0 * 60.0,
    }


def true_rate_dps(params: GyroParams, t: np.ndarray) -> np.ndarray:
    """Scripted true angular rate about Z (deg/s)."""
    if params.profile == MotionProfile.CONSTANT:
        return np.full_like(t, params.rate_dps, dtype=float)
    if params.profile == MotionProfile.SINE:
        return params.rate_dps * np.sin(2.0 * np.pi * params.sine_hz * t)
    # step turn: rotate for 3 s then stop
    w = np.zeros_like(t)
    w[(t >= 1.0) & (t < 4.0)] = params.rate_dps
    return w


def _integrate(params: GyroParams, t: np.ndarray, w_true: np.ndarray, rng: np.random.Generator) -> dict[str, np.ndarray]:
    dt = 1.0 / params.fs_hz
    sensed = params.error_model().apply(w_true, params.fs_hz, rng)
    w_meas = sensed["meas"]
    w_int = w_meas - (params.bias_dps if params.compensate_bias else 0.0)
    theta_true = np.cumsum(w_true) * dt
    theta_hat = np.cumsum(w_int) * dt
    return {
        "rate_meas_dps": w_meas,
        "bias_history_dps": sensed["bias"],
        "angle_true_deg": wrap_180(theta_true),
        "angle_est_deg": wrap_180(theta_hat),
        "angle_err_deg": theta_hat - theta_true,  # unwrapped: drift can exceed 180 deg
    }


def simulate_gyro(params: GyroParams) -> dict[str, object]:
    n = int(params.duration_s * params.fs_hz)
    t = np.arange(n, dtype=float) / params.fs_hz
    w_true = true_rate_dps(params, t)
    rng = np.random.default_rng(params.seed)
    r = _integrate(params, t, w_true, rng)
    sigma = params.arw_deg_per_sqrt_s * np.sqrt(params.fs_hz)
    return {
        "t_s": t,
        "rate_true_dps": w_true,
        "rate_meas_dps": r["rate_meas_dps"],
        "bias_history_dps": r["bias_history_dps"],
        "angle_true_deg": r["angle_true_deg"],
        "angle_est_deg": r["angle_est_deg"],
        "angle_err_deg": r["angle_err_deg"],
        "final_err_deg": float(r["angle_err_deg"][-1]),
        "bias_dps": params.bias_dps,
        "sigma_rate_dps": float(sigma),
        "arw_envelope_deg": params.arw_deg_per_sqrt_s * np.sqrt(t),
    }


def monte_carlo_errors(params: GyroParams, n_runs: int = 30) -> np.ndarray:
    """Angle-error histories (n_runs, n) with independent noise realisations."""
    n = int(params.duration_s * params.fs_hz)
    t = np.arange(n, dtype=float) / params.fs_hz
    w_true = true_rate_dps(params, t)
    out = np.empty((n_runs, n))
    for k in range(n_runs):
        rng = np.random.default_rng(10_000 + params.seed * 97 + k)
        out[k] = _integrate(params, t, w_true, rng)["angle_err_deg"]
    return out


def static_allan(params: GyroParams, record_s: float = 3600.0, fs_hz: float = 20.0, seed: int = 7) -> dict[str, object]:
    """Allan deviation of a static (zero-rate) record with the current error model."""
    n = int(record_s * fs_hz)
    y = params.error_model().apply(np.zeros(n), fs_hz, np.random.default_rng(seed))["meas"]
    taus, adev = allan_deviation(y, fs_hz, n_taus=45)
    keep = taus <= record_s / 10.0
    terms = read_noise_terms(taus, adev, t_total=record_s)
    return {"taus": taus[keep], "adev": adev[keep], "terms": terms}


def process(params: GyroParams) -> dict[str, object]:
    return simulate_gyro(params)
