"""Generate the IMU deck's data figures from the same physics the demos use.

Usage (from the repo root)::

    python -m teaching_sims.slides.imu_figures --out slides/figures/imu
    python -m teaching_sims.slides.imu_figures --only gyro_allan --out /tmp/x

Each figure is a function registered with ``@figure("name")`` that returns a
matplotlib ``Figure``; it is saved as ``<name>.pdf``. Colors come from
``teaching_sims.ui.palette`` so slides and demos use the same role colors.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from teaching_sims.core.allan import allan_deviation  # noqa: E402
from teaching_sims.core.imu_errors import GRADE_PRESETS, SensorErrorModel  # noqa: E402
from teaching_sims.ui.palette import mpl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
FIG_W, FIG_H = 6.4, 3.4  # inches; fits a 16:9 beamer frame at ~0.9 textwidth

REGISTRY: dict[str, Callable[[], plt.Figure]] = {}


def figure(name: str):
    def deco(fn: Callable[[], plt.Figure]):
        REGISTRY[name] = fn
        return fn

    return deco


def _setup_style() -> None:
    inter = REPO_ROOT / "fonts" / "Inter-4.1" / "extras" / "ttf"
    family = "DejaVu Sans"
    if inter.is_dir():
        for f in inter.glob("Inter-*.ttf"):
            font_manager.fontManager.addfont(str(f))
        family = "Inter"
    plt.rcParams.update(
        {
            "font.family": family,
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 1.8,
            "figure.dpi": 100,
            "savefig.bbox": "tight",
            "mathtext.fontset": "dejavusans",
        }
    )


def new_fig(ncols: int = 1, nrows: int = 1, w: float = FIG_W, h: float = FIG_H, **kw):
    fig, ax = plt.subplots(nrows, ncols, figsize=(w, h), constrained_layout=True, **kw)
    return fig, ax


# --- A. frames and rotations ------------------------------------------------------

_AX_RGB = ((0.86, 0.25, 0.25), (0.25, 0.65, 0.35), (0.2, 0.4, 0.85))


def _ned_to_plot(v: np.ndarray) -> np.ndarray:
    """NED -> matplotlib (x=E, y=N, z=Up)."""
    v = np.asarray(v, dtype=float)
    return np.stack([v[..., 1], v[..., 0], -v[..., 2]], axis=-1)


def _draw_body(ax, r: np.ndarray, *, ghost: np.ndarray | None = None, axis_nav: np.ndarray | None = None) -> None:
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    half = np.array([0.8, 0.5, 0.18])
    v = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], dtype=float) * half
    faces = ((4, 5, 7, 6), (0, 1, 3, 2), (2, 3, 7, 6), (0, 1, 5, 4), (0, 2, 6, 4), (1, 3, 7, 5))
    fills = [mpl("fused")] + [(0.75, 0.77, 0.82)] * 3 + [(0.6, 0.63, 0.7)] + [(0.75, 0.77, 0.82)]

    def box(rr, alpha, edge, fill=True):
        pts = _ned_to_plot(v @ rr.T)
        polys = [[pts[i] for i in f] for f in faces]
        pc = Poly3DCollection(polys, alpha=alpha, edgecolor=edge, linewidths=0.6)
        pc.set_facecolor(fills if fill else (1, 1, 1, 0))
        ax.add_collection3d(pc)

    if ghost is not None:
        box(ghost, 0.0, (0.6, 0.6, 0.6), fill=False)
    box(r, 0.35, (0.3, 0.3, 0.35))
    for k in range(3):
        tip = _ned_to_plot(r[:, k] * 1.25)
        ax.plot([0, tip[0]], [0, tip[1]], [0, tip[2]], color=_AX_RGB[k], lw=2)
    if axis_nav is not None:
        a = _ned_to_plot(axis_nav / np.linalg.norm(axis_nav) * 1.5)
        ax.plot([-a[0], a[0]], [-a[1], a[1]], [-a[2], a[2]], color=mpl("cursor"), lw=2.2)
    for k, lab in enumerate("NED"):
        tip = _ned_to_plot(np.eye(3)[k] * 1.5)
        ax.plot([0, tip[0]], [0, tip[1]], [0, tip[2]], color="0.6", lw=0.8)
        ax.text(*(tip * 1.1), lab, color="0.45", fontsize=8)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)
    ax.set_zlim(-1.3, 1.3)
    ax.set_box_aspect((1, 1, 1), zoom=1.45)
    ax.view_init(elev=22, azim=-30)
    ax.set_axis_off()


@figure("rotation_order")
def fig_rotation_order() -> plt.Figure:
    """Build ZYX vs roll-first XYZ with the same three angles."""
    from teaching_sims.topics.attitude.physics import Sequence, sequence_frames

    angles = (60.0, 30.0, 40.0)
    rows = (
        (Sequence.INTRINSIC_ZYX, "Z-Y$'$-X$''$ (yaw, pitch, roll)"),
        (Sequence.INTRINSIC_XYZ, "X-Y$'$-Z$''$ (roll, pitch, yaw)"),
    )
    fig = plt.figure(figsize=(FIG_W, 3.5), constrained_layout=True)
    ref = sequence_frames(*angles, Sequence.INTRINSIC_ZYX)["final"]
    for ri, (seq, name) in enumerate(rows):
        sf = sequence_frames(*angles, seq, n_per_stage=2)
        snaps = [np.eye(3)] + [sf["frames"][2 * k + 1] for k in range(3)]
        for ci, r in enumerate(snaps):
            ax = fig.add_subplot(2, 4, ri * 4 + ci + 1, projection="3d")
            axis = sf["axis_nav"][2 * (ci - 1) + 1] if ci > 0 else None
            _draw_body(ax, r, ghost=ref if (ri == 1 and ci == 3) else None, axis_nav=axis)
            if ci == 0:
                ax.set_title(name, fontsize=8, loc="left")
            else:
                ax.set_title(sf["labels"][ci - 1], fontsize=8)
    return fig


@figure("gimbal_sensitivity")
def fig_gimbal_sensitivity() -> plt.Figure:
    from teaching_sims.topics.attitude.physics import euler_sensitivity_scan

    pitches = np.linspace(-89.5, 89.5, 719)
    s = euler_sensitivity_scan(30.0, 20.0, pitches, 0.5)
    fig, ax = new_fig(h=3.0)
    ax.semilogy(pitches, np.maximum(s["dyaw_deg"], 1e-4), color=mpl("gyro"), label=r"$|\Delta\psi|$ yaw")
    ax.semilogy(pitches, np.maximum(s["droll_deg"], 1e-4), color=mpl("accel"), label=r"$|\Delta\phi|$ roll")
    ax.semilogy(pitches, 0.5 * s["euler_rate_gain"], color=mpl("reference"), ls="--", lw=1.2,
                label=r"$0.5^\circ/\cos\theta$")
    ax.set_ylim(1e-2, 100)
    ax.set_xlabel(r"pitch $\theta$ (deg)")
    ax.set_ylabel("change in extracted angle (deg)")
    ax.set_title(r"Extracted Euler change for a $0.5^\circ$ body rotation", loc="left")
    ax.legend(loc="upper center")
    return fig


@figure("rate_integration")
def fig_rate_integration() -> plt.Figure:
    from teaching_sims.topics.attitude.physics import AttitudeParams, Integrator, integrate_attitude

    base = dict(yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0, wz_dps=90.0, wx_dps=20.0, int_dt_s=0.05)
    runs = (
        ("first-order DCM", dict(integrator=Integrator.DCM_EULER), mpl("error"), dict(lw=4.0, alpha=0.6)),
        ("first-order DCM + renorm.", dict(integrator=Integrator.DCM_EULER, renormalize=True), mpl("mag"),
         dict(lw=1.8, ls="--")),
        ("quaternion exp-map", dict(integrator=Integrator.QUAT_EXP, renormalize=True), mpl("fused"), dict(lw=2.0)),
    )
    fig, (a1, a2) = new_fig(2, 1, h=3.2)
    for name, kw, c, style in runs:
        out = integrate_attitude(AttitudeParams(**base, **kw))
        a1.plot(out["t_s"], out["angle_err_deg"], color=c, label=name, **style)
        a2.semilogy(out["t_s"], np.maximum(out["ortho_err"], 1e-16), color=c, label=name, **style)
    a1.annotate("renormalising does not\nremove this error", xy=(7.0, 1.4), xytext=(1.0, 1.55),
                fontsize=8, color=mpl("mag"), arrowprops=dict(arrowstyle="->", color=mpl("mag")))
    a1.set_title("attitude error (deg)", loc="left")
    a2.set_title(r"$\|R^\top R - I\|$", loc="left")
    for a in (a1, a2):
        a.set_xlabel("t (s)")
    a1.legend(loc="upper left", fontsize=8)
    return fig


@figure("coning_dt")
def fig_coning_dt() -> plt.Figure:
    from teaching_sims.topics.attitude.physics import AttitudeParams, Integrator, integrate_attitude

    dts = np.array([0.002, 0.005, 0.01, 0.02, 0.05, 0.1])
    fig, ax = new_fig(h=2.8, w=4.6)
    for amp, c in ((30.0, mpl("gyro")), (60.0, mpl("fused"))):
        errs = [
            integrate_attitude(
                AttitudeParams(yaw_deg=0, pitch_deg=0, roll_deg=0, wz_dps=0.0, coning_amp_dps=amp, coning_hz=2.0,
                               int_duration_s=5.0, int_dt_s=float(dt), integrator=Integrator.QUAT_EXP, renormalize=True)
            )["final_angle_err_deg"]
            for dt in dts
        ]
        ax.loglog(1.0 / dts, errs, "o-", color=c, label=f"coning amplitude {amp:.0f} deg/s")
    ax.set_xlabel("integration rate (Hz)")
    ax.set_ylabel("error after 5 s (deg)")
    ax.set_title("Coning: exp-map with constant-rate steps", loc="left")
    ax.legend()
    return fig


# --- B. sensors -----------------------------------------------------------------------


@figure("mems_accel_response")
def fig_mems_accel_response() -> plt.Figure:
    """Frequency response for soft vs stiff springs and two damping ratios."""
    from teaching_sims.topics.mems_accel.physics import (
        MEMSAccelParams,
        bandwidth_hz,
        frequency_response,
        sensitivity_nm_per_g,
    )

    f = np.logspace(1, np.log10(40_000), 400)
    fig, ax = new_fig(h=3.0, w=5.2)
    cases = (
        (0.5, 0.7, mpl("accel"), "-"),
        (8.0, 0.7, mpl("gyro"), "-"),
        (8.0, 0.1, mpl("gyro"), ":"),
    )
    for k, z, c, ls in cases:
        p = MEMSAccelParams(kn_n_per_m=k, zeta=z)
        ax.loglog(f, frequency_response(p, f)["mag"], color=c, ls=ls,
                  label=f"k={k:g} N/m, $\\zeta$={z:g}: {sensitivity_nm_per_g(p):.0f} nm/g, BW {bandwidth_hz(p) / 1e3:.1f} kHz")
    ax.axhline(1 / np.sqrt(2), color=mpl("reference"), lw=0.8, ls="--")
    ax.set_ylim(1e-2, 8)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel(r"$|a_{\mathrm{meas}}/a_{\mathrm{ext}}|$")
    ax.legend(loc="lower left", fontsize=8)
    return fig


@figure("accel_disturbance_tilt")
def fig_accel_disturbance_tilt() -> plt.Figure:
    """Bias, surge and lever arm are indistinguishable from tilt for a static accelerometer."""
    from teaching_sims.topics.accelerometer.physics import AccelParams, tilt_error_curve

    d = np.linspace(-3, 3, 241)
    c = tilt_error_curve(AccelParams(roll_deg=0.0, pitch_deg=0.0), d)
    fig, ax = new_fig(h=2.9, w=4.6)
    ax.plot(d, c["pitch_err_deg"], color=mpl("fused"))
    ax.plot(d, np.degrees(d / 9.80665), color=mpl("reference"), ls="--", lw=1.0, label=r"small-angle $b/g$")
    for x, txt in ((0.1, "consumer bias\n0.1 m/s$^2$ = 0.6$^\\circ$"), (1.0, "car accelerating\n1 m/s$^2$ = 5.8$^\\circ$")):
        y = float(np.degrees(np.arctan(x / 9.80665)))
        ax.plot([x], [y], "o", color=mpl("cursor"))
        ax.annotate(txt, xy=(x, y), xytext=(x + 0.4, y - 7), fontsize=8,
                    arrowprops=dict(arrowstyle="->", color="0.4"))
    ax.set_xlabel(r"extra specific force along $x$ (m/s$^2$)")
    ax.set_ylabel("pitch error (deg)")
    ax.legend(loc="upper left")
    return fig


@figure("accel_vibration_average")
def fig_accel_vibration_average() -> plt.Figure:
    from teaching_sims.topics.accelerometer.physics import process
    from teaching_sims.topics.accelerometer.scenarios import get_scenario

    out = process(get_scenario("vibration_average").params)
    t = out["t_s"]
    fig, ax = new_fig(h=2.6, w=4.8)
    ax.plot(t, out["pitch_est_deg"], color=mpl("measured"), lw=0.8, label="instantaneous")
    ax.plot(t, out["pitch_avg_deg"], color=mpl("fused"), label="1 s moving average")
    ax.axhline(get_scenario("vibration_average").params.pitch_deg, color=mpl("truth"), lw=1.2, label="truth")
    ax.set_xlabel("t (s)")
    ax.set_ylabel("pitch (deg)")
    ax.set_ylim(-12, 22)
    ax.legend(loc="upper center", fontsize=8, ncol=3, frameon=True, framealpha=0.9)
    return fig


@figure("accel_six_position")
def fig_accel_six_position() -> plt.Figure:
    from teaching_sims.topics.accelerometer.physics import (
        gravity_specific_force_body,
        measure,
        six_position_calibration,
        tilt_from_accel,
    )
    from teaching_sims.topics.accelerometer.scenarios import get_scenario

    p = replace_params(get_scenario("six_position_cal").params, noise_mps2=0.02)
    cal = six_position_calibration(p, samples_per_pose=300)
    rng = np.random.default_rng(3)
    ginv = np.linalg.inv(cal["gain"])
    before, after = [], []
    for _ in range(300):
        roll, pitch = rng.uniform(-60, 60), rng.uniform(-60, 60)
        q = replace_params(p, roll_deg=roll, pitch_deg=pitch)
        f = gravity_specific_force_body(0.0, pitch, roll)
        y = measure(q, f, rng, 50).mean(axis=0)
        r0, p0 = tilt_from_accel(*y)
        r1, p1 = tilt_from_accel(*(ginv @ (y - cal["bias"])))
        before.append(np.hypot(r0 - roll, p0 - pitch))
        after.append(np.hypot(r1 - roll, p1 - pitch))
    fig, ax = new_fig(h=2.8, w=4.6)
    bins = np.logspace(np.log10(min(after) * 0.8), np.log10(max(before) * 1.2), 40)
    ax.set_xscale("log")
    ax.hist(before, bins=bins, color=mpl("error"), alpha=0.8, label=f"raw: median {np.median(before):.2f}$^\\circ$")
    ax.hist(after, bins=bins, color=mpl("fused"), alpha=0.9, label=f"calibrated: median {np.median(after):.2f}$^\\circ$")
    ax.set_xlabel("tilt error over 300 random poses (deg)")
    ax.set_ylabel("count")
    ax.legend()
    return fig


@figure("lever_arm_tilt")
def fig_lever_arm_tilt() -> plt.Figure:
    from teaching_sims.topics.accelerometer.physics import AccelParams, process

    rates = np.linspace(0, 180, 61)
    fig, ax = new_fig(h=2.8, w=4.6)
    for r, c in ((0.1, mpl("accel")), (0.3, mpl("gyro")), (0.5, mpl("fused"))):
        err = [process(AccelParams(roll_deg=0, pitch_deg=0, noise_mps2=0.0, lever_x_m=r, yaw_rate_dps=float(w),
                                   duration_s=1.0))["pitch_mean_deg"] for w in rates]
        ax.plot(rates, err, color=c, label=f"IMU {r:.1f} m from spin axis")
    ax.set_xlabel("yaw rate (deg/s)")
    ax.set_ylabel("fake pitch (deg)")
    ax.legend(loc="lower left", fontsize=8)
    return fig


def replace_params(p, **kw):
    from dataclasses import replace

    return replace(p, **kw)


@figure("mag_tilt_error")
def fig_mag_tilt_error() -> plt.Figure:
    from teaching_sims.core.imu import wrap_180
    from teaching_sims.topics.magnetometer.physics import MagParams, process

    fig, ax = new_fig(h=2.8, w=4.8)
    for pitch, c in ((10.0, mpl("mag")), (25.0, mpl("error"))):
        out = process(MagParams(pitch_deg=pitch, noise_ut=0.0, n_sweep=180))
        y = out["yaw_sweep_deg"]
        ax.plot(y, wrap_180(out["heading_raw_deg"] - y), color=c, label=f"pitch {pitch:.0f}$^\\circ$, no tilt comp.")
    out = process(MagParams(pitch_deg=25.0, noise_ut=0.0, n_sweep=180))
    ax.plot(out["yaw_sweep_deg"], wrap_180(out["heading_tc_deg"] - out["yaw_sweep_deg"]), color=mpl("fused"),
            label="pitch 25$^\\circ$, tilt-compensated")
    ax.set_xlabel("true heading (deg)")
    ax.set_ylabel("heading error (deg)")
    ax.set_xticks([-180, -90, 0, 90, 180])
    ax.legend(fontsize=8, loc="lower left")
    return fig


@figure("mag_iron_calibration")
def fig_mag_iron_calibration() -> plt.Figure:
    from teaching_sims.topics.magnetometer.physics import compass_swing, process
    from teaching_sims.topics.magnetometer.scenarios import get_scenario

    p = get_scenario("iron_calibrated").params
    cal = compass_swing(p)
    out = process(p, cal=cal)
    raw = process(p)
    fig, (a1, a2) = new_fig(2, 1, h=2.9, w=6.0)
    a1.plot(out["bx"], out["by"], ".", color=mpl("measured"), ms=4, label="raw swing")
    a1.plot(cal["ellipse_x"], cal["ellipse_y"], color=mpl("mag"), lw=1.5, label="fitted ellipse")
    a1.plot(*cal["centre"], "o", color=mpl("cursor"), label="hard-iron centre")
    a1.plot(out["bx_cal"], out["by_cal"], ".", color=mpl("fused"), ms=4, label="calibrated")
    a1.set_aspect("equal")
    a1.set_xlabel("$b_x$ ($\\mu$T)")
    a1.set_ylabel("$b_y$ ($\\mu$T)")
    a1.legend(fontsize=7, loc="upper left")
    from teaching_sims.core.imu import wrap_180

    y = raw["yaw_sweep_deg"]
    a2.plot(y, wrap_180(raw["heading_tc_deg"] - y), color=mpl("error"), label=f"raw: RMS {raw['rms_err_deg']:.1f}$^\\circ$")
    a2.plot(y, wrap_180(out["heading_cal_deg"] - y), color=mpl("fused"),
            label=f"calibrated: RMS {out['rms_err_deg']:.1f}$^\\circ$")
    a2.set_xticks([-180, -90, 0, 90, 180])
    a2.set_xlabel("true heading (deg)")
    a2.set_ylabel("heading error (deg)")
    a2.legend(fontsize=8)
    return fig


@figure("mems_gyro_modes")
def fig_mems_gyro_modes() -> plt.Figure:
    """Mode split vs mode matched: sensitivity and rate bandwidth."""
    from teaching_sims.topics.mems_gyro.physics import (
        MEMSGyroParams,
        rate_bandwidth_hz,
        rate_frequency_response,
        sensitivity_nm_per_dps,
    )

    f = np.logspace(-1, 3, 400)
    fig, ax = new_fig(h=3.0, w=5.2)
    for split, c in ((0.0, mpl("fused")), (100.0, mpl("mag")), (300.0, mpl("gyro"))):
        p = MEMSGyroParams(sense_split_hz=split, q_sense=200.0)
        g = np.abs(rate_frequency_response(p, f, include_lpf=False))
        ax.loglog(f, g, color=c, label=f"split {split:.0f} Hz: {sensitivity_nm_per_dps(p) * 1e3:.0f} pm/(deg/s), "
                                       f"BW {rate_bandwidth_hz(p, include_lpf=False):.0f} Hz")
    ax.axhline(1 / np.sqrt(2), color=mpl("reference"), lw=0.8, ls="--")
    ax.set_ylim(1e-2, 20)
    ax.set_xlabel("rate input frequency (Hz)")
    ax.set_ylabel("rate output / input")
    ax.legend(loc="lower left", fontsize=8)
    return fig


@figure("mems_gyro_quadrature")
def fig_mems_gyro_quadrature() -> plt.Figure:
    """Bias from demodulator phase error with 200 deg/s-equivalent quadrature."""
    from teaching_sims.topics.mems_gyro.physics import MEMSGyroParams, RateProfile, process

    phis = np.linspace(-6, 6, 7)
    meas = [process(MEMSGyroParams(profile=RateProfile.ZERO, quadrature_dps=200.0, demod_phase_err_deg=float(ph),
                                   duration_s=0.15))["bias_dps"] for ph in phis]
    fine = np.linspace(-6, 6, 200)
    fig, ax = new_fig(h=2.8, w=4.2)
    ax.plot(fine, -200.0 * np.sin(np.radians(fine)), color=mpl("reference"), lw=1.2,
            label=r"$-\Omega_q \sin\varphi$")
    ax.plot(phis, meas, "o", color=mpl("fused"), label="simulated")
    ax.set_xlabel(r"demodulator phase error $\varphi$ (deg)")
    ax.set_ylabel("rate bias (deg/s)")
    ax.set_title(r"Quadrature $\Omega_q$ = 200 deg/s equivalent", loc="left")
    ax.legend()
    return fig


# --- D. attitude fusion ---------------------------------------------------------------


@figure("cf_bode")
def fig_cf_bode() -> plt.Figure:
    from teaching_sims.topics.complementary.physics import crossover_hz, transfer_functions

    dt = 0.01
    f = np.logspace(-3, np.log10(50), 400)
    fig, ax = new_fig(h=2.9, w=4.8)
    for alpha, ls in ((0.9, ":"), (0.98, "-"), (0.998, "--")):
        tf = transfer_functions(alpha, dt, f)
        fc = crossover_hz(alpha, dt)
        ax.loglog(f, tf["lowpass"], color=mpl("accel"), ls=ls)
        ax.loglog(f, tf["highpass"], color=mpl("gyro"), ls=ls)
        ax.axvline(fc, color=mpl("fused"), ls=ls, lw=0.9)
        ax.text(fc * 1.1, 2e-3, f"$\\alpha$={alpha}", rotation=90, fontsize=7, color=mpl("fused"))
    ax.plot([], [], color=mpl("accel"), label="accel path (low-pass)")
    ax.plot([], [], color=mpl("gyro"), label="gyro path (high-pass)")
    ax.set_ylim(1e-3, 2)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("gain")
    ax.legend(fontsize=8, loc="lower left")
    return fig


@figure("cf_kf_compare")
def fig_cf_kf_compare() -> plt.Figure:
    from teaching_sims.topics.complementary.physics import process
    from teaching_sims.topics.complementary.scenarios import get_scenario

    p = get_scenario("kalman_bias").params
    out = process(p)
    t = out["t_s"]
    fig, (a1, a2) = new_fig(1, 2, h=3.4, w=5.2, sharex=True)
    a1.plot(t, out["err_accel_deg"], color=mpl("accel"), lw=0.6, alpha=0.7, label="accel only")
    a1.plot(t, out["err_comp_deg"], color=mpl("fused"), lw=1.2, label=f"CF (RMS {out['rms_comp_deg']:.2f})")
    a1.plot(t, out["err_kf_deg"], color=mpl("kalman"), lw=1.2, label=f"KF (RMS {out['rms_kf_deg']:.2f})")
    a1.set_ylim(-4, 4)
    a1.set_ylabel("pitch error (deg)")
    a1.legend(fontsize=7, ncol=3, loc="upper right")
    s = 2 * out["kf_bias_sigma_dps"]
    a2.fill_between(t, out["kf_bias_dps"] - s, out["kf_bias_dps"] + s, color=mpl("kalman"), alpha=0.2)
    a2.plot(t, out["kf_bias_dps"], color=mpl("kalman"), label="KF bias estimate $\\pm2\\sigma$")
    a2.axhline(p.gyro_bias_dps, color=mpl("truth"), lw=1.2, label="true bias")
    a2.set_ylim(-0.5, 2.0)
    a2.set_xlabel("t (s)")
    a2.set_ylabel("deg/s")
    a2.legend(fontsize=7, loc="lower right")
    return fig


@figure("surge_gating")
def fig_surge_gating() -> plt.Figure:
    from dataclasses import replace as _replace

    from teaching_sims.topics.complementary.physics import process
    from teaching_sims.topics.complementary.scenarios import get_scenario

    p = get_scenario("surge_gated").params
    raw = process(_replace(p, gate_accel=False))
    gated = process(p)
    t = raw["t_s"]
    fig, ax = new_fig(h=2.7, w=4.8)
    ax.axvspan(p.surge_start_s, p.surge_start_s + p.surge_dur_s, color=mpl("error"), alpha=0.08, lw=0)
    ax.text(p.surge_start_s + 0.2, 13, "4 m/s$^2$ surge", fontsize=8, color=mpl("error"))
    ax.plot(t, raw["err_comp_deg"], color=mpl("error"), label=f"CF, no gating (RMS {raw['rms_comp_deg']:.1f})")
    ax.plot(t, gated["err_comp_deg"], color=mpl("fused"), label=f"CF, gated (RMS {gated['rms_comp_deg']:.1f})")
    passed = (t >= p.surge_start_s) & (t < p.surge_start_s + p.surge_dur_s) & gated["accel_used"]
    if np.any(passed):
        t_leak = float(t[passed][len(t[passed]) // 2])
        ax.annotate("tilt cancels |f| change:\nspoofed samples pass the gate", xy=(t_leak, 12), xytext=(8.6, 18),
                    fontsize=7, arrowprops=dict(arrowstyle="->", color="0.4"))
    ax.set_xlabel("t (s)")
    ax.set_ylabel("pitch error (deg)")
    ax.set_ylim(-5, 26)
    ax.legend(fontsize=8, loc="upper left")
    return fig


@figure("mahony_observability")
def fig_mahony_observability() -> plt.Figure:
    from teaching_sims.topics.complementary.mahony import MahonyParams, simulate_mahony

    a = simulate_mahony(MahonyParams(use_mag=False))
    b = simulate_mahony(MahonyParams(use_mag=True))
    t = a["t_s"]
    fig, (a1, a2) = new_fig(2, 1, h=2.8, w=6.0)
    a1.plot(t, a["euler_err_deg"][:, 0], color=mpl("error"), label="yaw, no mag")
    a1.plot(t, b["euler_err_deg"][:, 0], color=mpl("mag"), label="yaw, with mag")
    a1.plot(t, a["euler_err_deg"][:, 1], color=mpl("gyro"), lw=1.0, label="pitch (either)")
    a1.set_xlabel("t (s)")
    a1.set_ylabel("error (deg)")
    a1.legend(fontsize=7)
    a2.plot(t, a["bias_est_dps"][:, 2], color=mpl("error"), label="$\\hat b_z$, no mag")
    a2.plot(t, b["bias_est_dps"][:, 2], color=mpl("mag"), label="$\\hat b_z$, with mag")
    a2.plot(t, a["bias_est_dps"][:, 0], color=mpl("accel"), lw=1.0, label="$\\hat b_x$ (either)")
    a2.axhline(a["bias_true_dps"][2], color=mpl("truth"), lw=0.8, ls="--")
    a2.axhline(a["bias_true_dps"][0], color=mpl("truth"), lw=0.8, ls="--")
    a2.set_xlabel("t (s)")
    a2.set_ylabel("bias (deg/s)")
    a2.legend(fontsize=7)
    return fig


# --- E. inertial navigation --------------------------------------------------------------


@figure("ins_error_budget")
def fig_ins_error_budget() -> plt.Figure:
    """Simulated position error vs analytic references (log-log)."""
    from teaching_sims.topics.ins.physics import process
    from teaching_sims.topics.ins.scenarios import get_scenario

    p = get_scenario("error_budget").params
    out = process(p)
    t = out["t_s"][1:]
    fig, ax = new_fig(h=3.2, w=5.2)
    roles = {"init velocity": "reference", "accel bias": "accel", "initial tilt": "mag",
             "pitch gyro bias": "kalman", "yaw gyro bias": "gyro"}
    laws = {"init velocity": r"$\delta v\,t$", "accel bias": r"$\frac{1}{2}b_a t^2$",
            "initial tilt": r"$\frac{1}{2}g\,\delta\theta\,t^2$", "pitch gyro bias": r"$\frac{1}{6}g\,b_g t^3$",
            "yaw gyro bias": r"$\frac{1}{2}v\,\varepsilon\,t^2$"}
    for name, role in roles.items():
        ref = out["references"][name][1:]
        if np.any(ref > 0):
            ax.loglog(t, ref, color=mpl(role), ls="--", lw=1.2, label=f"{name}: {laws[name]}")
    ax.loglog(t, np.maximum(out["pos_err_m"][1:], 1e-4), color=mpl("error"), lw=2.4, label="simulated INS error")
    ax.set_ylim(1e-3, 1e3)
    ax.set_xlabel("t (s)")
    ax.set_ylabel("position error (m)")
    ax.legend(fontsize=7, loc="upper left")
    return fig


@figure("ins_aiding")
def fig_ins_aiding() -> plt.Figure:
    """Unaided vs ZUPT vs position fixes."""
    from dataclasses import replace as _replace

    from teaching_sims.topics.ins.physics import Aiding, process
    from teaching_sims.topics.ins.scenarios import get_scenario

    fig, (a1, a2) = new_fig(2, 1, h=2.9, w=6.2)
    z = get_scenario("zupt").params
    free = process(_replace(z, aiding=Aiding.NONE))
    zupt = process(z)
    fooled = process(get_scenario("zupt_false_detection").params)
    t = free["t_s"]
    a1.axvspan(30, t[-1], color=mpl("accel"), alpha=0.08, lw=0)
    a1.text(31, 1, "parked", fontsize=8, color=mpl("accel"))
    a1.plot(t, free["pos_err_m"], color=mpl("error"), label="unaided")
    a1.plot(t, zupt["pos_err_m"], color=mpl("accel"), label="ZUPT (true stops)")
    a1.plot(t, fooled["pos_err_m"], color=mpl("mag"), ls="--", label="ZUPT (IMU detector)")
    a1.set_yscale("log")
    a1.set_ylim(0.05, 500)
    a1.set_xlabel("t (s)")
    a1.set_ylabel("position error (m)")
    a1.set_title("stop-and-go vehicle", loc="left", fontsize=9)
    a1.legend(fontsize=7, loc="lower right")
    pf = get_scenario("position_fixes").params
    un = process(_replace(pf, aiding=Aiding.NONE))
    fx = process(pf)
    t2 = un["t_s"]
    a2.plot(t2, un["pos_err_m"], color=mpl("error"), label="unaided")
    a2.plot(t2, fx["pos_err_m"], color=mpl("fused"), label=f"fixes every {pf.fix_interval_s:.0f} s")
    a2.set_xlabel("t (s)")
    a2.set_ylabel("position error (m)")
    a2.set_title("circle, gyro + accel bias", loc="left", fontsize=9)
    a2.legend(fontsize=7)
    return fig


@figure("ins_grades")
def fig_ins_grades() -> plt.Figure:
    """One-minute unaided error per grade (calibrated turn-on bias)."""
    from teaching_sims.topics.ins.physics import INSParams, PathProfile, params_for_grade, process

    fig, ax = new_fig(h=2.8, w=4.8)
    for key, c in (("consumer", mpl("error")), ("industrial", mpl("gyro")), ("tactical", mpl("accel"))):
        p = params_for_grade(INSParams(profile=PathProfile.STRAIGHT, perfect_attitude=False, duration_s=120.0), key)
        out = process(p)
        ax.semilogy(out["t_s"][1:], np.maximum(out["pos_err_m"][1:], 1e-3), color=c,
                    label=f"{GRADE_PRESETS[key].name}: {out['pos_err_m'][int(60 * p.fs_hz)]:.1f} m at 60 s")
    ax.set_xlabel("t (s)")
    ax.set_ylabel("position error (m)")
    ax.set_title("Unaided INS, residual biases after calibration", loc="left", fontsize=9)
    ax.legend(fontsize=7, loc="lower right")
    return fig


# --- C. errors and characterisation ------------------------------------------------


@figure("allan_signatures")
def fig_allan_signatures() -> plt.Figure:
    """Allan deviation of each noise term alone and combined (log-log)."""
    fs, dur = 20.0, 6 * 3600.0
    n = int(fs * dur)
    rng = np.random.default_rng(1)
    N, B, K = 2e-3, 5e-4, 2e-5
    terms = {
        "white noise $N$": SensorErrorModel(white_density=N),
        "bias instability $B$": SensorErrorModel(bias_instability=B, bi_corr_time_s=100.0),
        "rate random walk $K$": SensorErrorModel(rrw=K),
    }
    fig, ax = new_fig(h=3.6)
    colors = [mpl("gyro"), mpl("mag"), mpl("accel")]
    combined = np.zeros(n)
    for (label, m), c in zip(terms.items(), colors):
        y = m.apply(np.zeros(n), fs, rng)["meas"]
        combined += y
        tau, ad = allan_deviation(y, fs, n_taus=50)
        keep = tau <= dur / 10
        ax.loglog(tau[keep], ad[keep], color=c, lw=1.2, ls="--", label=label)
    tau, ad = allan_deviation(combined, fs, n_taus=50)
    keep = tau <= dur / 10
    ax.loglog(tau[keep], ad[keep], color=mpl("fused"), lw=2.8, label="sum (what you measure)")
    ax.plot([1.0], [N], "o", color=mpl("gyro"))
    ax.annotate(r"$N=\sigma_A(1\,\mathrm{s})$, slope $-\frac{1}{2}$", xy=(1.0, N), xytext=(2.0, 5e-3), color=mpl("gyro"))
    ax.annotate(r"floor $\approx 0.664\,B$, slope 0", xy=(200.0, 3.3e-4), xytext=(1.5, 3e-5), color=mpl("mag"),
                arrowprops=dict(arrowstyle="->", color=mpl("mag")))
    ax.annotate(r"slope $+\frac{1}{2}$: $K$", xy=(1500.0, K * np.sqrt(1500 / 3)), xytext=(300.0, 1.4e-5),
                color=mpl("accel"), arrowprops=dict(arrowstyle="->", color=mpl("accel")))
    ax.set_xlabel(r"averaging time $\tau$ (s)")
    ax.set_ylabel(r"$\sigma_A(\tau)$ (deg/s)")
    ax.set_ylim(1e-5, 0.1)
    ax.legend(loc="lower left")
    return fig


@figure("gyro_error_growth")
def fig_gyro_error_growth() -> plt.Figure:
    """RMS heading error vs time for each error term alone (log-log)."""
    from teaching_sims.topics.gyroscope.physics import GyroParams, MotionProfile, monte_carlo_errors

    base = dict(profile=MotionProfile.CONSTANT, rate_dps=0.0, bias_dps=0.0, arw_deg_per_sqrt_s=0.0,
                duration_s=600.0, fs_hz=10.0)
    terms = (
        (r"constant bias 10 deg/h $\;\propto t$", dict(bias_dps=10 / 3600), mpl("error"), 1),
        (r"ARW 0.3 deg/$\sqrt{h}$ $\;\propto\sqrt{t}$", dict(arw_deg_per_sqrt_s=0.3 / 60), mpl("gyro"), 60),
        (r"bias instab. 10 deg/h $\;\sim t$ (while correlated)",
         dict(bias_instability_dps=10 / 3600, bi_corr_time_s=100.0), mpl("mag"), 60),
        (r"RRW 30 deg/h/$\sqrt{h}$ $\;\propto t^{3/2}$", dict(rrw_dps_per_sqrt_s=30 / 216000), mpl("accel"), 60),
    )
    fig, ax = new_fig(h=3.1, w=5.0)
    for label, kw, c, runs in terms:
        p = GyroParams(**(base | kw))
        e = monte_carlo_errors(p, n_runs=runs)
        rms = np.sqrt(np.mean(e**2, axis=0))
        t = (np.arange(e.shape[1]) + 1) / p.fs_hz
        ax.loglog(t, rms, color=c, label=label)
    ax.set_xlim(1, 600)
    ax.set_ylim(1e-3, 5)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("RMS heading error (deg)")
    ax.legend(loc="upper left", fontsize=8)
    return fig


@figure("grade_heading_drift")
def fig_grade_heading_drift() -> plt.Figure:
    """Heading error over 10 min per grade, turn-on bias calibrated out (ensemble RMS)."""
    from teaching_sims.topics.gyroscope.physics import GyroParams, MotionProfile, monte_carlo_errors, params_for_grade

    fig, ax = new_fig(h=2.9, w=4.8)
    for key, c in (("consumer", mpl("error")), ("industrial", mpl("gyro")), ("tactical", mpl("accel"))):
        p = params_for_grade(GyroParams(profile=MotionProfile.CONSTANT, rate_dps=0.0, duration_s=600.0, fs_hz=10.0,
                                        compensate_bias=True), key)
        e = monte_carlo_errors(p, n_runs=40)
        t = np.arange(e.shape[1]) / p.fs_hz / 60.0
        ax.semilogy(t[1:], np.sqrt(np.mean(e**2, axis=0))[1:], color=c, label=GRADE_PRESETS[key].name)
    ax.set_xlabel("time (min)")
    ax.set_ylabel("RMS heading error (deg)")
    ax.set_title("Turn-on bias calibrated; in-run errors remain", loc="left")
    ax.legend(fontsize=8)
    return fig


@figure("grade_allan")
def fig_grade_allan() -> plt.Figure:
    """Allan curves for the three grade presets (gyro)."""
    fs, dur = 50.0, 2 * 3600.0
    n = int(fs * dur)
    rng = np.random.default_rng(2)
    fig, ax = new_fig(h=3.4)
    for key, c in zip(("consumer", "industrial", "tactical"), (mpl("error"), mpl("gyro"), mpl("accel"))):
        spec = GRADE_PRESETS[key]
        m = spec.gyro_model()
        y = m.apply(np.zeros(n), fs, rng)["meas"] - m.bias
        tau, ad = allan_deviation(y, fs, n_taus=45)
        ax.loglog(tau, ad * 3600.0, color=c, label=f"{spec.name} ({spec.example})")
    ax.set_xlabel(r"$\tau$ (s)")
    ax.set_ylabel(r"$\sigma_A$ (deg/h)")
    ax.legend(loc="lower left")
    return fig


# --- driver ----------------------------------------------------------------------


def generate(out_dir: Path, only: list[str] | None = None) -> list[Path]:
    _setup_style()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    names = only or list(REGISTRY)
    for name in names:
        fig = REGISTRY[name]()
        path = out_dir / f"{name}.pdf"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("slides/figures/imu"))
    ap.add_argument("--only", nargs="*", default=None, help="subset of figure names")
    ap.add_argument("--list", action="store_true", help="list figure names and exit")
    args = ap.parse_args(argv)
    if args.list:
        print("\n".join(REGISTRY))
        return 0
    for p in generate(args.out, args.only):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
