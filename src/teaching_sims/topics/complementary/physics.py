"""Single-axis attitude fusion: complementary filter vs Kalman filter (pitch).

Sensors (FRD body, specific force f = a - g):

* gyro   : w_meas = d(theta)/dt + b + n_g
* accel  : f_x = g sin(theta) + a_surge,  f_z = -g cos(theta)  (+ noise)
           theta_acc = atan2(f_x, -f_z)   (forward surge reads as nose-up)

Complementary filter (per step):

    theta_k = alpha (theta_{k-1} + w_k dt) + (1 - alpha) theta_acc,k

equivalent to a high-pass on the gyro angle and a low-pass on the accel
angle, both with time constant tau = alpha dt / (1 - alpha).

Kalman filter: state [theta, b], gyro drives the prediction, accel tilt is
the measurement. Its steady-state gain is a complementary filter with a
particular tau, *plus* an online bias estimate.

Accel gating: skip the accel correction when | |f| - g | exceeds a threshold
(a cheap detector of non-gravitational acceleration).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from teaching_sims.core.imu import DEG2RAD, G0, RAD2DEG, wrap_180


class PitchMotion(str, Enum):
    SINE = "sine"
    RAMP = "ramp"
    STEP = "step"


@dataclass(frozen=True)
class ComplementaryParams:
    """Fuse gyro rate with accelerometer tilt on a single pitch axis."""

    motion: PitchMotion = PitchMotion.SINE
    amp_deg: float = 25.0
    sine_hz: float = 0.25
    duration_s: float = 12.0
    fs_hz: float = 100.0
    # Complementary weight on gyro path (0 -> trust accel only, 1 -> gyro only)
    alpha: float = 0.98
    gyro_bias_dps: float = 0.8
    gyro_noise_dps: float = 0.3
    accel_noise_mps2: float = 0.15
    # Forward (body x) linear acceleration that contaminates accel tilt
    surge_mps2: float = 0.0
    surge_start_s: float = 0.0
    surge_dur_s: float = 0.0  # 0 = whole run
    # Kalman filter tuning
    kf_q_bias_dps_rts: float = 0.02  # bias random-walk density assumed by the KF
    kf_r_deg: float = 2.0  # accel-tilt measurement std assumed by the KF
    # Gate accel updates when | |f| - g | > threshold
    gate_accel: bool = False
    gate_threshold_mps2: float = 0.4
    seed: int = 0

    def __post_init__(self) -> None:
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError("alpha must be in [0, 1]")
        if self.fs_hz <= 0 or self.duration_s <= 0:
            raise ValueError("fs_hz and duration_s must be positive")
        if self.kf_r_deg <= 0:
            raise ValueError("kf_r_deg must be positive")

    @property
    def dt(self) -> float:
        return 1.0 / self.fs_hz


def filter_tau_s(alpha: float, dt: float) -> float:
    """Complementary-filter time constant tau = alpha dt / (1 - alpha)."""
    return float("inf") if alpha >= 1.0 else alpha * dt / (1.0 - alpha)


def crossover_hz(alpha: float, dt: float) -> float:
    tau = filter_tau_s(alpha, dt)
    return 0.0 if not np.isfinite(tau) or tau <= 0 else 1.0 / (2.0 * np.pi * tau)


def alpha_for_tau(tau_s: float, dt: float) -> float:
    return tau_s / (tau_s + dt)


def transfer_functions(alpha: float, dt: float, f_hz: np.ndarray) -> dict[str, np.ndarray]:
    """Discrete CF responses: accel path (low-pass) and gyro-angle path (high-pass)."""
    z1 = np.exp(-2j * np.pi * np.asarray(f_hz, dtype=float) * dt)  # z^-1
    den = 1.0 - alpha * z1
    lp = (1.0 - alpha) / den
    hp = alpha * (1.0 - z1) / den
    return {"f_hz": np.asarray(f_hz, dtype=float), "lowpass": np.abs(lp), "highpass": np.abs(hp)}


def true_pitch_deg(params: ComplementaryParams, t: np.ndarray) -> np.ndarray:
    if params.motion == PitchMotion.SINE:
        return params.amp_deg * np.sin(2.0 * np.pi * params.sine_hz * t)
    if params.motion == PitchMotion.RAMP:
        return np.clip(params.amp_deg * (t / max(params.duration_s, 1e-9)), -90, 90)
    # step at mid-time
    out = np.zeros_like(t)
    out[t >= 0.5 * params.duration_s] = params.amp_deg
    return out


def surge_profile(params: ComplementaryParams, t: np.ndarray) -> np.ndarray:
    if params.surge_mps2 == 0.0:
        return np.zeros_like(t)
    if params.surge_dur_s <= 0.0:
        return np.full_like(t, params.surge_mps2)
    on = (t >= params.surge_start_s) & (t < params.surge_start_s + params.surge_dur_s)
    return np.where(on, params.surge_mps2, 0.0)


def run_kalman(
    gyro_dps: np.ndarray,
    accel_tilt_deg: np.ndarray,
    use_accel: np.ndarray,
    dt: float,
    q_theta_dps: float,
    q_bias_dps_rts: float,
    r_deg: float,
    theta0: float,
) -> dict[str, np.ndarray]:
    """Two-state KF [theta (deg), bias (deg/s)]."""
    n = gyro_dps.shape[0]
    f = np.array([[1.0, -dt], [0.0, 1.0]])
    q = np.diag([(q_theta_dps * dt) ** 2, q_bias_dps_rts**2 * dt])
    r = r_deg**2
    x = np.array([theta0, 0.0])
    p = np.diag([r, 1.0])  # 1 (deg/s)^2 initial bias uncertainty
    th = np.empty(n)
    bb = np.empty(n)
    s_th = np.empty(n)
    s_b = np.empty(n)
    k_th = np.empty(n)
    for i in range(n):
        if i > 0:
            x = np.array([x[0] + (gyro_dps[i] - x[1]) * dt, x[1]])
            p = f @ p @ f.T + q
        k = np.zeros(2)
        if use_accel[i]:
            innov = wrap_180(accel_tilt_deg[i] - x[0])
            s = p[0, 0] + r  # H = [1, 0]
            k = p[:, 0] / s
            x = x + k * innov
            p = p - np.outer(k, p[0, :])
        th[i], bb[i] = x
        s_th[i], s_b[i] = np.sqrt(p[0, 0]), np.sqrt(p[1, 1])
        k_th[i] = k[0]
    return {"theta": th, "bias": bb, "sigma_theta": s_th, "sigma_bias": s_b, "gain_theta": k_th}


def simulate_complementary(params: ComplementaryParams) -> dict[str, object]:
    n = int(params.duration_s * params.fs_hz)
    dt = params.dt
    t = np.arange(n, dtype=float) * dt
    pitch = true_pitch_deg(params, t)
    rate = np.gradient(pitch, dt)

    rng = np.random.default_rng(params.seed)
    gyro = rate + params.gyro_bias_dps + rng.normal(0.0, params.gyro_noise_dps, n)

    th = pitch * DEG2RAD
    surge = surge_profile(params, t)
    fx = G0 * np.sin(th) + surge + rng.normal(0.0, params.accel_noise_mps2, n)
    fz = -G0 * np.cos(th) + rng.normal(0.0, params.accel_noise_mps2, n)
    accel_tilt = wrap_180(np.arctan2(fx, -fz) * RAD2DEG)
    f_norm = np.hypot(fx, fz)
    accel_ok = np.abs(f_norm - G0) <= params.gate_threshold_mps2 if params.gate_accel else np.ones(n, dtype=bool)

    gyro_only = np.cumsum(gyro) * dt
    a = params.alpha
    comp = np.zeros(n)
    comp[0] = accel_tilt[0]
    for i in range(1, n):
        pred = comp[i - 1] + gyro[i] * dt
        comp[i] = a * pred + (1.0 - a) * accel_tilt[i] if accel_ok[i] else pred

    kf = run_kalman(
        gyro, accel_tilt, accel_ok, dt,
        q_theta_dps=params.gyro_noise_dps,
        q_bias_dps_rts=params.kf_q_bias_dps_rts,
        r_deg=params.kf_r_deg,
        theta0=float(accel_tilt[0]),
    )
    k_ss = float(np.median(kf["gain_theta"][n // 2 :][accel_ok[n // 2 :]])) if np.any(accel_ok[n // 2 :]) else 0.0
    alpha_eq = 1.0 - k_ss

    def rms(x: np.ndarray) -> float:
        return float(np.sqrt(np.mean(wrap_180(x - pitch) ** 2)))

    return {
        "t_s": t,
        "pitch_true_deg": pitch,
        "gyro_rate_dps": gyro,
        "accel_tilt_deg": accel_tilt,
        "accel_used": accel_ok,
        "surge_mps2": surge,
        "gyro_only_deg": wrap_180(gyro_only),
        "comp_deg": wrap_180(comp),
        "kf_deg": wrap_180(kf["theta"]),
        "kf_sigma_deg": kf["sigma_theta"],
        "kf_bias_dps": kf["bias"],
        "kf_bias_sigma_dps": kf["sigma_bias"],
        "err_gyro_deg": wrap_180(gyro_only - pitch),
        "err_accel_deg": wrap_180(accel_tilt - pitch),
        "err_comp_deg": wrap_180(comp - pitch),
        "err_kf_deg": wrap_180(kf["theta"] - pitch),
        "rms_comp_deg": rms(comp),
        "rms_gyro_deg": rms(gyro_only),
        "rms_accel_deg": rms(accel_tilt),
        "rms_kf_deg": rms(kf["theta"]),
        "tau_s": filter_tau_s(params.alpha, dt),
        "fc_hz": crossover_hz(params.alpha, dt),
        "kf_gain_ss": k_ss,
        "kf_alpha_eq": alpha_eq,
        "kf_tau_eq_s": filter_tau_s(alpha_eq, dt),
        "kf_bias_final_dps": float(kf["bias"][-1]),
        "gated_fraction": float(1.0 - np.mean(accel_ok)),
    }


def process(params: ComplementaryParams) -> dict[str, object]:
    return simulate_complementary(params)
