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
