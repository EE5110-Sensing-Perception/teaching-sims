"""Frames and rotations teaching physics.

Covers:

* rotation representations - ZYX Euler, DCM, unit quaternion, axis-angle
* frame conventions - aerospace NED/FRD vs ROS REP-103 ENU/FLU
* composition order - intrinsic Z-Y'-X'' vs extrinsic X-Y-Z vs swapped order
* the Euler singularity - extraction sensitivity and Euler-rate gain ~ 1/cos(pitch)
* attitude kinematics - integrating body rates with exp-map vs first-order DCM,
  renormalisation, and coning error from coarse steps

All DCMs are active body-to-navigation rotations: ``v_nav = R @ v_body``.
Quaternions are Hamilton, scalar-first ``[w, x, y, z]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from teaching_sims.core.imu import DEG2RAD, RAD2DEG, wrap_180


class Convention(str, Enum):
    NED_FRD = "ned_frd"  # aerospace: North-East-Down, body Forward-Right-Down
    ENU_FLU = "enu_flu"  # ROS REP-103: East-North-Up, body Forward-Left-Up


class Sequence(str, Enum):
    INTRINSIC_ZYX = "intrinsic_zyx"  # yaw about Z, pitch about new Y', roll about new X''
    EXTRINSIC_XYZ = "extrinsic_xyz"  # roll about fixed X, pitch about fixed Y, yaw about fixed Z
    INTRINSIC_XYZ = "intrinsic_xyz"  # roll first about body X, then Y', then Z'' - a different pose


class Integrator(str, Enum):
    QUAT_EXP = "quat_exp"  # exact for constant rate over each step
    DCM_EULER = "dcm_euler"  # R <- R (I + [w]x dt): first order, loses orthonormality


@dataclass(frozen=True)
class AttitudeParams:
    """Pose, sequence and rate-integration settings for the attitude demo."""

    yaw_deg: float = 20.0
    pitch_deg: float = 15.0
    roll_deg: float = -10.0
    convention: Convention = Convention.NED_FRD
    sequence: Sequence = Sequence.INTRINSIC_ZYX
    # Gimbal-lock scan
    animate_pitch: bool = False
    pitch_scan_deg: float = 89.0
    perturb_deg: float = 0.5
    n_samples: int = 181
    # Rate integration (kinematics)
    wx_dps: float = 0.0
    wy_dps: float = 0.0
    wz_dps: float = 30.0
    coning_amp_dps: float = 0.0  # body rate [a cos(Wt), a sin(Wt), 0] on top of w
    coning_hz: float = 2.0
    int_duration_s: float = 10.0
    int_dt_s: float = 0.02
    integrator: Integrator = Integrator.QUAT_EXP
    renormalize: bool = False
    seed: int = 0

    def __post_init__(self) -> None:
        if self.n_samples < 3:
            raise ValueError("n_samples must be >= 3")
        if self.int_dt_s <= 0 or self.int_duration_s <= 0:
            raise ValueError("int_dt_s and int_duration_s must be positive")


# --- elementary rotations and Euler ------------------------------------------------


def rot_x(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def rot_y(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def rot_z(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def euler_zyx_to_dcm(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """Body-to-NED DCM for ZYX (yaw-pitch-roll) aerospace sequence: Rz Ry Rx."""
    cy, sy = np.cos(yaw), np.sin(yaw)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll), np.sin(roll)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=float,
    )


def dcm_to_euler_zyx(r: np.ndarray) -> tuple[float, float, float]:
    """Extract yaw, pitch, roll (rad). Pitch near +/-90 is singular."""
    sp = float(np.clip(-r[2, 0], -1.0, 1.0))
    pitch = np.arcsin(sp)
    if abs(sp) < 0.999999:
        roll = np.arctan2(r[2, 1], r[2, 2])
        yaw = np.arctan2(r[1, 0], r[0, 0])
    else:
        # Gimbal lock: only yaw -/+ roll is defined; pick roll = 0
        roll = 0.0
        yaw = np.arctan2(-r[0, 1], r[1, 1])
    return float(yaw), float(pitch), float(roll)


# --- quaternions -----------------------------------------------------------------


def euler_to_quat(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """Quaternion [w, x, y, z] for ZYX Euler."""
    cy, sy = np.cos(yaw * 0.5), np.sin(yaw * 0.5)
    cp, sp = np.cos(pitch * 0.5), np.sin(pitch * 0.5)
    cr, sr = np.cos(roll * 0.5), np.sin(roll * 0.5)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    q = np.array([w, x, y, z], dtype=float)
    return q / np.linalg.norm(q)


def quat_to_dcm(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def dcm_to_quat(r: np.ndarray) -> np.ndarray:
    """Shepperd's method; returns the representative with w >= 0."""
    tr = float(np.trace(r))
    cands = np.array([tr, r[0, 0], r[1, 1], r[2, 2]])
    k = int(np.argmax(cands))
    if k == 0:
        w = 0.5 * np.sqrt(1.0 + tr)
        q = np.array([w, (r[2, 1] - r[1, 2]) / (4 * w), (r[0, 2] - r[2, 0]) / (4 * w), (r[1, 0] - r[0, 1]) / (4 * w)])
    elif k == 1:
        x = 0.5 * np.sqrt(1.0 + 2 * r[0, 0] - tr)
        q = np.array([(r[2, 1] - r[1, 2]) / (4 * x), x, (r[0, 1] + r[1, 0]) / (4 * x), (r[0, 2] + r[2, 0]) / (4 * x)])
    elif k == 2:
        y = 0.5 * np.sqrt(1.0 + 2 * r[1, 1] - tr)
        q = np.array([(r[0, 2] - r[2, 0]) / (4 * y), (r[0, 1] + r[1, 0]) / (4 * y), y, (r[1, 2] + r[2, 1]) / (4 * y)])
    else:
        z = 0.5 * np.sqrt(1.0 + 2 * r[2, 2] - tr)
        q = np.array([(r[1, 0] - r[0, 1]) / (4 * z), (r[0, 2] + r[2, 0]) / (4 * z), (r[1, 2] + r[2, 1]) / (4 * z), z])
    q = q / np.linalg.norm(q)
    return q if q[0] >= 0 else -q


def quat_mul(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Hamilton product p (x) q."""
    pw, px, py, pz = p
    qw, qx, qy, qz = q
    return np.array(
        [
            pw * qw - px * qx - py * qy - pz * qz,
            pw * qx + px * qw + py * qz - pz * qy,
            pw * qy - px * qz + py * qw + pz * qx,
            pw * qz + px * qy - py * qx + pz * qw,
        ]
    )


def quat_from_rotvec(phi: np.ndarray) -> np.ndarray:
    """Exponential map: rotation vector (rad) -> unit quaternion."""
    phi = np.asarray(phi, dtype=float)
    ang = float(np.linalg.norm(phi))
    if ang < 1e-12:
        return np.array([1.0, 0.5 * phi[0], 0.5 * phi[1], 0.5 * phi[2]]) / np.sqrt(1 + 0.25 * ang * ang)
    ax = phi / ang
    return np.concatenate(([np.cos(0.5 * ang)], np.sin(0.5 * ang) * ax))


def quat_axis_angle(q: np.ndarray) -> tuple[np.ndarray, float]:
    """Unit rotation axis and angle (deg, in [0, 180]) of a unit quaternion."""
    q = np.asarray(q, dtype=float)
    if q[0] < 0:
        q = -q  # q and -q are the same rotation
    s = float(np.linalg.norm(q[1:]))
    ang = 2.0 * np.arctan2(s, q[0])
    axis = q[1:] / s if s > 1e-12 else np.array([1.0, 0.0, 0.0])
    return axis, float(ang * RAD2DEG)


def rotation_angle_deg(r_a: np.ndarray, r_b: np.ndarray) -> float:
    """Angle of the relative rotation R_a^T R_b (deg)."""
    c = (float(np.trace(r_a.T @ r_b)) - 1.0) * 0.5
    return float(np.arccos(np.clip(c, -1.0, 1.0)) * RAD2DEG)


def skew(w: np.ndarray) -> np.ndarray:
    return np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])


def orthonormalize(r: np.ndarray) -> np.ndarray:
    """Closest rotation matrix (SVD projection onto SO(3))."""
    u, _, vt = np.linalg.svd(r)
    m = u @ vt
    if np.linalg.det(m) < 0:
        u[:, -1] *= -1
        m = u @ vt
    return m


# --- conventions -------------------------------------------------------------------

# NED <-> ENU swaps the first two axes and flips the third (self-inverse).
T_NED_ENU = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
# FRD <-> FLU flips y and z (self-inverse).
T_FRD_FLU = np.diag([1.0, -1.0, -1.0])


def dcm_ned_frd_to_enu_flu(r_ned_frd: np.ndarray) -> np.ndarray:
    """Same physical attitude, re-expressed as R^{ENU}_{FLU}."""
    return T_NED_ENU @ r_ned_frd @ T_FRD_FLU


def euler_ned_to_ros(yaw_deg: float, pitch_deg: float, roll_deg: float) -> tuple[float, float, float]:
    """ZYX Euler of the same pose in ROS (ENU/FLU).

    Yaw is measured from East, counter-clockwise; nose-up pitch is negative;
    roll keeps its sign.
    """
    return float(wrap_180(90.0 - yaw_deg)), -pitch_deg, roll_deg


def nav_axis_labels(conv: Convention) -> tuple[str, str, str]:
    return ("N", "E", "D") if conv == Convention.NED_FRD else ("E", "N", "U")


def body_axis_labels(conv: Convention) -> tuple[str, str, str]:
    return ("x fwd", "y right", "z down") if conv == Convention.NED_FRD else ("x fwd", "y left", "z up")


def body_axes_ned(yaw_deg: float, pitch_deg: float, roll_deg: float) -> dict[str, np.ndarray]:
    """Unit body axes expressed in NED."""
    r = euler_zyx_to_dcm(yaw_deg * DEG2RAD, pitch_deg * DEG2RAD, roll_deg * DEG2RAD)
    return {"x": r[:, 0], "y": r[:, 1], "z": r[:, 2], "dcm": r}


# --- composition order -----------------------------------------------------------------


def sequence_frames(
    yaw_deg: float,
    pitch_deg: float,
    roll_deg: float,
    seq: Sequence = Sequence.INTRINSIC_ZYX,
    n_per_stage: int = 40,
) -> dict[str, object]:
    """Intermediate DCMs while building the rotation one elementary step at a time.

    Returns ``frames`` (N, 3, 3), ``stage`` (N,) index 0..2, ``axis_nav`` (N, 3):
    the rotation axis in nav coordinates at each frame, and ``labels``.
    """
    y, p, r = yaw_deg * DEG2RAD, pitch_deg * DEG2RAD, roll_deg * DEG2RAD
    s = np.linspace(0.0, 1.0, n_per_stage)
    frames: list[np.ndarray] = []
    stage: list[int] = []
    axis_nav: list[np.ndarray] = []
    ex, ey, ez = np.eye(3)

    if seq == Sequence.INTRINSIC_ZYX:
        steps = [(rot_z, y, ez, "yaw about Z"), (rot_y, p, ey, "pitch about Y'"), (rot_x, r, ex, "roll about X''")]
        pre = np.eye(3)
        for k, (fn, ang, ax_b, _) in enumerate(steps):
            for si in s:
                frames.append(pre @ fn(si * ang))
                stage.append(k)
                axis_nav.append(pre @ ax_b)  # intrinsic: axis moves with the body
            pre = pre @ fn(ang)
    elif seq == Sequence.EXTRINSIC_XYZ:
        steps = [(rot_x, r, ex, "roll about fixed X"), (rot_y, p, ey, "pitch about fixed Y"), (rot_z, y, ez, "yaw about fixed Z")]
        post = np.eye(3)
        for k, (fn, ang, ax_n, _) in enumerate(steps):
            for si in s:
                frames.append(fn(si * ang) @ post)
                stage.append(k)
                axis_nav.append(ax_n)  # extrinsic: axis fixed in the nav frame
            post = fn(ang) @ post
    else:  # INTRINSIC_XYZ: roll first about body axes
        steps = [(rot_x, r, ex, "roll about X"), (rot_y, p, ey, "pitch about Y'"), (rot_z, y, ez, "yaw about Z''")]
        pre = np.eye(3)
        for k, (fn, ang, ax_b, _) in enumerate(steps):
            for si in s:
                frames.append(pre @ fn(si * ang))
                stage.append(k)
                axis_nav.append(pre @ ax_b)
            pre = pre @ fn(ang)

    return {
        "frames": np.asarray(frames),
        "stage": np.asarray(stage, dtype=int),
        "axis_nav": np.asarray(axis_nav),
        "labels": [st[3] for st in steps],
        "final": frames[-1],
    }


# --- Euler singularity -----------------------------------------------------------------


def euler_sensitivity_scan(
    yaw_deg: float,
    roll_deg: float,
    pitches_deg: np.ndarray,
    perturb_deg: float = 0.5,
) -> dict[str, np.ndarray]:
    """How much a tiny body rotation moves the extracted Euler angles.

    For each pitch, rotate the body by ``perturb_deg`` about its own z axis and
    re-extract ZYX Euler. Away from +/-90 deg the change is ~perturb; near the
    singularity yaw and roll both swing by ~perturb / cos(pitch).
    """
    y0, r0 = yaw_deg * DEG2RAD, roll_deg * DEG2RAD
    d = rot_z(perturb_deg * DEG2RAD)
    dyaw, droll, dpitch = [], [], []
    for p_deg in pitches_deg:
        rr = euler_zyx_to_dcm(y0, p_deg * DEG2RAD, r0)
        a = np.array(dcm_to_euler_zyx(rr)) * RAD2DEG
        b = np.array(dcm_to_euler_zyx(rr @ d)) * RAD2DEG
        dd = wrap_180(b - a)
        dyaw.append(abs(dd[0]))
        dpitch.append(abs(dd[1]))
        droll.append(abs(dd[2]))
    cosp = np.cos(np.asarray(pitches_deg) * DEG2RAD)
    return {
        "pitch_deg": np.asarray(pitches_deg, dtype=float),
        "dyaw_deg": np.asarray(dyaw),
        "dpitch_deg": np.asarray(dpitch),
        "droll_deg": np.asarray(droll),
        "euler_rate_gain": 1.0 / np.maximum(np.abs(cosp), 1e-3),
    }


# --- kinematics ----------------------------------------------------------------------


def body_rate_dps(params: AttitudeParams, t: np.ndarray) -> np.ndarray:
    """Body angular rate history (N, 3) in deg/s."""
    t = np.atleast_1d(t)
    w = np.tile([params.wx_dps, params.wy_dps, params.wz_dps], (t.shape[0], 1)).astype(float)
    if params.coning_amp_dps > 0:
        om = 2.0 * np.pi * params.coning_hz
        w[:, 0] += params.coning_amp_dps * np.cos(om * t)
        w[:, 1] += params.coning_amp_dps * np.sin(om * t)
    return w


def _truth_attitude(params: AttitudeParams, t_out: np.ndarray, r0: np.ndarray, h_max: float = 1e-3) -> np.ndarray:
    """Reference attitude via fine midpoint exp-map integration (step <= h_max)."""
    q = dcm_to_quat(r0)
    out = np.empty((t_out.shape[0], 3, 3))
    out[0] = r0
    for k in range(1, t_out.shape[0]):
        span = t_out[k] - t_out[k - 1]
        substeps = max(1, int(np.ceil(span / h_max)))
        h = span / substeps
        for j in range(substeps):
            tm = t_out[k - 1] + (j + 0.5) * h
            w = body_rate_dps(params, np.array([tm]))[0] * DEG2RAD
            q = quat_mul(q, quat_from_rotvec(w * h))
        q = q / np.linalg.norm(q)
        out[k] = quat_to_dcm(q)
    return out


def integrate_attitude(params: AttitudeParams) -> dict[str, np.ndarray | float]:
    """Integrate body rates from the slider pose; compare with a fine reference."""
    dt = params.int_dt_s
    n = int(round(params.int_duration_s / dt)) + 1
    t = np.arange(n) * dt
    r0 = euler_zyx_to_dcm(params.yaw_deg * DEG2RAD, params.pitch_deg * DEG2RAD, params.roll_deg * DEG2RAD)
    truth = _truth_attitude(params, t, r0)
    # Sensor-like samples: rate sampled at the start of each step (what a naive loop uses)
    w_s = body_rate_dps(params, t) * DEG2RAD

    est = np.empty((n, 3, 3))
    est[0] = r0
    q = dcm_to_quat(r0)
    r = r0.copy()
    for k in range(1, n):
        w = w_s[k - 1]
        if params.integrator == Integrator.QUAT_EXP:
            q = quat_mul(q, quat_from_rotvec(w * dt))
            if params.renormalize:
                q = q / np.linalg.norm(q)
            est[k] = quat_to_dcm(q)
        else:
            r = r @ (np.eye(3) + skew(w) * dt)
            if params.renormalize:
                r = orthonormalize(r)
            est[k] = r

    ortho = np.array([np.linalg.norm(m.T @ m - np.eye(3)) for m in est])
    ang_err = np.array([rotation_angle_deg(orthonormalize(e), tr) for e, tr in zip(est, truth)])
    euler_true = np.array([dcm_to_euler_zyx(m) for m in truth]) * RAD2DEG
    euler_est = np.array([dcm_to_euler_zyx(orthonormalize(m)) for m in est]) * RAD2DEG
    return {
        "t_s": t,
        "truth": truth,
        "est": est,
        "ortho_err": ortho,
        "angle_err_deg": ang_err,
        "euler_true_deg": euler_true,
        "euler_est_deg": euler_est,
        "final_angle_err_deg": float(ang_err[-1]),
        "final_ortho_err": float(ortho[-1]),
    }


# --- snapshot for the pose view -----------------------------------------------------------


def process(params: AttitudeParams) -> dict[str, object]:
    """Pose snapshot plus the gimbal-lock sensitivity scan."""
    y, p, r = params.yaw_deg * DEG2RAD, params.pitch_deg * DEG2RAD, params.roll_deg * DEG2RAD
    dcm = euler_zyx_to_dcm(y, p, r)
    q = euler_to_quat(y, p, r)
    y2, p2, r2 = dcm_to_euler_zyx(quat_to_dcm(q))
    axis, angle = quat_axis_angle(q)
    pitches = np.linspace(-params.pitch_scan_deg, params.pitch_scan_deg, params.n_samples)
    scan = euler_sensitivity_scan(params.yaw_deg, params.roll_deg, pitches, params.perturb_deg)
    dcm_ros = dcm_ned_frd_to_enu_flu(dcm)
    return {
        "dcm": dcm,
        "dcm_ros": dcm_ros,
        "euler_ros_deg": np.array(euler_ned_to_ros(params.yaw_deg, params.pitch_deg, params.roll_deg)),
        "body_x_ned": dcm[:, 0],
        "body_y_ned": dcm[:, 1],
        "body_z_ned": dcm[:, 2],
        "quat": q,
        "quat_neg_dcm_err": float(np.max(np.abs(quat_to_dcm(-q) - dcm))),
        "axis": axis,
        "angle_deg": angle,
        "euler_from_quat_deg": np.array([y2, p2, r2]) * RAD2DEG,
        "det_dcm": float(np.linalg.det(dcm)),
        "scan": scan,
        "euler_rate_gain": float(1.0 / max(abs(np.cos(p)), 1e-3)),
    }
