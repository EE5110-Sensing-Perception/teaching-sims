"""Figures for the IMU study guides (PNG, for Canvas pages).

Usage (from the repo root)::

    python -m teaching_sims.guides.figures --out guides/imu/img
    python -m teaching_sims.guides.figures --only g_random_walk

Two sources:

* ``REUSED``: slide figures from :mod:`teaching_sims.slides.imu_figures`, re-rendered as PNG.
* ``REGISTRY`` here: extra foundational figures (definitions, geometry, intuition)
  that the slides assume. Each figure is a function returning a matplotlib ``Figure``.

"Truth" is always drawn as a dashed line: in the shared palette its dark slate
is too close to the gyro blue for colour-blind readers, so line style carries it.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Arc, FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

from teaching_sims.slides import imu_figures as slides  # noqa: E402
from teaching_sims.slides.imu_figures import new_fig  # noqa: E402
from teaching_sims.ui.palette import mpl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DPI = 150
G = 9.80665

# Slide figures reused as-is (PNG export).
REUSED = (
    "rotation_order", "gimbal_sensitivity", "rate_integration", "coning_dt",
    "mems_accel_response", "mems_gyro_modes", "mems_gyro_quadrature",
    "accel_disturbance_tilt", "accel_vibration_average", "accel_six_position", "lever_arm_tilt",
    "gyro_error_growth", "allan_signatures", "grade_allan", "grade_heading_drift",
    "mag_tilt_error", "mag_iron_calibration",
    "cf_bode", "cf_kf_compare", "surge_gating", "mahony_observability",
    "ins_error_budget", "ins_aiding", "ins_grades",
)
# Static assets copied next to the figures.
ASSETS = {"mems_comb_drive": REPO_ROOT / "tutorials" / "assets" / "mems-comb-drive.png"}

REGISTRY: dict[str, Callable[[], plt.Figure]] = {}

TRUTH = dict(color=mpl("truth"), ls="--", lw=1.6)


def figure(name: str):
    def deco(fn: Callable[[], plt.Figure]):
        REGISTRY[name] = fn
        return fn

    return deco


def _arrow(ax, p0, p1, color, lw=2.0, label=None, label_xy=None, fs=9, **kw):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14, color=color, lw=lw, **kw))
    if label:
        x, y = label_xy if label_xy is not None else p1
        ax.text(x, y, label, color=color, fontsize=fs, ha="center", va="center")


def _schematic(ax, xlim, ylim):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.set_axis_off()


# --- 1. frames and rotations ------------------------------------------------------------


def _arrow3(ax, v, color, label, lw=2.0, ls="-"):
    ax.plot([0, v[0]], [0, v[1]], [0, v[2]], color=color, lw=lw, ls=ls)
    ax.text(*(np.asarray(v) * 1.15), label, color=color, fontsize=9, ha="center", va="center")


@figure("g_frames_conventions")
def fig_frames_conventions() -> plt.Figure:
    """One physical pose, two labelings: NED/FRD vs ENU/FLU."""
    fig = plt.figure(figsize=(7.2, 3.4), constrained_layout=True)
    yaw = np.radians(30.0)  # nose 30 deg east of north
    fwd = np.array([np.sin(yaw), np.cos(yaw), 0.0])  # plot coords: x=E, y=N, z=Up
    left = np.array([-np.cos(yaw), np.sin(yaw), 0.0])
    up = np.array([0.0, 0.0, 1.0])
    rgb = slides._AX_RGB
    panels = (
        ("Aerospace: NED nav, FRD body", (("N", [0, 1, 0]), ("E", [1, 0, 0]), ("D", [0, 0, -1])),
         (("x fwd", fwd), ("y right", -left), ("z down", -up))),
        ("ROS REP-103: ENU nav, FLU body", (("E", [1, 0, 0]), ("N", [0, 1, 0]), ("U", [0, 0, 1])),
         (("x fwd", fwd), ("y left", left), ("z up", up))),
    )
    for k, (title, nav, body) in enumerate(panels):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        for lab, v in nav:
            _arrow3(ax, np.array(v, float) * 1.4, "0.55", lab, lw=1.0)
        for (lab, v), c in zip(body, rgb):
            _arrow3(ax, v * 0.95, c, lab, lw=2.4)
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-1.3, 1.3)
        ax.set_zlim(-1.3, 1.3)
        ax.set_box_aspect((1, 1, 1), zoom=1.25)
        ax.view_init(elev=20, azim=-60)
        ax.set_axis_off()
        ax.set_title(title, fontsize=10)
    fig.text(0.5, 0.02, "Same vehicle, same pose (nose 30° east of north, level). Only the axis labels and signs change.",
             ha="center", fontsize=8.5, color="0.35")
    return fig


@figure("g_dcm_2d")
def fig_dcm_2d() -> plt.Figure:
    """Top view: a 30 deg yaw; the DCM columns are the body axes written in nav coordinates."""
    fig, ax = new_fig(w=4.6, h=4.0)
    psi = np.radians(30.0)
    # plot x = East, plot y = North
    _arrow(ax, (0, 0), (0, 1.25), "0.5", lw=1.2, label="N (nav x)", label_xy=(0, 1.38))
    _arrow(ax, (0, 0), (1.25, 0), "0.5", lw=1.2, label="E (nav y)", label_xy=(1.45, -0.08))
    bx = np.array([np.sin(psi), np.cos(psi)])
    by = np.array([np.cos(psi), -np.sin(psi)])
    _arrow(ax, (0, 0), tuple(bx), slides._AX_RGB[0], lw=2.4)
    _arrow(ax, (0, 0), tuple(by), slides._AX_RGB[1], lw=2.4)
    ax.text(bx[0] + 0.05, bx[1] + 0.07, r"body $x$ = $[\cos\psi,\ \sin\psi,\ 0]^\top$" "\n= [0.866, 0.500, 0]",
            color=slides._AX_RGB[0], fontsize=8.5, va="bottom")
    ax.text(by[0] + 0.05, by[1] - 0.05, r"body $y$ = $[-\sin\psi,\ \cos\psi,\ 0]^\top$" "\n= [-0.500, 0.866, 0]",
            color=slides._AX_RGB[1], fontsize=8.5, va="top")
    ax.plot([bx[0], bx[0]], [0, bx[1]], color="0.7", lw=0.8, ls=":")
    ax.plot([0, bx[0]], [bx[1], bx[1]], color="0.7", lw=0.8, ls=":")
    ax.add_patch(Arc((0, 0), 0.7, 0.7, theta1=60, theta2=90, color=mpl("cursor"), lw=1.5))
    ax.text(0.12, 0.42, r"$\psi$=30°", color="0.3", fontsize=9)
    ax.text(-0.35, -0.55, "Written as components (N, E, D).\nBody z = D = [0, 0, 1] (into the page).",
            fontsize=8, color="0.35")
    _schematic(ax, (-0.45, 2.2), (-0.75, 1.5))
    return fig


@figure("g_quat_double_cover")
def fig_quat_double_cover() -> plt.Figure:
    """R repeats every 360 deg, q only every 720 deg: q and -q are the same rotation."""
    a = np.linspace(0, 720, 721)
    fig, ax = new_fig(w=5.6, h=2.8)
    ax.plot(a, np.cos(np.radians(a)), color=mpl("gyro"), label=r"DCM entry $R_{11}=\cos\alpha$")
    ax.plot(a, np.cos(np.radians(a) / 2), color=mpl("fused"), label=r"quaternion $q_w=\cos(\alpha/2)$")
    for x, txt in ((360, "same R, q flipped sign"), (720, "back to start")):
        ax.axvline(x, color=mpl("reference"), lw=0.8, ls=":")
        ax.text(x - 8, -1.25, txt, fontsize=8, ha="right", color="0.35")
    ax.set_xticks(range(0, 721, 90))
    ax.set_ylim(-1.35, 1.2)
    ax.set_xlabel(r"rotation angle $\alpha$ about a fixed axis (deg)")
    ax.legend(loc="upper center", ncol=2, fontsize=8)
    return fig


# --- 2. MEMS accelerometer ----------------------------------------------------------------


@figure("g_msd_step")
def fig_msd_step() -> plt.Figure:
    """Normalised step response of a spring-mass-damper for several damping ratios."""
    from scipy.signal import lti, step

    w0 = 2 * np.pi
    t = np.linspace(0, 4, 800)
    fig, ax = new_fig(w=5.4, h=3.0)
    for z, c, ls in ((0.1, mpl("error"), "-"), (0.35, mpl("mag"), "-"), (0.707, mpl("gyro"), "-"),
                     (2.0, mpl("accel"), "-.")):
        _, y = step(lti([w0**2], [1, 2 * z * w0, w0**2]), T=t)
        ax.plot(t, y, color=c, ls=ls, label=rf"$\zeta$ = {z:g}")
    ax.axhline(1.0, **{**TRUTH, "lw": 1.0})
    ax.text(3.95, 1.04, "input (step)", ha="right", fontsize=8, color="0.3")
    ax.set_xlabel(r"time in periods of the natural frequency, $t f_0$")
    ax.set_ylabel("output / input")
    ax.legend(loc="lower right", fontsize=8, ncol=2)
    ax.set_title("Step response of a second-order sensor", loc="left")
    return fig


@figure("g_comb_capacitance")
def fig_comb_capacitance() -> plt.Figure:
    """Parallel-plate comb: single sides are nonlinear, the difference is nearly linear."""
    from teaching_sims.topics.mems_accel.physics import MEMSAccelParams, capacitance_f

    p = MEMSAccelParams()
    x = np.linspace(-0.8e-6, 0.8e-6, 301)
    c1, c2, dc = capacitance_f(p, x)
    c0 = capacitance_f(p, np.array([0.0]))[0][0]
    fig, ax = new_fig(w=5.2, h=3.0)
    xu = x * 1e6
    ax.plot(xu, c1 * 1e15, color=mpl("gyro"), label=r"$C_1 \propto 1/(g_0-x)$")
    ax.plot(xu, c2 * 1e15, color=mpl("accel"), label=r"$C_2 \propto 1/(g_0+x)$")
    ax.plot(xu, dc * 1e15, color=mpl("fused"), label=r"$\Delta C = C_1 - C_2$")
    ax.plot(xu, 2 * c0 * x / (p.gap0_um * 1e-6) * 1e15, color=mpl("reference"), ls=":", lw=1.2,
            label=r"linear approx. $2C_0x/g_0$")
    ax.set_xlabel(r"proof-mass displacement $x$ ($\mu$m), gap $g_0$ = 2 $\mu$m")
    ax.set_ylabel("capacitance (fF)")
    ax.legend(fontsize=8, loc="upper left")
    return fig


@figure("g_aliasing")
def fig_aliasing() -> plt.Figure:
    """A 1100 Hz vibration sampled at 1 kHz looks like a 100 Hz signal."""
    t = np.linspace(0, 0.02, 4000)
    ts = np.arange(0, 0.02 + 1e-9, 1e-3)
    fig, ax = new_fig(w=5.6, h=2.6)
    ax.plot(t * 1e3, np.sin(2 * np.pi * 1100 * t), color=mpl("measured"), lw=0.9, label="true vibration, 1100 Hz")
    ax.plot(t * 1e3, np.sin(2 * np.pi * 100 * t), color=mpl("fused"), ls="--", lw=1.4, label="what the samples suggest, 100 Hz")
    ax.plot(ts * 1e3, np.sin(2 * np.pi * 1100 * ts), "o", color=mpl("gyro"), ms=6, label="samples at 1 kHz")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("acceleration (norm.)")
    ax.set_ylim(-1.3, 1.8)
    ax.legend(loc="upper center", ncol=3, fontsize=7.5)
    return fig


# --- 3. MEMS gyroscope ---------------------------------------------------------------------


@figure("g_coriolis_phase")
def fig_coriolis_phase() -> plt.Figure:
    """Drive displacement, drive velocity, and the two forces on the sense axis."""
    ph = np.linspace(0, 4 * np.pi, 600)
    fig, axs = new_fig(nrows=2, w=5.8, h=3.8, sharex=True)
    axs[0].plot(ph / (2 * np.pi), np.sin(ph), color=mpl("gyro"), label=r"drive displacement $x=A\sin\omega_d t$")
    axs[0].plot(ph / (2 * np.pi), np.cos(ph), color=mpl("accel"), ls="-.", label=r"drive velocity $\dot x$")
    axs[0].legend(fontsize=8, loc="upper right", ncol=2)
    axs[0].set_ylim(-1.4, 1.9)
    axs[1].plot(ph / (2 * np.pi), -np.cos(ph), color=mpl("fused"), label=r"Coriolis $-2\Omega\dot x$ (follows velocity)")
    axs[1].plot(ph / (2 * np.pi), -0.6 * np.sin(ph), color=mpl("mag"), ls="--",
                label=r"quadrature $-(k_{xy}/m)\,x$ (follows displacement)")
    axs[1].legend(fontsize=8, loc="upper right", ncol=1)
    axs[1].set_ylim(-1.4, 2.2)
    axs[1].set_xlabel("drive cycles")
    axs[0].set_ylabel("drive axis")
    axs[1].set_ylabel("force on sense axis")
    return fig


@figure("g_mass_path")
def fig_mass_path() -> plt.Figure:
    """Proof-mass path (x, y) for pure Coriolis (ellipse) vs pure quadrature (tilted line)."""
    ph = np.linspace(0, 2 * np.pi, 400)
    fig, axs = new_fig(ncols=2, w=5.6, h=2.8)
    for ax, y, c, title in ((axs[0], 0.35 * np.cos(ph), mpl("fused"), "rotation: Coriolis"),
                            (axs[1], 0.35 * np.sin(ph), mpl("mag"), "quadrature (no rotation)")):
        ax.plot(np.sin(ph), y, color=c)
        ax.set_aspect("equal")
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-0.6, 0.6)
        ax.set_xlabel("drive x")
        ax.set_title(title, fontsize=10)
    axs[0].set_ylabel("sense y (exaggerated)")
    return fig


@figure("g_demodulation")
def fig_demodulation() -> plt.Figure:
    """Synchronous demodulation: multiply by the reference, low-pass, get the rate."""
    from scipy.signal import butter, filtfilt

    fs, fc = 20_000.0, 200.0
    t = np.arange(0, 0.12, 1 / fs)
    rate = np.where(t > 0.03, 1.0, 0.0) + np.where(t > 0.08, -0.5, 0.0)
    sense = rate * np.cos(2 * np.pi * fc * t)
    prod = sense * 2 * np.cos(2 * np.pi * fc * t)
    b, a = butter(2, 60 / (fs / 2))
    out = filtfilt(b, a, prod)
    fig, axs = new_fig(nrows=3, w=6.0, h=4.6, sharex=True)
    axs[0].plot(t * 1e3, sense, color=mpl("gyro"), lw=0.7)
    axs[0].set_ylabel("sense y")
    axs[0].set_title(r"1) sense signal: carrier at $f_d$, amplitude $\propto$ rate", loc="left", fontsize=9)
    axs[1].plot(t * 1e3, prod, color=mpl("measured"), lw=0.7)
    axs[1].set_ylabel("y × ref")
    axs[1].set_title(r"2) multiply by reference: DC term $\propto$ rate, plus ripple at $2f_d$", loc="left", fontsize=9)
    axs[2].plot(t * 1e3, rate, **TRUTH, label="true rate")
    axs[2].plot(t * 1e3, out, color=mpl("fused"), label="low-pass output")
    axs[2].set_ylabel("rate")
    axs[2].set_title("3) low-pass filter removes $2f_d$: the rate estimate", loc="left", fontsize=9)
    axs[2].legend(fontsize=8, loc="upper right")
    axs[2].set_xlabel("time (ms)  (carrier slowed to 200 Hz for visibility)")
    return fig


@figure("g_iq_phasor")
def fig_iq_phasor() -> plt.Figure:
    """Phasor view: a reference phase error leaks the large quadrature into the rate channel."""
    fig, ax = new_fig(w=5.4, h=4.0)
    phi = np.radians(15.0)  # exaggerated for visibility
    ax.plot([-1.0, 1.6], [0, 0], color="0.75", lw=0.8)
    ax.plot([0, 0], [-0.5, 1.5], color="0.75", lw=0.8)
    ax.text(1.62, 0.0, "I (in phase with\ndrive velocity)", fontsize=7.5, color="0.45", va="center")
    ax.text(0.03, 1.5, "Q (in phase with drive displacement)", fontsize=7.5, color="0.45")
    _arrow(ax, (0, 0), (0.7, 0), mpl("fused"), lw=2.4)
    ax.text(0.35, 0.07, r"Coriolis $\Omega$", color=mpl("fused"), fontsize=9, ha="center")
    _arrow(ax, (0, 0), (0, 1.3), mpl("mag"), lw=2.4)
    ax.text(0.05, 0.9, "quadrature $\\Omega_q$\n(often $\\gg\\Omega$)", color=mpl("mag"), fontsize=9)
    u = np.array([np.cos(phi), -np.sin(phi)])
    ax.plot([-0.9 * u[0], 1.5 * u[0]], [-0.9 * u[1], 1.5 * u[1]], color="0.25", lw=1.2, ls="--")
    ax.text(1.5 * u[0] - 0.1, 1.5 * u[1] - 0.2, "demodulator axis\n(phase error φ)", fontsize=8, color="0.25")
    ax.add_patch(Arc((0, 0), 1.0, 1.0, theta1=-15, theta2=0, color=mpl("cursor"), lw=1.5))
    ax.text(0.53, -0.1, "φ", fontsize=10, color="0.3")
    pq = np.dot([0, 1.3], u) * u
    ax.plot([0, pq[0]], [1.3, pq[1]], color=mpl("mag"), lw=0.8, ls=":")
    ax.plot([0, pq[0]], [0, pq[1]], color=mpl("error"), lw=4, solid_capstyle="butt")
    ax.text(pq[0] - 0.05, pq[1] + 0.12, "leak into rate output\n" r"$= -\Omega_q\sin\varphi$ (a bias)",
            color=mpl("error"), fontsize=8.5, ha="right")
    _schematic(ax, (-1.3, 2.3), (-0.5, 1.65))
    return fig


# --- 4. accelerometer --------------------------------------------------------------------------


@figure("g_specific_force_cases")
def fig_specific_force_cases() -> plt.Figure:
    """Specific force f = a - g in three situations."""
    fig, axs = new_fig(ncols=3, w=7.2, h=3.0)
    cases = (
        ("at rest on a table", (0, 0), "f = −g: reads 1 g UP"),
        ("free fall", (0, -1), "a = g, so f = 0"),
        ("car accelerating\nforward at 0.5 g", (0.5, 0), "f = a − g: up and forward"),
    )
    for ax, (title, a, txt) in zip(axs, cases):
        ax.add_patch(Rectangle((-0.3, -0.2), 0.6, 0.4, color="0.85"))
        _arrow(ax, (0, 0), (0, -1), mpl("reference"), label="g", label_xy=(0.14, -0.9))
        if a != (0, 0):
            off = 0.12 if a[0] == 0 else 0.0
            _arrow(ax, (off, 0), (a[0] + off, a[1]), mpl("mag"), label="a", label_xy=(a[0] + off + 0.13, a[1] + 0.25))
        f = (a[0], a[1] + 1)
        if np.hypot(*f) > 1e-6:
            _arrow(ax, (0, 0), f, mpl("accel"), lw=2.6, label="f", label_xy=(f[0] + 0.12, f[1] + 0.05))
        else:
            ax.plot(0, 0, "o", color=mpl("accel"), ms=7)
        ax.set_title(title, fontsize=9.5)
        ax.text(0, -1.35, txt, fontsize=8.5, ha="center", color="0.3")
        _schematic(ax, (-0.9, 0.9), (-1.5, 1.3))
    return fig


@figure("g_tilt_geometry")
def fig_tilt_geometry() -> plt.Figure:
    """Side view: pitched body, f = -g resolved into body x and z components."""
    fig, ax = new_fig(w=5.0, h=3.4)
    th = np.radians(25.0)
    xb = np.array([np.cos(th), np.sin(th)])  # body forward (nose up)
    zb = np.array([np.sin(th), -np.cos(th)])  # body down
    body = np.array([[-0.8, -0.12], [0.8, -0.12], [0.8, 0.12], [-0.8, 0.12]])
    rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    pts = body @ rot.T
    ax.fill(pts[:, 0], pts[:, 1], color="0.85")
    ax.plot([-1.4, 1.5], [0, 0], color="0.6", lw=0.8, ls=":")
    _arrow(ax, (0, 0), tuple(xb * 1.3), slides._AX_RGB[0], label=r"body $x$", label_xy=tuple(xb * 1.45))
    _arrow(ax, (0, 0), tuple(zb * 1.0), slides._AX_RGB[2], label=r"body $z$", label_xy=tuple(zb * 1.15))
    f = np.array([0, 1.0])
    _arrow(ax, (0, 0), tuple(f), mpl("accel"), lw=2.6, label=r"$\mathbf{f}=-\mathbf{g}$", label_xy=(-0.18, 1.08))
    fx = np.dot(f, xb) * xb
    fz = np.dot(f, zb) * zb
    ax.plot([f[0], fx[0]], [f[1], fx[1]], color="0.6", lw=0.8, ls=":")
    ax.plot([0, fx[0]], [0, fx[1]], color=mpl("fused"), lw=3.2)
    ax.plot([0, fz[0]], [0, fz[1]], color=mpl("gyro"), lw=3.2)
    ax.text(fx[0] - 0.2, fx[1] + 0.12, r"$f_x = +g\sin\theta$", color=mpl("fused"), fontsize=9)
    ax.text(fz[0] - 0.95, fz[1] + 0.1, r"$f_z = -g\cos\theta$", color=mpl("gyro"), fontsize=9)
    ax.add_patch(Arc((0, 0), 1.0, 1.0, theta1=0, theta2=25, color=mpl("cursor"), lw=1.5))
    ax.text(0.55, 0.1, r"$\theta$", fontsize=10, color="0.3")
    _schematic(ax, (-1.4, 1.9), (-1.0, 1.35))
    return fig


@figure("g_scale_vs_pitch")
def fig_scale_vs_pitch() -> plt.Figure:
    """Pitch error vs true pitch for bias, x scale error and x-z misalignment: each varies differently with tilt."""
    from teaching_sims.topics.accelerometer.physics import AccelParams, process

    pitches = np.linspace(-60, 60, 25)
    fig, ax = new_fig(w=5.0, h=2.8)
    for kw, c, lab in (({"scale_x_pct": 2.0}, mpl("gyro"), "2 % scale error on x"),
                       ({"mis_xz_mrad": 10.0}, mpl("mag"), "10 mrad x–z misalignment"),
                       ({"bias_x_mps2": 0.1}, mpl("fused"), "0.1 m/s² bias on x")):
        err = [process(AccelParams(roll_deg=0.0, pitch_deg=float(p), noise_mps2=0.0, duration_s=0.5, **kw))["pitch_mean_deg"]
               - p for p in pitches]
        ax.plot(pitches, err, color=c, label=lab)
    ax.axhline(0, color="0.6", lw=0.8)
    ax.set_xlabel("true pitch (deg)")
    ax.set_ylabel("pitch error (deg)")
    ax.legend(fontsize=8, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 1.0))
    return fig


# --- 5. gyroscope ----------------------------------------------------------------------------------


@figure("g_random_walk")
def fig_random_walk() -> plt.Figure:
    """Integrated white rate noise: zero-mean spread growing as N sqrt(t)."""
    rng = np.random.default_rng(4)
    fs, n_t, n_runs, N = 100.0, 3000, 40, 0.4  # N in deg/sqrt(s)
    t = np.arange(1, n_t + 1) / fs
    w = rng.normal(0, N * np.sqrt(fs), (n_runs, n_t))
    ang = np.cumsum(w, axis=1) / fs
    fig, ax = new_fig(w=5.6, h=3.0)
    for k in range(n_runs):
        ax.plot(t, ang[k], color=mpl("measured"), lw=0.6, alpha=0.7)
    ax.plot(t, ang[0], color=mpl("gyro"), lw=1.4, label="one run")
    for s in (1, -1):
        ax.plot(t, s * N * np.sqrt(t), color=mpl("fused"), lw=1.8, label=r"$\pm N\sqrt{t}$ (1σ)" if s > 0 else None)
        ax.plot(t, s * 2 * N * np.sqrt(t), color=mpl("fused"), lw=1.0, ls=":", label=r"$\pm 2N\sqrt{t}$" if s > 0 else None)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("heading error (deg)")
    ax.set_title(r"40 runs, ARW $N$ = 0.4°/$\sqrt{s}$, no bias", loc="left")
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    return fig


@figure("g_noise_vs_rate")
def fig_noise_vs_rate() -> plt.Figure:
    """Same noise density at two sample rates: raw spread differs, 1 s averages agree."""
    rng = np.random.default_rng(1)
    N = 0.01  # deg/s/sqrt(Hz) = 0.6 deg/sqrt(h)
    fig, axs = new_fig(ncols=2, w=6.6, h=2.8, sharey=True)
    for ax, fs, c in ((axs[0], 100, mpl("gyro")), (axs[1], 1000, mpl("mag"))):
        n = int(10 * fs)
        x = rng.normal(0, N * np.sqrt(fs), n)
        t = np.arange(n) / fs
        ax.plot(t, x, color=c, lw=0.5, alpha=0.8, label=rf"samples: $\sigma$ = {N * np.sqrt(fs):.2f} °/s")
        avg = x.reshape(10, -1).mean(axis=1)
        ax.step(np.arange(11), np.r_[avg, avg[-1]], where="post", color=mpl("fused"), lw=2,
                label=rf"1 s averages: $\sigma$ ≈ {N:.2f} °/s")
        ax.set_title(f"{fs} Hz sampling", fontsize=10)
        ax.set_xlabel("time (s)")
        ax.legend(fontsize=7.5, loc="lower left")
    axs[0].set_ylabel("rate noise (deg/s)")
    axs[0].set_ylim(-1.3, 1.1)
    return fig


@figure("g_allan_clusters")
def fig_allan_clusters() -> plt.Figure:
    """How Allan variance is computed: cluster averages and their successive differences."""
    rng = np.random.default_rng(2)
    fs, T = 50, 20.0
    t = np.arange(int(fs * T)) / fs
    x = 0.4 * rng.standard_normal(t.size) + 0.45 * np.sin(2 * np.pi * t / 9)
    fig, ax = new_fig(w=6.0, h=2.8)
    ax.plot(t, x, color=mpl("measured"), lw=0.5)
    tau = 2.0
    m = int(tau * fs)
    k = t.size // m
    avg = x[: k * m].reshape(k, m).mean(axis=1)
    for i in range(k):
        ax.plot([i * tau, (i + 1) * tau], [avg[i], avg[i]], color=mpl("fused"), lw=2.4)
    for i in range(3):
        xm = (i + 1) * tau
        ax.annotate("", xy=(xm, avg[i + 1]), xytext=(xm, avg[i]),
                    arrowprops=dict(arrowstyle="<->", color=mpl("gyro"), lw=1.2))
    ax.text(1.0 * tau + 0.2, max(avg[:4]) + 0.25, r"$\bar\omega_{k+1}-\bar\omega_k$", color=mpl("gyro"), fontsize=9)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("rate at rest (deg/s)")
    ax.set_title(r"cluster length $\tau$ = 2 s:  $\sigma_A^2(\tau)=\frac{1}{2}\langle(\bar\omega_{k+1}-\bar\omega_k)^2\rangle$",
                 loc="left", fontsize=10)
    ax.set_ylim(-1.6, 1.6)
    return fig


# --- 6. magnetometer --------------------------------------------------------------------------------


@figure("g_earth_field")
def fig_earth_field() -> plt.Figure:
    """Earth field geometry: dip (side view) and declination (top view)."""
    fig, axs = new_fig(ncols=2, w=7.0, h=3.2)
    ax = axs[0]
    inc = np.radians(66.0)
    F = 1.6
    H, Z = F * np.cos(inc), F * np.sin(inc)
    ax.plot([-0.2, 1.4], [0, 0], color="0.6", lw=0.8)
    _arrow(ax, (0, 0), (H, -Z), mpl("mag"), lw=2.6, label="B (F ≈ 49 µT)", label_xy=(H / 2 - 0.45, -Z / 2 - 0.1))
    _arrow(ax, (0, 0), (H, 0), mpl("gyro"), label="H ≈ 20 µT", label_xy=(H + 0.15, 0.15))
    _arrow(ax, (H, 0), (H, -Z), mpl("accel"), label="Z ≈ 45 µT", label_xy=(H + 0.42, -Z / 2))
    ax.add_patch(Arc((0, 0), 0.9, 0.9, theta1=-66, theta2=0, color=mpl("cursor"), lw=1.5))
    ax.text(0.22, -0.2, "I = 66°", fontsize=8.5, color="0.3")
    ax.text(-0.25, 0.35, "horizontal, toward magnetic north", fontsize=8, color="0.4")
    ax.set_title("side view: inclination (dip)", fontsize=10)
    _schematic(ax, (-0.3, 1.6), (-1.7, 0.5))
    ax = axs[1]
    D = np.radians(12.0)
    _arrow(ax, (0, 0), (0, 1.3), "0.4", label="true north", label_xy=(0, 1.45))
    _arrow(ax, (0, 0), (1.1 * np.sin(D), 1.1 * np.cos(D)), mpl("mag"), label="magnetic north",
           label_xy=(1.1 * np.sin(D) + 0.45, 1.1 * np.cos(D)))
    psi = np.radians(70.0)
    _arrow(ax, (0, 0), (np.sin(psi), np.cos(psi)), slides._AX_RGB[0], label="vehicle nose",
           label_xy=(np.sin(psi) + 0.1, np.cos(psi) - 0.18))
    ax.add_patch(Arc((0, 0), 1.4, 1.4, theta1=90 - 12, theta2=90, color=mpl("cursor"), lw=1.5))
    ax.text(0.03, 0.78, "D", fontsize=9, color="0.3")
    ax.add_patch(Arc((0, 0), 0.8, 0.8, theta1=20, theta2=90 - 12, color=mpl("mag"), lw=1.2))
    ax.text(0.33, 0.28, r"$\psi_m$", fontsize=9, color=mpl("mag"))
    ax.text(-0.9, -0.45, r"true heading $\psi = \psi_m + D$", fontsize=9, color="0.3")
    ax.set_title("top view: declination", fontsize=10)
    _schematic(ax, (-1.0, 1.6), (-0.6, 1.6))
    return fig


@figure("g_iron_loci")
def fig_iron_loci() -> plt.Figure:
    """Level 360-degree swing: ideal circle, hard-iron shift, soft-iron ellipse."""
    psi = np.linspace(0, 2 * np.pi, 200)
    H = 20.0
    b = np.stack([H * np.cos(psi), -H * np.sin(psi)])
    soft = np.array([[1.25, 0.18], [0.18, 0.8]])
    fig, ax = new_fig(w=4.6, h=4.0)
    ax.plot(*b, color=mpl("truth"), ls="--", lw=1.4, label="ideal: circle at origin")
    ax.plot(b[0] + 8, b[1] - 5, color=mpl("gyro"), label="hard iron: shifted circle")
    ax.plot(*(soft @ b), color=mpl("mag"), ls="-.", label="soft iron: ellipse")
    ax.plot([0, 8], [0, -5], "o", color=mpl("gyro"), ms=4)
    ax.set_aspect("equal")
    ax.set_xlabel(r"$b_x$ (µT)")
    ax.set_ylabel(r"$b_y$ (µT)")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlim(-32, 42)
    ax.set_ylim(-32, 34)
    return fig


# --- 7. attitude fusion ---------------------------------------------------------------------------------


@figure("g_cf_signals")
def fig_cf_signals() -> plt.Figure:
    """Why fuse: gyro drifts, accel is noisy, the complementary filter keeps the best of each."""
    from teaching_sims.topics.complementary.physics import process
    from teaching_sims.topics.complementary.scenarios import get_scenario

    o = process(get_scenario("balanced_sine").params)
    t = o["t_s"]
    fig, ax = new_fig(w=6.0, h=3.0)
    ax.plot(t, o["accel_tilt_deg"], color=mpl("accel"), lw=0.6, alpha=0.8, label="accel tilt (noisy, no drift)")
    ax.plot(t, o["gyro_only_deg"], color=mpl("gyro"), lw=1.4, label="gyro integrated (smooth, drifts)")
    ax.plot(t, o["comp_deg"], color=mpl("fused"), lw=1.8, label="complementary filter")
    ax.plot(t, o["pitch_true_deg"], **TRUTH, label="truth")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("pitch (deg)")
    ax.legend(fontsize=7.5, loc="lower left", ncol=2)
    ax.set_ylim(-45, 40)
    return fig


@figure("g_lowpass_step")
def fig_lowpass_step() -> plt.Figure:
    """First-order low-pass step response: 63 % at t = tau, 95 % at 3 tau."""
    tau = 0.5
    t = np.linspace(0, 3, 400)
    y = 1 - np.exp(-t / tau)
    fig, ax = new_fig(w=4.8, h=2.8)
    ax.plot(t, np.ones_like(t), **TRUTH, label="input step")
    ax.plot(t, y, color=mpl("fused"), label=r"output $1-e^{-t/\tau}$")
    for k, lab in ((1, "63 %"), (3, "95 %")):
        ax.plot([k * tau, k * tau], [0, 1 - np.exp(-k)], color=mpl("reference"), lw=0.8, ls=":")
        ax.plot(k * tau, 1 - np.exp(-k), "o", color=mpl("cursor"), ms=6)
        ax.text(k * tau + 0.05, 1 - np.exp(-k) - 0.12, f"{lab} at {k}τ", fontsize=8)
    ax.set_xlabel(r"time (s), $\tau$ = 0.5 s")
    ax.set_ylabel("output")
    ax.legend(fontsize=8, loc="lower right")
    return fig


@figure("g_kalman_gaussians")
def fig_kalman_gaussians() -> plt.Figure:
    """1-D Kalman update: product of prediction and measurement Gaussians."""
    x = np.linspace(-2, 10, 600)

    def gauss(m, s):
        return np.exp(-0.5 * ((x - m) / s) ** 2) / (s * np.sqrt(2 * np.pi))

    mp, sp, mz, sz = 3.0, 1.5, 6.0, 1.0
    k = sp**2 / (sp**2 + sz**2)
    mu, su = mp + k * (mz - mp), np.sqrt((1 - k) * sp**2)
    fig, ax = new_fig(w=5.4, h=2.9)
    ax.plot(x, gauss(mp, sp), color=mpl("gyro"), label=f"prediction (gyro): {mp:g} ± {sp:g}°")
    ax.plot(x, gauss(mz, sz), color=mpl("accel"), ls="-.", label=f"measurement (accel): {mz:g} ± {sz:g}°")
    ax.plot(x, gauss(mu, su), color=mpl("fused"), lw=2.4, label=f"update: {mu:.2f} ± {su:.2f}°  (K = {k:.2f})")
    ax.set_xlabel("pitch (deg)")
    ax.set_ylabel("probability density")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_ylim(0, 0.75)
    return fig


# --- 8. INS ----------------------------------------------------------------------------------------------------


@figure("g_integration_chain")
def fig_integration_chain() -> plt.Figure:
    """A constant accel bias integrates to a velocity ramp and a quadratic position error."""
    b = 0.05
    t = np.linspace(0, 60, 400)
    fig, axs = new_fig(ncols=3, w=7.2, h=2.6)
    for ax, y, lab, c in ((axs[0], np.full_like(t, b), "accel error (m/s²)", mpl("accel")),
                          (axs[1], b * t, "velocity error (m/s)", mpl("gyro")),
                          (axs[2], 0.5 * b * t**2, "position error (m)", mpl("fused"))):
        ax.plot(t, y, color=c)
        ax.set_title(lab, fontsize=9.5)
        ax.set_xlabel("time (s)")
        ax.set_ylim(0, None)
    axs[0].set_ylim(0, 0.08)
    axs[1].text(3, 2.6, r"$b\,t$", fontsize=11, color=mpl("gyro"))
    axs[2].text(3, 75, r"$\frac{1}{2} b\,t^2$", fontsize=11, color=mpl("fused"))
    axs[0].text(3, 0.057, r"$b$ = 0.05 m/s² ≈ 5 mg", fontsize=8.5, color="0.3")
    axs[2].text(4, 55, "90 m at 60 s", fontsize=8.5, color="0.3")
    return fig


@figure("g_gravity_leak")
def fig_gravity_leak() -> plt.Figure:
    """A tilt error rotates g into the horizontal: an apparent acceleration g sin(dtheta)."""
    fig, ax = new_fig(w=4.8, h=3.2)
    d = np.radians(12.0)  # exaggerated
    ax.plot([-1.3, 1.3], [0, 0], color="0.6", lw=0.8, ls=":")
    ax.text(-1.25, 0.06, "true level", fontsize=8, color="0.4")
    ax.plot([-1.3 * np.cos(d), 1.3 * np.cos(d)], [1.3 * np.sin(d), -1.3 * np.sin(d)], color=mpl("error"), lw=1.2)
    ax.text(0.35, -0.42, "level as the INS believes it (tilt δθ)", fontsize=8, color=mpl("error"))
    _arrow(ax, (0, 0), (0, 1.1), mpl("accel"), lw=2.4, label="f = −g (true)", label_xy=(-0.42, 1.0))
    ax.plot([0, 1.1 * np.sin(d)], [0, 1.1 * np.cos(d)], color="0.5", lw=0.8)
    leak = 1.1 * np.sin(d)
    ax.plot([0, leak], [1.1, 1.1], color=mpl("fused"), lw=3.0)
    ax.text(leak + 0.05, 1.1, r"$g\sin\delta\theta \approx g\,\delta\theta$" "\nleaks into 'horizontal'",
            color=mpl("fused"), fontsize=8.5, va="center")
    ax.add_patch(Arc((0, 0), 1.2, 1.2, theta1=90 - 12, theta2=90, color=mpl("cursor"), lw=1.5))
    ax.text(0.03, 0.72, r"$\delta\theta$", fontsize=9)
    _schematic(ax, (-1.35, 1.6), (-0.45, 1.35))
    return fig


@figure("g_mechanisation")
def fig_mechanisation() -> plt.Figure:
    """Strapdown mechanisation block diagram."""
    fig, ax = new_fig(w=7.0, h=2.6)
    boxes = {
        "gyro": (0.0, 1.4, "gyro\n" r"$\tilde{\omega}^b$", mpl("gyro")),
        "att": (2.0, 1.4, "attitude\n" r"$\dot R = R[\omega]_\times$", mpl("gyro")),
        "acc": (0.0, 0.0, "accel\n" r"$\tilde{f}^b$", mpl("accel")),
        "rot": (2.0, 0.0, "rotate\n" r"$R\,\tilde{f}^b$", mpl("fused")),
        "g": (4.0, 0.0, "add gravity\n" r"$+\,g^n$", mpl("fused")),
        "v": (6.0, 0.0, "integrate\n" r"$v^n$", mpl("fused")),
        "p": (8.0, 0.0, "integrate\n" r"$p^n$", mpl("fused")),
    }
    w, h = 1.5, 0.9
    for x, y, txt, c in boxes.values():
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", fc="white", ec=c, lw=1.8))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=8.5)

    def link(a, b, vertical=False):
        xa, ya = boxes[a][:2]
        xb, yb = boxes[b][:2]
        if vertical:
            _arrow(ax, (xa + w / 2, ya), (xb + w / 2, yb + h), "0.3", lw=1.3)
        else:
            _arrow(ax, (xa + w, ya + h / 2), (xb, yb + h / 2), "0.3", lw=1.3)

    link("gyro", "att")
    link("acc", "rot")
    link("att", "rot", vertical=True)
    link("rot", "g")
    link("g", "v")
    link("v", "p")
    ax.text(3.65, 1.9, "attitude error δθ here …", fontsize=8, color=mpl("error"))
    ax.text(3.9, -0.35, "… leaks g·δθ into the acceleration here", fontsize=8, color=mpl("error"))
    _schematic(ax, (-0.2, 9.7), (-0.5, 2.5))
    return fig


# --- generation ---------------------------------------------------------------------------------------------


def all_names() -> list[str]:
    return [*REUSED, *REGISTRY, *ASSETS]


def generate(out_dir: Path, only: list[str] | None = None) -> list[Path]:
    slides._setup_style()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in only or all_names():
        path = out_dir / f"{name}.png"
        if name in ASSETS:
            shutil.copyfile(ASSETS[name], path)
        else:
            fn = REGISTRY.get(name) or slides.REGISTRY[name]
            fig = fn()
            fig.savefig(path, dpi=DPI, facecolor="white")
            plt.close(fig)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("guides/imu/img"))
    ap.add_argument("--only", nargs="*", default=None, help="subset of figure names")
    ap.add_argument("--list", action="store_true", help="list figure names and exit")
    args = ap.parse_args(argv)
    if args.list:
        print("\n".join(all_names()))
        return 0
    for p in generate(args.out, args.only):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
