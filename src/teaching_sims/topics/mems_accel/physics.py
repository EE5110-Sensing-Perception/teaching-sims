"""MEMS comb-drive accelerometer physics (spring-mass + capacitive readout)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.signal import lti, lsim


class Excitation(str, Enum):
    REST = "rest"
    CONSTANT = "constant"
    IMPULSE = "impulse"
    STEP = "step"
    SINE = "sine"


@dataclass(frozen=True)
class MEMSAccelParams:
    """1-axis MEMS accelerometer (proof mass + suspension + comb fingers)."""

    # Mechanical (SI)
    mass_kg: float = 1.0e-8  # ~10 ug
    kn_n_per_m: float = 2.0  # suspension stiffness
    zeta: float = 0.35  # damping ratio (underdamped < 1 rings after impulse)
    # Comb capacitor geometry (teaching scale)
    gap0_um: float = 2.0
    area_um2: float = 500.0
    n_fingers: int = 8
    # Excitation
    excitation: Excitation = Excitation.IMPULSE
    a_const_mps2: float = 5.0
    impulse_amp_mps2: float = 40.0
    impulse_width_s: float = 0.002
    impulse_time_s: float = 0.05
    sine_amp_mps2: float = 8.0
    sine_hz: float = 40.0
    # Error sources
    output_bias_mps2: float = 0.0  # electronic / scale-factor offset on reported accel
    mech_offset_um: float = 0.0  # rest-position offset (looks like bias)
    # Simulation
    duration_s: float = 0.25
    fs_hz: float = 20_000.0
    seed: int = 0

    def __post_init__(self) -> None:
        if self.mass_kg <= 0 or self.kn_n_per_m <= 0:
            raise ValueError("mass and stiffness must be positive")
        if self.zeta < 0:
            raise ValueError("zeta must be >= 0")
        if self.gap0_um <= 0:
            raise ValueError("gap0_um must be positive")
        if self.fs_hz <= 0 or self.duration_s <= 0:
            raise ValueError("fs_hz and duration_s must be positive")

    @property
    def omega0_rad_s(self) -> float:
        return float(np.sqrt(self.kn_n_per_m / self.mass_kg))

    @property
    def f0_hz(self) -> float:
        return self.omega0_rad_s / (2.0 * np.pi)

    @property
    def damping_nsm(self) -> float:
        return 2.0 * self.zeta * np.sqrt(self.kn_n_per_m * self.mass_kg)

    @property
    def scale_mps2_per_m(self) -> float:
        """Steady-state: a_ss = -omega0^2 * x  =>  reported a from displacement."""
        return self.omega0_rad_s**2


def external_accel(params: MEMSAccelParams, t: np.ndarray) -> np.ndarray:
    """Frame acceleration a_ext(t) along the sense axis (m/s^2)."""
    a = np.zeros_like(t, dtype=float)
    if params.excitation == Excitation.REST:
        return a
    if params.excitation == Excitation.CONSTANT:
        a[:] = params.a_const_mps2
        return a
    if params.excitation == Excitation.STEP:
        a[t >= params.impulse_time_s] = params.a_const_mps2
        return a
    if params.excitation == Excitation.SINE:
        a[:] = params.sine_amp_mps2 * np.sin(2.0 * np.pi * params.sine_hz * t)
        return a
    # Impulse: short rectangular pulse
    t0 = params.impulse_time_s
    tw = params.impulse_width_s
    a[(t >= t0) & (t < t0 + tw)] = params.impulse_amp_mps2
    return a


def _eps0() -> float:
    return 8.854187817e-12


def capacitance_f(params: MEMSAccelParams, x_m: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parallel-plate comb pair: C1 ~ 1/(g0-x), C2 ~ 1/(g0+x); return C1, C2, dC."""
    g0 = params.gap0_um * 1e-6
    area = params.area_um2 * 1e-12
    n = float(params.n_fingers)
    # Soft clip so gaps stay positive for large excursions
    gap1 = np.clip(g0 - x_m, 0.15 * g0, None)
    gap2 = np.clip(g0 + x_m, 0.15 * g0, None)
    c1 = n * _eps0() * area / gap1
    c2 = n * _eps0() * area / gap2
    return c1, c2, c1 - c2


def simulate_mems(params: MEMSAccelParams) -> dict[str, object]:
    """Integrate m x'' + c x' + k x = -m a_ext; map x -> capacitance and accel estimate."""
    n = int(params.duration_s * params.fs_hz)
    t = np.arange(n, dtype=float) / params.fs_hz
    a_ext = external_accel(params, t)

    # LTI: X(s)/A(s) = -1 / (s^2 + 2 zeta w0 s + w0^2)
    w0 = params.omega0_rad_s
    num = [-1.0]
    den = [1.0, 2.0 * params.zeta * w0, w0 * w0]
    sys = lti(num, den)
    # Force zero IC; mech offset applied after
    _, x_dyn, _ = lsim(sys, U=a_ext, T=t)
    x_m = np.asarray(x_dyn, dtype=float) + params.mech_offset_um * 1e-6

    c1, c2, dc = capacitance_f(params, x_m)
    # Ideal open-loop estimate from displacement (quasi-static scale)
    a_from_x = -params.scale_mps2_per_m * x_m
    a_meas = a_from_x + params.output_bias_mps2

    # Steady-state expectation for constant excitation
    a_ss = 0.0
    if params.excitation in (Excitation.CONSTANT, Excitation.STEP):
        a_ss = params.a_const_mps2

    return {
        "t_s": t,
        "a_ext_mps2": a_ext,
        "x_um": x_m * 1e6,
        "c1_fF": c1 * 1e15,
        "c2_fF": c2 * 1e15,
        "dc_fF": dc * 1e15,
        "a_meas_mps2": a_meas,
        "a_from_x_mps2": a_from_x,
        "f0_hz": params.f0_hz,
        "zeta": params.zeta,
        "gap0_um": params.gap0_um,
        "x_final_um": float(x_m[-1] * 1e6),
        "a_meas_final": float(a_meas[-1]),
        "a_ss_expected": a_ss,
        "ringing": bool(params.zeta < 1.0 and params.excitation == Excitation.IMPULSE),
    }


K_BOLTZMANN = 1.380649e-23


def frequency_response(params: MEMSAccelParams, f_hz: np.ndarray) -> dict[str, np.ndarray]:
    """Reported-accel / true-accel versus frequency (1 at DC), and phase in deg.

    The mechanical transfer X/A = -1/(s^2 + 2 zeta w0 s + w0^2); the open-loop
    readout scales x by w0^2, so the normalised response is w0^2 / (w0^2 - w^2 + 2j zeta w0 w).
    """
    w = 2.0 * np.pi * np.asarray(f_hz, dtype=float)
    w0 = params.omega0_rad_s
    h = w0 * w0 / (w0 * w0 - w * w + 2j * params.zeta * w0 * w)
    return {"f_hz": np.asarray(f_hz, dtype=float), "mag": np.abs(h), "phase_deg": np.angle(h, deg=True)}


def bandwidth_hz(params: MEMSAccelParams) -> float:
    """-3 dB frequency of the normalised response (closed form)."""
    z2 = params.zeta**2
    x = 1.0 - 2.0 * z2 + np.sqrt((1.0 - 2.0 * z2) ** 2 + 1.0)  # (w/w0)^2 where |H| = 1/sqrt(2)
    return float(params.f0_hz * np.sqrt(x))


def sensitivity_nm_per_g(params: MEMSAccelParams) -> float:
    """Static proof-mass displacement per 1 g (nm)."""
    return float(9.80665 / params.omega0_rad_s**2 * 1e9)


def brownian_noise_ug_rthz(params: MEMSAccelParams, temp_k: float = 300.0) -> float:
    """Thermo-mechanical (Brownian) noise floor sqrt(4 kB T c)/m in ug/sqrt(Hz)."""
    a_n = np.sqrt(4.0 * K_BOLTZMANN * temp_k * params.damping_nsm) / params.mass_kg
    return float(a_n / 9.80665e-6)


def process(params: MEMSAccelParams) -> dict[str, object]:
    out = simulate_mems(params)
    out["bandwidth_hz"] = bandwidth_hz(params)
    out["sens_nm_per_g"] = sensitivity_nm_per_g(params)
    out["brownian_ug_rthz"] = brownian_noise_ug_rthz(params)
    return out
