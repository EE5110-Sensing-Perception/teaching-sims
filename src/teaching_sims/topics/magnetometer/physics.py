"""Magnetometer heading: Earth field, tilt compensation, iron calibration, disturbances.

Earth field in NED from total intensity F, inclination (dip) I and declination D:

    b_n = F [cos I cos D,  cos I sin D,  sin I]

Body measurement: ``b = S R^T (b_n + d_n) + h + noise`` with soft iron ``S``,
hard iron ``h`` (both body-fixed, so calibratable) and a world-fixed
disturbance ``d_n`` (e.g. a steel structure) that no calibration removes.

Magnetic heading is ``atan2(-y_h, x_h)`` of the tilt-compensated horizontal
field; true heading = magnetic heading + declination.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from teaching_sims.core.imu import DEG2RAD, RAD2DEG, wrap_180
from teaching_sims.topics.attitude.physics import euler_zyx_to_dcm


@dataclass(frozen=True)
class MagParams:
    """Body magnetometer with optional hard/soft-iron, tilt, and disturbances."""

    yaw_deg: float = 35.0  # true heading
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    # Local Earth field (defaults ~ [20, 0, 45] uT: mid northern latitude)
    total_ut: float = 49.24
    inclination_deg: float = 66.04
    declination_deg: float = 0.0
    apply_declination: bool = True
    # Hard-iron bias (body uT)
    hard_x_ut: float = 0.0
    hard_y_ut: float = 0.0
    hard_z_ut: float = 0.0
    # Soft-iron scale (diagonal) and cross-coupling xy
    soft_xx: float = 1.0
    soft_yy: float = 1.0
    soft_zz: float = 1.0
    soft_xy: float = 0.0
    # World-fixed disturbance (NED uT), e.g. nearby steel
    dist_n_ut: float = 0.0
    dist_e_ut: float = 0.0
    dist_d_ut: float = 0.0
    noise_ut: float = 0.3
    # Sweep yaw for polar plot if enabled
    sweep_yaw: bool = True
    n_sweep: int = 72
    tilt_compensate: bool = True
    seed: int = 0

    def __post_init__(self) -> None:
        if self.n_sweep < 8:
            raise ValueError("n_sweep must be >= 8")
        if self.total_ut <= 0:
            raise ValueError("total_ut must be positive")


def earth_field_ned(params: MagParams) -> np.ndarray:
    i, d = params.inclination_deg * DEG2RAD, params.declination_deg * DEG2RAD
    f = params.total_ut
    return np.array([f * np.cos(i) * np.cos(d), f * np.cos(i) * np.sin(d), f * np.sin(i)], dtype=float)


def soft_iron_matrix(params: MagParams) -> np.ndarray:
    s = np.eye(3)
    s[0, 0] = params.soft_xx
    s[1, 1] = params.soft_yy
    s[2, 2] = params.soft_zz
    s[0, 1] = s[1, 0] = params.soft_xy
    return s


def measure_mag_body(params: MagParams, yaw_deg: float, pitch_deg: float, roll_deg: float, rng) -> np.ndarray:
    r_bn = euler_zyx_to_dcm(yaw_deg * DEG2RAD, pitch_deg * DEG2RAD, roll_deg * DEG2RAD).T
    b_n = earth_field_ned(params) + np.array([params.dist_n_ut, params.dist_e_ut, params.dist_d_ut])
    b_body = r_bn @ b_n
    hard = np.array([params.hard_x_ut, params.hard_y_ut, params.hard_z_ut])
    b = soft_iron_matrix(params) @ b_body + hard
    if params.noise_ut > 0:
        b = b + rng.normal(0.0, params.noise_ut, size=3)
    return b


def horizontal_field(bx: float, by: float, bz: float, pitch_deg: float, roll_deg: float) -> tuple[float, float]:
    """Rotate the body field back to the local level plane (x_h north-ish, y_h east-ish)."""
    p = pitch_deg * DEG2RAD
    r = roll_deg * DEG2RAD
    xh = bx * np.cos(p) + by * np.sin(r) * np.sin(p) + bz * np.cos(r) * np.sin(p)
    yh = by * np.cos(r) - bz * np.sin(r)
    return float(xh), float(yh)


def heading_from_mag(bx: float, by: float, bz: float, pitch_deg: float, roll_deg: float, compensate: bool) -> float:
    """Magnetic heading (deg). With compensate=True use the tilt-compensated horizontal field."""
    if compensate:
        xh, yh = horizontal_field(bx, by, bz, pitch_deg, roll_deg)
        return float(wrap_180(np.arctan2(-yh, xh) * RAD2DEG))
    return float(wrap_180(np.arctan2(-by, bx) * RAD2DEG))


# --- calibration --------------------------------------------------------------------


def fit_ellipse_calibration(bx: np.ndarray, by: np.ndarray) -> dict[str, np.ndarray | float]:
    """2-D ellipse fit for hard/soft iron from a *level* yaw sweep (compass swing).

    Fits a x^2 + b xy + c y^2 + d x + e y = 1 by linear least squares, then
    returns the centre (hard iron) and a matrix ``W`` mapping the ellipse onto
    a circle of the mean radius: ``b_corr = W (b - centre)``.
    """
    x = np.asarray(bx, dtype=float)
    y = np.asarray(by, dtype=float)
    d = np.column_stack([x * x, x * y, y * y, x, y])
    coef, *_ = np.linalg.lstsq(d, np.ones_like(x), rcond=None)
    a, b, c, dd, ee = coef
    q = np.array([[a, b / 2.0], [b / 2.0, c]])
    centre = -0.5 * np.linalg.solve(q, np.array([dd, ee]))
    k = 1.0 + centre @ q @ centre
    qn = q / k  # (p - c)^T qn (p - c) = 1
    evals, evecs = np.linalg.eigh(qn)
    radius = float(np.mean(1.0 / np.sqrt(evals)))  # keep the average field strength
    w = radius * (evecs @ np.diag(np.sqrt(evals)) @ evecs.T)
    t = np.linspace(0, 2 * np.pi, 200)
    unit = np.stack([np.cos(t), np.sin(t)])
    ell = centre[:, None] + evecs @ np.diag(1.0 / np.sqrt(evals)) @ unit
    return {"centre": centre, "w": w, "radius": radius, "ellipse_x": ell[0], "ellipse_y": ell[1]}


def compass_swing(params: MagParams, n: int = 72) -> dict[str, np.ndarray | float]:
    """Level yaw sweep with the current iron, then fit the calibration."""
    level = replace(params, pitch_deg=0.0, roll_deg=0.0, dist_n_ut=0.0, dist_e_ut=0.0, dist_d_ut=0.0)
    rng = np.random.default_rng(params.seed + 101)
    yaws = np.linspace(-180.0, 180.0, n, endpoint=False)
    pts = np.array([measure_mag_body(level, float(yw), 0.0, 0.0, rng) for yw in yaws])
    cal = fit_ellipse_calibration(pts[:, 0], pts[:, 1])
    cal["swing_bx"] = pts[:, 0]
    cal["swing_by"] = pts[:, 1]
    return cal


def apply_mag_calibration(b: np.ndarray, cal: dict | None) -> np.ndarray:
    if cal is None:
        return b
    out = np.array(b, dtype=float)
    out[:2] = cal["w"] @ (out[:2] - cal["centre"])
    return out


# --- disturbance check ---------------------------------------------------------------


def field_check(b_body: np.ndarray, pitch_deg: float, roll_deg: float, params: MagParams,
                tol_mag_pct: float = 5.0, tol_dip_deg: float = 3.0) -> dict[str, float | bool]:
    """Compare |b| and dip with the expected Earth field: a gate for disturbances."""
    mag = float(np.linalg.norm(b_body))
    r_nb = euler_zyx_to_dcm(0.0, pitch_deg * DEG2RAD, roll_deg * DEG2RAD)
    b_lvl = r_nb @ b_body  # yaw does not change the dip
    dip = float(np.arctan2(b_lvl[2], np.hypot(b_lvl[0], b_lvl[1])) * RAD2DEG)
    d_mag = 100.0 * (mag - params.total_ut) / params.total_ut
    d_dip = dip - params.inclination_deg
    return {
        "magnitude_ut": mag,
        "dip_deg": dip,
        "d_mag_pct": d_mag,
        "d_dip_deg": d_dip,
        "ok": bool(abs(d_mag) <= tol_mag_pct and abs(d_dip) <= tol_dip_deg),
    }


# --- main -------------------------------------------------------------------------------


def _true_heading(params: MagParams, h_mag: float) -> float:
    return float(wrap_180(h_mag + (params.declination_deg if params.apply_declination else 0.0)))


def process(params: MagParams, cal: dict | None = None) -> dict[str, object]:
    rng = np.random.default_rng(params.seed)
    if params.sweep_yaw:
        yaws = np.linspace(-180.0, 180.0, params.n_sweep, endpoint=False)
    else:
        yaws = np.array([params.yaw_deg], dtype=float)

    bx_s, by_s, bz_s, bx_c, by_c = [], [], [], [], []
    hdg_raw, hdg_tc, hdg_err, hdg_cal = [], [], [], []
    for yaw in yaws:
        b = measure_mag_body(params, float(yaw), params.pitch_deg, params.roll_deg, rng)
        bc = apply_mag_calibration(b, cal)
        bx_s.append(b[0])
        by_s.append(b[1])
        bz_s.append(b[2])
        bx_c.append(bc[0])
        by_c.append(bc[1])
        raw = _true_heading(params, heading_from_mag(b[0], b[1], b[2], params.pitch_deg, params.roll_deg, False))
        tc = _true_heading(params, heading_from_mag(b[0], b[1], b[2], params.pitch_deg, params.roll_deg, True))
        h_cal = _true_heading(
            params, heading_from_mag(bc[0], bc[1], bc[2], params.pitch_deg, params.roll_deg, params.tilt_compensate)
        )
        use = h_cal if cal is not None else (tc if params.tilt_compensate else raw)
        hdg_raw.append(raw)
        hdg_tc.append(tc)
        hdg_cal.append(h_cal)
        hdg_err.append(wrap_180(use - yaw))

    # Single pose snapshot at selected yaw
    b0 = measure_mag_body(params, params.yaw_deg, params.pitch_deg, params.roll_deg, rng)
    b0c = apply_mag_calibration(b0, cal)
    h_raw0 = _true_heading(params, heading_from_mag(*b0c, params.pitch_deg, params.roll_deg, False))
    h_tc0 = _true_heading(params, heading_from_mag(*b0c, params.pitch_deg, params.roll_deg, True))
    h0 = h_tc0 if params.tilt_compensate else h_raw0

    return {
        "yaw_sweep_deg": yaws,
        "bx": np.asarray(bx_s),
        "by": np.asarray(by_s),
        "bz": np.asarray(bz_s),
        "bx_cal": np.asarray(bx_c),
        "by_cal": np.asarray(by_c),
        "heading_raw_deg": np.asarray(hdg_raw),
        "heading_tc_deg": np.asarray(hdg_tc),
        "heading_cal_deg": np.asarray(hdg_cal),
        "heading_err_deg": np.asarray(hdg_err),
        "snapshot_b_ut": b0,
        "snapshot_heading_deg": h0,
        "snapshot_raw_deg": h_raw0,
        "snapshot_tc_deg": h_tc0,
        "snapshot_err_deg": float(wrap_180(h0 - params.yaw_deg)),
        "rms_err_deg": float(np.sqrt(np.mean(np.asarray(hdg_err) ** 2))),
        "field_check": field_check(b0c, params.pitch_deg, params.roll_deg, params),
        "earth_field_ned": earth_field_ned(params),
    }
