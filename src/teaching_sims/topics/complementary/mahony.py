"""3-D nonlinear complementary (Mahony) attitude filter with bias estimation.

    q_dot   = 1/2 q (x) [0, w_gyro - b_hat + Kp e]
    b_hat_dot = -Ki e

with the correction ``e`` built from vector observations:

* accel: e_a = a_meas x v_pred, where v_pred = R^T [0, 0, -1] is the
  predicted specific-force direction (stationary, NED/FRD).
* mag (optional): e_m = m_meas x w_pred, where w_pred uses a reference that
  keeps only horizontal-plane (yaw) information.

Without a magnetometer, rotations about the vertical are unobservable: the
yaw error and the vertical gyro-bias estimate are never corrected.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from teaching_sims.core.imu import DEG2RAD, G0, RAD2DEG, wrap_180
from teaching_sims.topics.attitude.physics import (
    dcm_to_euler_zyx,
    euler_to_quat,
    quat_from_rotvec,
    quat_mul,
    quat_to_dcm,
)


@dataclass(frozen=True)
class MahonyParams:
    duration_s: float = 60.0
    fs_hz: float = 100.0
    # truth motion amplitudes / rates
    roll_amp_deg: float = 20.0
    pitch_amp_deg: float = 15.0
    yaw_rate_dps: float = 10.0
    motion_hz: float = 0.1
    # gyro errors (deg/s)
    bias_x_dps: float = 0.5
    bias_y_dps: float = -0.4
    bias_z_dps: float = 0.6
    gyro_noise_dps: float = 0.1
    accel_noise_mps2: float = 0.1
    mag_noise_ut: float = 0.5
    # forward surge (body x) during a window
    surge_mps2: float = 0.0
    surge_start_s: float = 20.0
    surge_dur_s: float = 10.0
    # filter
    kp: float = 1.0
    ki: float = 0.05
    use_mag: bool = False
    gate_accel: bool = False
    gate_threshold_mps2: float = 0.4
    seed: int = 0

    def __post_init__(self) -> None:
        if self.fs_hz <= 0 or self.duration_s <= 0:
            raise ValueError("fs_hz and duration_s must be positive")
        if self.kp < 0 or self.ki < 0:
            raise ValueError("gains must be >= 0")


B_NED = np.array([20.0, 0.0, 45.0])  # uT, mid-latitude field


def _truth_euler(p: MahonyParams, t: np.ndarray) -> np.ndarray:
    w = 2.0 * np.pi * p.motion_hz
    roll = p.roll_amp_deg * np.sin(w * t)
    pitch = p.pitch_amp_deg * np.sin(0.7 * w * t + 0.8)
    yaw = wrap_180(p.yaw_rate_dps * t)
    return np.column_stack([yaw, pitch, roll])


def simulate_mahony(p: MahonyParams) -> dict[str, object]:
    n = int(p.duration_s * p.fs_hz)
    dt = 1.0 / p.fs_hz
    t = np.arange(n) * dt
    eul = _truth_euler(p, t)
    q_true = np.array([euler_to_quat(*(e * DEG2RAD)) for e in eul])
    r_true = np.array([quat_to_dcm(q) for q in q_true])

    # body rates from consecutive truth attitudes: R_k^T R_{k+1} = exp([w dt]x)
    w_true = np.zeros((n, 3))
    for k in range(n - 1):
        d = r_true[k].T @ r_true[k + 1]
        w_true[k] = 0.5 * np.array([d[2, 1] - d[1, 2], d[0, 2] - d[2, 0], d[1, 0] - d[0, 1]]) / dt
    w_true[-1] = w_true[-2]

    rng = np.random.default_rng(p.seed)
    bias = np.array([p.bias_x_dps, p.bias_y_dps, p.bias_z_dps]) * DEG2RAD
    gyro = w_true + bias + rng.normal(0.0, p.gyro_noise_dps * DEG2RAD, (n, 3))
    surge = np.zeros(n)
    on = (t >= p.surge_start_s) & (t < p.surge_start_s + p.surge_dur_s)
    surge[on] = p.surge_mps2
    f_body = np.einsum("kji,j->ki", r_true, np.array([0.0, 0.0, -G0]))
    f_body[:, 0] += surge
    acc = f_body + rng.normal(0.0, p.accel_noise_mps2, (n, 3))
    mag = np.einsum("kji,j->ki", r_true, B_NED) + rng.normal(0.0, p.mag_noise_ut, (n, 3))

    q = euler_to_quat(0.0, 0.0, 0.0)  # start level, facing north
    b_hat = np.zeros(3)
    est = np.empty((n, 3))
    bias_est = np.empty((n, 3))
    used = np.ones(n, dtype=bool)
    for k in range(n):
        r_hat = quat_to_dcm(q)
        e = np.zeros(3)
        a = acc[k]
        a_ok = (not p.gate_accel) or abs(np.linalg.norm(a) - G0) <= p.gate_threshold_mps2
        used[k] = a_ok
        if a_ok:
            v_pred = r_hat.T @ np.array([0.0, 0.0, -1.0])
            e += np.cross(a / np.linalg.norm(a), v_pred)
        if p.use_mag:
            m = mag[k] / np.linalg.norm(mag[k])
            h = r_hat @ m
            b_ref = np.array([np.hypot(h[0], h[1]), 0.0, h[2]])
            w_pred = r_hat.T @ b_ref
            e += np.cross(m, w_pred)
        b_hat = b_hat - p.ki * e * dt
        w = gyro[k] - b_hat + p.kp * e
        q = quat_mul(q, quat_from_rotvec(w * dt))
        q = q / np.linalg.norm(q)
        est[k] = np.array(dcm_to_euler_zyx(quat_to_dcm(q))) * RAD2DEG
        bias_est[k] = b_hat * RAD2DEG

    err = wrap_180(est - eul)
    tail = t >= 0.75 * p.duration_s
    return {
        "t_s": t,
        "euler_true_deg": eul,  # columns yaw, pitch, roll
        "euler_est_deg": est,
        "euler_err_deg": err,
        "bias_true_dps": bias * RAD2DEG,
        "bias_est_dps": bias_est,
        "accel_used": used,
        "surge_mps2": surge,
        "rms_tail_deg": np.sqrt(np.mean(err[tail] ** 2, axis=0)),
        "final_err_deg": err[-1],
        "r_true": r_true,
    }


def estimated_dcm(out: dict, i: int) -> np.ndarray:
    from teaching_sims.topics.attitude.physics import euler_zyx_to_dcm

    y, p, r = out["euler_est_deg"][i] * DEG2RAD
    return euler_zyx_to_dcm(y, p, r)
