"""Planar strapdown INS with a tilt (gravity-leakage) channel and simple aiding.

Mechanisation per step (NED, flat Earth, horizontal channels):

    heading   psi_hat  = integral of the yaw gyro          (or truth if perfect_attitude)
    tilt err  theta_e  = theta0 + b_pitch t                 (pitch misalignment)
    f_nav     = R(psi_hat) [f_x cos(theta_e) - g sin(theta_e),  f_y]
    v        += f_nav dt          (gravity already removed above)
    p        += v dt

Unaided error growth for each source (position error):

    initial velocity error dv   -> dv t
    accel bias b_a              -> b_a t^2 / 2
    initial tilt theta0         -> g theta0 t^2 / 2     (0.1 deg  ~ 1.7 mg of accel bias)
    pitch gyro bias b_g         -> g b_g t^3 / 6        (the famous t^3 term)
    yaw gyro bias eps, speed v  -> v eps t^2 / 2        (cross-track, straight path)

Aiding:

* ZUPT: when the vehicle is detected stationary, reset velocity to zero.
  Detector = oracle (true stops) or IMU thresholds on |f_horizontal| and |w|.
  The IMU detector cannot tell a stop from constant-velocity cruise.
* Position fixes (GNSS / odometry) every N seconds, fused by a per-axis
  [p, v] Kalman filter (loosely coupled).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

import numpy as np

from teaching_sims.core.imu import DEG2RAD, G0, RAD2DEG, wrap_180
from teaching_sims.core.imu_errors import GRADE_PRESETS


class PathProfile(str, Enum):
    STRAIGHT = "straight"
    CIRCLE = "circle"
    STOP_AND_GO = "stop_and_go"


class Aiding(str, Enum):
    NONE = "none"
    ZUPT = "zupt"
    POSITION = "position"


class ZuptDetector(str, Enum):
    ORACLE = "oracle"
    IMU = "imu"


@dataclass(frozen=True)
class INSParams:
    """Planar (North-East) INS; heading from yaw-rate gyro, accel in body x/y."""

    profile: PathProfile = PathProfile.CIRCLE
    speed_mps: float = 5.0
    radius_m: float = 40.0
    duration_s: float = 40.0
    fs_hz: float = 50.0
    gyro_bias_dps: float = 0.2  # yaw gyro
    accel_bias_x_mps2: float = 0.05  # body forward
    accel_bias_y_mps2: float = 0.0  # body right
    accel_noise_mps2: float = 0.02
    gyro_noise_dps: float = 0.05
    perfect_attitude: bool = False
    # Tilt channel
    tilt0_deg: float = 0.0  # initial pitch misalignment
    gyro_pitch_bias_dps: float = 0.0
    init_vel_err_mps: float = 0.0  # forward velocity error at start
    # Aiding
    aiding: Aiding = Aiding.NONE
    zupt_detector: ZuptDetector = ZuptDetector.ORACLE
    zupt_acc_thr_mps2: float = 0.15
    zupt_gyro_thr_dps: float = 1.0
    fix_interval_s: float = 5.0
    fix_sigma_m: float = 2.0
    seed: int = 0

    def __post_init__(self) -> None:
        if self.fs_hz <= 0 or self.duration_s <= 0:
            raise ValueError("fs_hz and duration_s must be positive")
        if self.speed_mps < 0:
            raise ValueError("speed_mps must be >= 0")
        if self.fix_interval_s <= 0 or self.fix_sigma_m <= 0:
            raise ValueError("fix_interval_s and fix_sigma_m must be positive")


def params_for_grade(base: INSParams, grade: str, calibrated: bool = True) -> INSParams:
    """Residual biases for an IMU grade: bias instability if calibrated, else turn-on bias."""
    spec = GRADE_PRESETS[grade]
    g_bias_dph = spec.gyro_bi_dph if calibrated else spec.gyro_bias_dph
    a_bias_mps2 = (spec.accel_bi_ug * 1e-6 if calibrated else spec.accel_bias_mg * 1e-3) * G0
    return replace(
        base,
        gyro_bias_dps=g_bias_dph / 3600.0,
        gyro_pitch_bias_dps=g_bias_dph / 3600.0,
        accel_bias_x_mps2=a_bias_mps2,
        accel_bias_y_mps2=0.0,
        accel_noise_mps2=spec.accel_noise_ug_rthz * 1e-6 * G0 * np.sqrt(base.fs_hz),
        gyro_noise_dps=spec.gyro_arw_dpsh / 60.0 * np.sqrt(base.fs_hz),
    )


def _truth(params: INSParams, t: np.ndarray) -> dict[str, np.ndarray]:
    n = len(t)
    dt = t[1] - t[0] if n > 1 else 1.0
    zeros = np.zeros(n)
    if params.profile == PathProfile.STRAIGHT:
        v = np.full(n, params.speed_mps)
        return {"north": params.speed_mps * t, "east": zeros.copy(), "hdg": zeros.copy(), "ax": zeros.copy(),
                "ay": zeros.copy(), "speed": v}

    if params.profile == PathProfile.STOP_AND_GO:
        # accelerate 0-5 s, cruise to 25 s, brake to 30 s, stop
        ax = np.zeros(n)
        ax[t < 5.0] = params.speed_mps / 5.0
        ax[(t >= 25.0) & (t < 30.0)] = -params.speed_mps / 5.0
        v = np.clip(np.cumsum(ax) * dt, 0.0, None)
        v[t >= 30.0] = 0.0
        north = np.concatenate(([0.0], np.cumsum(v[:-1]) * dt))
        return {"north": north, "east": zeros.copy(), "hdg": zeros.copy(), "ax": ax, "ay": zeros.copy(),
                "speed": v}

    r = max(params.radius_m, 1e-9)
    omega = params.speed_mps / r  # rad/s, clockwise seen from above (heading increases)
    return {
        "north": r * np.sin(omega * t),
        "east": r * (1.0 - np.cos(omega * t)),
        "hdg": wrap_180(omega * t * RAD2DEG),
        "ax": zeros.copy(),
        "ay": np.full(n, params.speed_mps**2 / r),  # centripetal, body right
        "speed": np.full(n, params.speed_mps),
    }


def error_growth_reference(params: INSParams, t: np.ndarray) -> dict[str, np.ndarray]:
    """Analytic unaided position-error curves for each error source alone."""
    g = G0
    return {
        "init velocity": np.abs(params.init_vel_err_mps) * t,
        "accel bias": 0.5 * np.hypot(params.accel_bias_x_mps2, params.accel_bias_y_mps2) * t**2,
        "initial tilt": 0.5 * g * np.abs(params.tilt0_deg * DEG2RAD) * t**2,
        "pitch gyro bias": g * np.abs(params.gyro_pitch_bias_dps * DEG2RAD) * t**3 / 6.0,
        "yaw gyro bias": 0.5 * params.speed_mps * np.abs(params.gyro_bias_dps * DEG2RAD) * t**2,
    }


def simulate_ins(params: INSParams) -> dict[str, object]:
    n = int(params.duration_s * params.fs_hz)
    dt = 1.0 / params.fs_hz
    t = np.arange(n, dtype=float) * dt
    truth = _truth(params, t)
    n_true, e_true, hdg_true = truth["north"], truth["east"], truth["hdg"]
    speed = truth["speed"]
    yaw_rate_true = np.gradient(np.unwrap(hdg_true * DEG2RAD), dt) * RAD2DEG

    rng = np.random.default_rng(params.seed)
    gyro = yaw_rate_true + params.gyro_bias_dps + rng.normal(0.0, params.gyro_noise_dps, n)
    ax_m = truth["ax"] + params.accel_bias_x_mps2 + rng.normal(0.0, params.accel_noise_mps2, n)
    ay_m = truth["ay"] + params.accel_bias_y_mps2 + rng.normal(0.0, params.accel_noise_mps2, n)

    hdg_est = hdg_true.copy() if params.perfect_attitude else wrap_180(np.cumsum(gyro) * dt)
    tilt_err = params.tilt0_deg * DEG2RAD + params.gyro_pitch_bias_dps * DEG2RAD * t

    # ZUPT detection
    if params.aiding == Aiding.ZUPT:
        if params.zupt_detector == ZuptDetector.ORACLE:
            zupt = speed < 1e-6
        else:
            zupt = (np.hypot(ax_m, ay_m) < params.zupt_acc_thr_mps2) & (np.abs(gyro) < params.zupt_gyro_thr_dps)
    else:
        zupt = np.zeros(n, dtype=bool)

    # Position fixes
    fix_every = max(1, int(round(params.fix_interval_s * params.fs_hz)))
    fix_mask = np.zeros(n, dtype=bool)
    if params.aiding == Aiding.POSITION:
        fix_mask[fix_every::fix_every] = True
    fixes_n = n_true + rng.normal(0.0, params.fix_sigma_m, n)
    fixes_e = e_true + rng.normal(0.0, params.fix_sigma_m, n)

    # Per-axis [p, v] KF matrices (position aiding)
    f_mat = np.array([[1.0, dt], [0.0, 1.0]])
    sig_a = max(params.accel_noise_mps2, 0.05) + abs(params.accel_bias_x_mps2) + G0 * abs(params.tilt0_deg * DEG2RAD)
    q = sig_a**2 * np.array([[dt**4 / 4, dt**3 / 2], [dt**3 / 2, dt**2]])
    r_fix = params.fix_sigma_m**2
    p_cov = [np.diag([1.0, 1.0]), np.diag([1.0, 1.0])]

    vn = np.zeros(n)
    ve = np.zeros(n)
    pn = np.zeros(n)
    pe = np.zeros(n)
    psi0 = hdg_true[0] * DEG2RAD
    v0 = speed[0] + params.init_vel_err_mps
    vn[0], ve[0] = v0 * np.cos(psi0), v0 * np.sin(psi0)
    for i in range(1, n):
        psi = hdg_est[i] * DEG2RAD
        c, s = np.cos(psi), np.sin(psi)
        f_fwd = ax_m[i] * np.cos(tilt_err[i]) - G0 * np.sin(tilt_err[i])
        an = f_fwd * c - ay_m[i] * s
        ae = f_fwd * s + ay_m[i] * c
        vn[i] = vn[i - 1] + an * dt
        ve[i] = ve[i - 1] + ae * dt
        pn[i] = pn[i - 1] + vn[i] * dt
        pe[i] = pe[i - 1] + ve[i] * dt
        if zupt[i]:
            vn[i] = ve[i] = 0.0
        if params.aiding == Aiding.POSITION:
            for k in range(2):
                p_cov[k] = f_mat @ p_cov[k] @ f_mat.T + q
            if fix_mask[i]:
                for k, (pos, vel, fix) in enumerate(((pn, vn, fixes_n), (pe, ve, fixes_e))):
                    pk = p_cov[k]
                    gain = pk[:, 0] / (pk[0, 0] + r_fix)
                    innov = fix[i] - pos[i]
                    pos[i] += gain[0] * innov
                    vel[i] += gain[1] * innov
                    p_cov[k] = pk - np.outer(gain, pk[0, :])

    v_true_n = speed * np.cos(hdg_true * DEG2RAD)
    v_true_e = speed * np.sin(hdg_true * DEG2RAD)
    pos_err = np.hypot(pn - n_true, pe - e_true)
    vel_err = np.hypot(vn - v_true_n, ve - v_true_e)
    return {
        "t_s": t,
        "north_true_m": n_true,
        "east_true_m": e_true,
        "north_est_m": pn,
        "east_est_m": pe,
        "hdg_true_deg": hdg_true,
        "hdg_est_deg": hdg_est,
        "speed_true_mps": speed,
        "pos_err_m": pos_err,
        "vel_err_mps": vel_err,
        "tilt_err_deg": tilt_err * RAD2DEG,
        "final_pos_err_m": float(pos_err[-1]),
        "max_pos_err_m": float(np.max(pos_err)),
        "ax_meas": ax_m,
        "ay_meas": ay_m,
        "gyro_meas_dps": gyro,
        "zupt_mask": zupt,
        "fix_mask": fix_mask,
        "fix_n": fixes_n,
        "fix_e": fixes_e,
        "references": error_growth_reference(params, t),
    }


def process(params: INSParams) -> dict[str, object]:
    return simulate_ins(params)
