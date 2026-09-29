"""MEMS Coriolis vibratory gyroscope (tuning-fork style, single proof mass model).

A proof mass is driven to oscillate along x at the drive resonance
``x = A sin(w_d t)`` (amplitude held by an AGC loop). Rotation ``Omega`` about
z produces a Coriolis acceleration along y, in phase with the drive
*velocity*:

    y'' + (w_y / Q) y' + w_y^2 y = -2 Omega x'  -  (k_xy / m) x

The second term is **quadrature** coupling (elastic cross-talk from
fabrication imperfections), in phase with drive *displacement*: 90 degrees
from the Coriolis signal. Synchronous demodulation with the (phase-
compensated) velocity reference recovers Omega and rejects quadrature, but
a demodulator phase error ``phi`` leaks it into the output as a bias
``-Omega_q sin(phi)``.

Mode matching (sense frequency = drive frequency) multiplies sensitivity by
~Q but narrows the rate bandwidth to ~f/(2Q).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.signal import butter, lfilter, lsim

from teaching_sims.core.imu import DEG2RAD, RAD2DEG


class RateProfile(str, Enum):
    ZERO = "zero"
    STEP = "step"
    SINE = "sine"


@dataclass(frozen=True)
class MEMSGyroParams:
    drive_hz: float = 5000.0
    drive_amp_um: float = 5.0
    sense_split_hz: float = 300.0  # f_sense - f_drive (0 = mode matched)
    q_sense: float = 200.0
    # Rotation input
    profile: RateProfile = RateProfile.STEP
    rate_dps: float = 100.0
    rate_hz: float = 20.0  # for SINE
    step_time_s: float = 0.05
    # Imperfections
    quadrature_dps: float = 0.0  # quadrature expressed as an equivalent rate
    demod_phase_err_deg: float = 0.0
    pickoff_noise_pm: float = 0.0  # white displacement noise per sample (picometres rms)
    # Readout
    lpf_hz: float = 100.0
    duration_s: float = 0.3
    fs_hz: float = 100_000.0
    seed: int = 0

    def __post_init__(self) -> None:
        if self.drive_hz <= 0 or self.fs_hz < 8 * self.drive_hz:
            raise ValueError("need drive_hz > 0 and fs_hz >= 8 drive_hz")
        if self.q_sense <= 0.5:
            raise ValueError("q_sense must exceed 0.5")
        if self.duration_s <= 0 or self.lpf_hz <= 0:
            raise ValueError("duration_s and lpf_hz must be positive")

    @property
    def w_d(self) -> float:
        return 2.0 * np.pi * self.drive_hz

    @property
    def w_y(self) -> float:
        return 2.0 * np.pi * (self.drive_hz + self.sense_split_hz)


def sense_tf(params: MEMSGyroParams, w: np.ndarray | float) -> np.ndarray:
    """Sense-mode transfer Y/U = 1 / (w_y^2 - w^2 + j w w_y / Q)."""
    w = np.asarray(w, dtype=float)
    wy = params.w_y
    return 1.0 / (wy * wy - w * w + 1j * w * wy / params.q_sense)


def sensitivity_nm_per_dps(params: MEMSGyroParams) -> float:
    """Sense amplitude (nm) per deg/s of rotation, at DC rate."""
    h0 = np.abs(sense_tf(params, params.w_d))
    return float(2.0 * DEG2RAD * params.drive_amp_um * 1e-6 * params.w_d * h0 * 1e9)


def rate_frequency_response(params: MEMSGyroParams, f_rate_hz: np.ndarray, include_lpf: bool = True) -> np.ndarray:
    """Complex rate-in -> rate-out response after ideal demodulation (1 at DC).

    A rate at w_r puts Coriolis sidebands at w_d +/- w_r; each is shaped by the
    sense mode before demodulation folds them back:
    G = (H(w_d + w_r) e^{-j<H0} + conj(H(w_d - w_r)) e^{+j<H0}) / (2 |H0|).
    """
    wr = 2.0 * np.pi * np.asarray(f_rate_hz, dtype=float)
    h0 = sense_tf(params, params.w_d)
    ph = np.angle(h0)
    hp = sense_tf(params, params.w_d + wr)
    hm = sense_tf(params, params.w_d - wr)
    g = (hp * np.exp(-1j * ph) + np.conj(hm) * np.exp(1j * ph)) / (2.0 * np.abs(h0))
    if include_lpf:
        b, a = butter(2, 2.0 * np.pi * params.lpf_hz, analog=True)
        s = 1j * wr
        g = g * np.polyval(b, s) / np.polyval(a, s)
    return g


def rate_bandwidth_hz(params: MEMSGyroParams, include_lpf: bool = True) -> float:
    """-3 dB frequency of |G| found numerically."""
    f = np.logspace(-1, np.log10(params.drive_hz * 0.9), 2000)
    g = np.abs(rate_frequency_response(params, f, include_lpf))
    below = np.nonzero(g < 1.0 / np.sqrt(2.0))[0]
    return float(f[below[0]]) if below.size else float(f[-1])


def true_rate_dps(params: MEMSGyroParams, t: np.ndarray) -> np.ndarray:
    if params.profile == RateProfile.ZERO:
        return np.zeros_like(t)
    if params.profile == RateProfile.SINE:
        return params.rate_dps * np.sin(2.0 * np.pi * params.rate_hz * t)
    out = np.zeros_like(t)
    out[t >= params.step_time_s] = params.rate_dps
    return out


def simulate_gyro(params: MEMSGyroParams) -> dict[str, object]:
    n = int(params.duration_s * params.fs_hz)
    t = np.arange(n) / params.fs_hz
    wd = params.w_d
    amp = params.drive_amp_um * 1e-6
    x = amp * np.sin(wd * t)
    xdot = amp * wd * np.cos(wd * t)

    omega = true_rate_dps(params, t) * DEG2RAD
    kq = 2.0 * wd * params.quadrature_dps * DEG2RAD  # k_xy / m  giving Omega_q equivalent
    u_cor = -2.0 * omega * xdot
    u_quad = -kq * x

    wy = params.w_y
    sys = ([1.0], [1.0, wy / params.q_sense, wy * wy])
    _, y, _ = lsim(sys, U=u_cor + u_quad, T=t)
    y = np.asarray(y, dtype=float)
    if params.pickoff_noise_pm > 0:
        rng = np.random.default_rng(params.seed)
        y = y + rng.normal(0.0, params.pickoff_noise_pm * 1e-12, n)

    # Synchronous demodulation: reference = drive velocity, delayed by the
    # (calibrated) sense-mode phase, plus any phase error.
    h0 = sense_tf(params, wd)
    ref_phase = wd * t + np.angle(h0) + params.demod_phase_err_deg * DEG2RAD
    b, a = butter(2, params.lpf_hz / (0.5 * params.fs_hz))
    i_ch = lfilter(b, a, 2.0 * y * np.cos(ref_phase))
    q_ch = lfilter(b, a, 2.0 * y * np.sin(ref_phase))
    # Scale factor ("factory calibration"): I per rad/s. The sinc^2 term is the
    # gain of lsim's linear input interpolation at the carrier frequency.
    interp_gain = np.sinc(params.drive_hz / params.fs_hz) ** 2
    scale = -2.0 * amp * wd * np.abs(h0) * interp_gain
    rate_est = i_ch / scale * RAD2DEG
    quad_est = q_ch / scale * RAD2DEG  # quadrature channel in equivalent deg/s

    tail = t >= t[-1] - 0.25 * params.duration_s
    rate_true = omega * RAD2DEG
    return {
        "t_s": t,
        "x_um": x * 1e6,
        "y_nm": y * 1e9,
        "rate_true_dps": rate_true,
        "rate_est_dps": rate_est,
        "quad_channel_dps": quad_est,
        "bias_dps": float(np.mean(rate_est[tail] - rate_true[tail])),
        "noise_dps": float(np.std(rate_est[tail] - rate_true[tail])),
        "expected_bias_dps": float(-params.quadrature_dps * np.sin(params.demod_phase_err_deg * DEG2RAD)),
        "sens_nm_per_dps": sensitivity_nm_per_dps(params),
        "rate_bw_hz": rate_bandwidth_hz(params),
        "sense_phase_deg": float(np.angle(h0, deg=True)),
    }


def envelope(t: np.ndarray, y: np.ndarray, n_bins: int = 1500) -> dict[str, np.ndarray]:
    """Min/max per bin for plotting a fast carrier over a long window."""
    n = y.shape[0]
    n_bins = max(1, min(n_bins, n))
    edges = np.linspace(0, n, n_bins + 1).astype(int)
    lo = np.array([y[a:b].min() for a, b in zip(edges[:-1], edges[1:])])
    hi = np.array([y[a:b].max() for a, b in zip(edges[:-1], edges[1:])])
    tc = np.array([t[a] for a in edges[:-1]])
    return {"t": tc, "lo": lo, "hi": hi}


def process(params: MEMSGyroParams) -> dict[str, object]:
    return simulate_gyro(params)
