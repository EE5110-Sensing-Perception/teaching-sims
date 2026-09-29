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

from teaching_sims.core.allan import allan_deviation, read_noise_terms  # noqa: E402
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
    ax.set_ylim(1e-2, 3)
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
