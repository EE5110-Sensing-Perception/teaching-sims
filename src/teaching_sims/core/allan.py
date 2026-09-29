"""Overlapping Allan deviation and simple noise-term read-off."""

from __future__ import annotations

import numpy as np


def allan_deviation(
    y: np.ndarray,
    fs: float,
    taus: np.ndarray | None = None,
    n_taus: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """Overlapping Allan deviation of a rate signal ``y`` sampled at ``fs``.

    Returns ``(taus, adev)`` in seconds and the units of ``y``. Averaging
    times default to ``n_taus`` log-spaced values from 1/fs to T/5.
    """
    y = np.asarray(y, dtype=float)
    n = y.shape[0]
    if n < 10:
        raise ValueError("need at least 10 samples")
    dt = 1.0 / fs
    if taus is None:
        m_max = max(1, n // 5)
        ms = np.unique(np.logspace(0, np.log10(m_max), n_taus).astype(int))
    else:
        ms = np.unique(np.clip(np.round(np.asarray(taus) * fs).astype(int), 1, n // 2))
    theta = np.concatenate(([0.0], np.cumsum(y) * dt))
    adev = np.empty(ms.shape[0])
    for k, m in enumerate(ms):
        tau = m * dt
        d = theta[2 * m :] - 2.0 * theta[m:-m] + theta[: -2 * m]
        adev[k] = np.sqrt(np.sum(d * d) / (2.0 * tau * tau * d.shape[0]))
    return ms * dt, adev


def read_noise_terms(
    taus: np.ndarray,
    adev: np.ndarray,
    t_total: float | None = None,
) -> dict[str, float]:
    """Read N, B, K off an Allan plot, as done by hand from a datasheet curve.

    Only averaging times with at least ~10 independent clusters
    (tau <= T/10) are trusted. Within that range:

    * N: fit a slope -1/2 line to the short-tau run where the local slope is ~-1/2; N = its value at 1 s
    * B: flat floor (median of the flat points), B = floor / 0.664

    Expect +/-20 % scatter on B and K from a single record of a few hours.
    * K: fit a slope +1/2 line to the long-tau run where the local slope is ~+1/2; K = its value at 3 s

    A term that is absent (no segment with that slope) is reported as NaN.
    """
    taus = np.asarray(taus, dtype=float)
    adev = np.asarray(adev, dtype=float)
    if t_total is None:
        t_total = 2.5 * float(taus[-1])  # default grid ends near T/5
    ok = taus <= t_total / 10.0
    if ok.sum() < 3:
        ok[:] = True
    lt, la = np.log10(taus[ok]), np.log10(adev[ok])
    slope = np.gradient(la, lt)

    def _fixed_slope(target: float, tau_ref: float, from_left: bool) -> tuple[float, float]:
        sel = np.abs(slope - target) < 0.12
        if not np.any(sel):
            return float("nan"), float("nan")
        # keep only the outermost contiguous run (short tau for N, long tau for K)
        idx = np.nonzero(sel)[0]
        run = [idx[0]] if from_left else [idx[-1]]
        seq = idx if from_left else idx[::-1]
        for k in seq[1:]:
            if abs(k - run[-1]) == 1:
                run.append(k)
            else:
                break
        sel = np.zeros_like(sel)
        sel[run] = True
        # intercept of a line with the fixed slope through the selected points
        c = float(np.mean(la[sel] - target * lt[sel]))
        return 10 ** (c + target * np.log10(tau_ref)), float(10 ** np.mean(lt[sel]))

    n_val, tau_n = _fixed_slope(-0.5, 1.0, from_left=True)
    k_val, tau_k = _fixed_slope(0.5, 3.0, from_left=False)
    # Floor: median over every flat (|slope| small) point; the bare minimum
    # of a noisy curve, or the few-cluster points near T/10, are biased low.
    i_b = int(np.argmin(la))
    flat = np.abs(slope) < 0.15
    floor = 10 ** float(np.median(la[flat])) if np.any(flat) else 10 ** float(la[i_b])
    return {
        "N": n_val,
        "B": float(floor / 0.664),
        "K": k_val,
        "tau_N": tau_n,
        "tau_B": float(10 ** lt[i_b]),
        "tau_K": tau_k,
    }
