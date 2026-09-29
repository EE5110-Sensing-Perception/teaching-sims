"""Accelerometer teaching physics: specific force, tilt, errors, calibration, lever arm.

Conventions: NED navigation frame, FRD body frame, specific force
``f = a - g`` so a level, stationary sensor reads ``f = [0, 0, -g]``.

Measurement model (per sample)::

    f_meas = (I + S) M f_true + b + n + vibration

with scale-factor errors ``S`` (diagonal), non-orthogonality ``M`` (small
off-diagonal terms), bias ``b`` and white noise ``n``. A lever arm ``r``
between the rotation centre and the IMU adds ``w x (w x r) + alpha x r``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from teaching_sims.core.imu import DEG2RAD, G0, RAD2DEG
from teaching_sims.core.imu_errors import misalignment_matrix
from teaching_sims.topics.attitude.physics import euler_zyx_to_dcm


@dataclass(frozen=True)
class AccelParams:
    """Static / quasi-static accelerometer experiment in body frame."""

    yaw_deg: float = 0.0
    roll_deg: float = 10.0
    pitch_deg: float = -5.0
    # True linear acceleration of the rotation centre, body axes (contaminates tilt)
    ax_mps2: float = 0.0
    ay_mps2: float = 0.0
    az_mps2: float = 0.0
    # Deterministic sensor errors
    bias_x_mps2: float = 0.0
    bias_y_mps2: float = 0.0
    bias_z_mps2: float = 0.0
    scale_x_pct: float = 0.0
    scale_y_pct: float = 0.0
    scale_z_pct: float = 0.0
    mis_xy_mrad: float = 0.0  # sensor x sees true y
    mis_xz_mrad: float = 0.0  # sensor x sees true z
    mis_yz_mrad: float = 0.0  # sensor y sees true z
    noise_mps2: float = 0.02
    duration_s: float = 4.0
    fs_hz: float = 100.0
    # Vibration (sinusoid on body X) to show averaging vs tilt
    vibe_amp_mps2: float = 0.0
    vibe_hz: float = 25.0
    # Moving-average window for the averaged tilt estimate
    avg_window_s: float = 1.0
    # Lever arm: IMU offset from the rotation centre (body, m) and body yaw motion
    lever_x_m: float = 0.0
    lever_y_m: float = 0.0
    lever_z_m: float = 0.0
    yaw_rate_dps: float = 0.0
    yaw_accel_dps2: float = 0.0
    compensate_lever: bool = False
    seed: int = 0

    def __post_init__(self) -> None:
        if self.fs_hz <= 0 or self.duration_s <= 0:
            raise ValueError("fs_hz and duration_s must be positive")
        if abs(self.pitch_deg) >= 89.0:
            raise ValueError("pitch_deg must be in (-89, 89) for this demo")
        if self.avg_window_s <= 0:
            raise ValueError("avg_window_s must be positive")

    @property
    def bias(self) -> np.ndarray:
        return np.array([self.bias_x_mps2, self.bias_y_mps2, self.bias_z_mps2], dtype=float)

    def gain_matrix(self) -> np.ndarray:
        """(I + S) M: maps true specific force to sensed (before bias)."""
        s = np.diag([1 + self.scale_x_pct / 100, 1 + self.scale_y_pct / 100, 1 + self.scale_z_pct / 100])
        m = misalignment_matrix((self.mis_xy_mrad, self.mis_xz_mrad, 0.0, self.mis_yz_mrad, 0.0, 0.0))
        return s @ m


def gravity_specific_force_body(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    """Specific force of a stationary body: R^T [0, 0, -g]."""
    r_nb = euler_zyx_to_dcm(yaw_deg * DEG2RAD, pitch_deg * DEG2RAD, roll_deg * DEG2RAD)
    return r_nb.T @ np.array([0.0, 0.0, -G0])


def lever_arm_accel(params: AccelParams) -> np.ndarray:
    """w x (w x r) + alpha x r for body rotation about z (body axes, m/s^2)."""
    w = np.array([0.0, 0.0, params.yaw_rate_dps * DEG2RAD])
    alpha = np.array([0.0, 0.0, params.yaw_accel_dps2 * DEG2RAD])
    r = np.array([params.lever_x_m, params.lever_y_m, params.lever_z_m])
    return np.cross(w, np.cross(w, r)) + np.cross(alpha, r)


def true_specific_force_body(params: AccelParams) -> np.ndarray:
    """True specific force at the IMU: gravity + centre acceleration + lever arm."""
    f = gravity_specific_force_body(params.yaw_deg, params.pitch_deg, params.roll_deg)
    f = f + np.array([params.ax_mps2, params.ay_mps2, params.az_mps2], dtype=float)
    return f + lever_arm_accel(params)


def tilt_from_accel(fx: float, fy: float, fz: float) -> tuple[float, float]:
    """Roll/pitch (deg) from specific force (FRD body, f = a - g).

    roll = atan2(-fy, -fz), pitch = atan2(fx, sqrt(fy^2 + fz^2)).
    Yaw is unobservable from gravity alone.
    """
    roll = np.arctan2(-fy, -fz)
    pitch = np.arctan2(fx, np.hypot(fy, fz))
    return float(roll * RAD2DEG), float(pitch * RAD2DEG)


def tilt_from_accel_array(f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    roll = np.arctan2(-f[:, 1], -f[:, 2]) * RAD2DEG
    pitch = np.arctan2(f[:, 0], np.hypot(f[:, 1], f[:, 2])) * RAD2DEG
    return roll, pitch


def measure(params: AccelParams, f_true: np.ndarray, rng: np.random.Generator, n: int) -> np.ndarray:
    """Apply the sensor error model to a constant true specific force."""
    g = params.gain_matrix()
    meas = np.tile(g @ f_true + params.bias, (n, 1))
    meas += rng.normal(0.0, params.noise_mps2, size=(n, 3))
    return meas


def apply_calibration(meas: np.ndarray, cal: dict[str, np.ndarray] | None) -> np.ndarray:
    """Invert an estimated (gain, bias) model: f = G^-1 (y - b)."""
    if cal is None:
        return meas
    ginv = np.linalg.inv(cal["gain"])
    return (meas - cal["bias"]) @ ginv.T


def moving_average(x: np.ndarray, n: int) -> np.ndarray:
    """Causal boxcar average (shorter window during start-up)."""
    n = max(1, int(n))
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = np.empty_like(x, dtype=float)
    idx = np.arange(1, x.shape[0] + 1)
    lo = np.maximum(0, idx - n)
    out[:] = (c[idx] - c[lo]) / (idx - lo)
    return out


def simulate_accel(params: AccelParams, cal: dict[str, np.ndarray] | None = None) -> dict[str, object]:
    """Time series of noisy accel + tilt estimates."""
    n = int(params.duration_s * params.fs_hz)
    t = np.arange(n, dtype=float) / params.fs_hz
    f_true = true_specific_force_body(params)
    rng = np.random.default_rng(params.seed)
    meas = measure(params, f_true, rng, n)
    meas[:, 0] += params.vibe_amp_mps2 * np.sin(2.0 * np.pi * params.vibe_hz * t)
    lever = lever_arm_accel(params)
    if params.compensate_lever:
        meas = meas - lever  # uses known rate + geometry
    meas = apply_calibration(meas, cal)

    rolls, pitches = tilt_from_accel_array(meas)
    n_avg = int(round(params.avg_window_s * params.fs_hz))
    roll_avg = moving_average(rolls, n_avg)
    pitch_avg = moving_average(pitches, n_avg)

    mean_f = meas.mean(axis=0)
    roll_hat, pitch_hat = tilt_from_accel(mean_f[0], mean_f[1], mean_f[2])

    return {
        "t_s": t,
        "fx": meas[:, 0],
        "fy": meas[:, 1],
        "fz": meas[:, 2],
        "roll_est_deg": rolls,
        "pitch_est_deg": pitches,
        "roll_avg_deg": roll_avg,
        "pitch_avg_deg": pitch_avg,
        "true_f_body": f_true,
        "mean_f_body": mean_f,
        "lever_accel": lever,
        "roll_mean_deg": roll_hat,
        "pitch_mean_deg": pitch_hat,
        "roll_err_deg": roll_hat - params.roll_deg,
        "pitch_err_deg": pitch_hat - params.pitch_deg,
        "true_yaw_deg": params.yaw_deg,
        "true_roll_deg": params.roll_deg,
        "true_pitch_deg": params.pitch_deg,
    }


def tilt_error_curve(params: AccelParams, disturbance: np.ndarray) -> dict[str, np.ndarray]:
    """Pitch error vs an extra x-axis specific force (bias, surge or lever arm - all identical).

    Evaluated on the noise-free gravity vector at the current pose.
    """
    f = gravity_specific_force_body(params.yaw_deg, params.pitch_deg, params.roll_deg)
    err = []
    for d in np.asarray(disturbance, dtype=float):
        _, p = tilt_from_accel(f[0] + d, f[1], f[2])
        err.append(p - params.pitch_deg)
    return {"d_mps2": np.asarray(disturbance, dtype=float), "pitch_err_deg": np.asarray(err)}


# --- six-position calibration --------------------------------------------------------

SIX_POSES: tuple[tuple[str, tuple[float, float, float]], ...] = (
    # (label, yaw/pitch/roll deg) - the named body axis points UP, so it reads +g
    ("x up", (0.0, 89.9, 0.0)),
    ("x down", (0.0, -89.9, 0.0)),
    ("y up", (0.0, 0.0, -90.0)),
    ("y down", (0.0, 0.0, 90.0)),
    ("z up", (0.0, 0.0, 180.0)),
    ("z down (level)", (0.0, 0.0, 0.0)),
)


def six_position_calibration(
    params: AccelParams,
    samples_per_pose: int = 200,
    seed: int = 1,
) -> dict[str, object]:
    """Simulate a six-position tumble test and fit y = G f + b by least squares.

    Each pose is ideally one axis up or down, so the true specific force is
    +/- g e_k. The 6x3 readings over-determine the 4 unknowns per sensor axis
    (one row of G plus one bias).
    """
    rng = np.random.default_rng(seed)
    f_true, y_mean, labels = [], [], []
    for label, (yw, pt, rl) in SIX_POSES:
        f = gravity_specific_force_body(yw, pt, rl)
        y = measure(params, f, rng, samples_per_pose).mean(axis=0)
        f_true.append(f)
        y_mean.append(y)
        labels.append(label)
    f_true = np.asarray(f_true)
    y_mean = np.asarray(y_mean)
    a = np.hstack([f_true, np.ones((6, 1))])  # 6 x 4
    theta, *_ = np.linalg.lstsq(a, y_mean, rcond=None)  # 4 x 3
    gain = theta[:3, :].T
    bias = theta[3, :]
    resid = y_mean - a @ theta
    return {
        "labels": labels,
        "f_true": f_true,
        "y_mean": y_mean,
        "gain": gain,
        "bias": bias,
        "true_gain": params.gain_matrix(),
        "true_bias": params.bias,
        "residual_rms": float(np.sqrt(np.mean(resid**2))),
    }


def process(params: AccelParams, cal: dict[str, np.ndarray] | None = None) -> dict[str, object]:
    return simulate_accel(params, cal)
