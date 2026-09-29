"""Shared inertial-sensor error model (deterministic + stochastic).

All signals are in the sensor's working units: deg/s for gyros, m/s^2 for
accelerometers. Datasheet quantities are converted with the helpers below so
demos can be driven from "grade" presets in the units students see on real
datasheets.

Stochastic terms and their Allan-deviation signatures:

* white noise density ``N``  (units*sqrt(s))   -> sigma_A(tau) = N / sqrt(tau)    slope -1/2
* bias instability ``B``     (units)           -> flat floor ~ 0.664 B            slope  0
* rate random walk ``K``     (units/sqrt(s))   -> sigma_A(tau) = K sqrt(tau / 3)  slope +1/2

Bias instability (flicker noise) is approximated by a sum of nine
first-order Gauss-Markov processes with correlation times spaced by 3x around
``bi_corr_time_s``. Each has sigma = 0.60 B, which puts the Allan floor at
~0.664 B, flat over roughly three decades of tau.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import lfilter

from teaching_sims.core.imu import G0

# --- datasheet unit conversions -------------------------------------------------

SEC_PER_HOUR = 3600.0


def dph_to_dps(x: float) -> float:
    """deg/h -> deg/s."""
    return x / SEC_PER_HOUR


def arw_dpsh_to_dpss(x: float) -> float:
    """Angle random walk deg/sqrt(h) -> deg/sqrt(s) (= deg/s/sqrt(Hz))."""
    return x / 60.0


def rrw_dphsh_to_dpss(x: float) -> float:
    """Rate random walk deg/h/sqrt(h) -> deg/s/sqrt(s)."""
    return x / (SEC_PER_HOUR * 60.0)


def ug_to_mps2(x: float) -> float:
    """micro-g -> m/s^2."""
    return x * 1e-6 * G0


def mg_to_mps2(x: float) -> float:
    """milli-g -> m/s^2."""
    return x * 1e-3 * G0


def ug_rthz_to_mps2_rths(x: float) -> float:
    """Accel noise density ug/sqrt(Hz) -> m/s^2*sqrt(s) (= m/s/sqrt(s))."""
    return ug_to_mps2(x)


def vrw_to_ug_rthz(vrw_mps_rth: float) -> float:
    """Velocity random walk m/s/sqrt(h) -> ug/sqrt(Hz)."""
    return vrw_mps_rth / 60.0 / (1e-6 * G0)


# --- single-axis model ------------------------------------------------------------

# Flicker (bias-instability) approximation: see module docstring.
_FLICKER_N = 9
_FLICKER_RATIO = 3.0
_FLICKER_SIGMA = 0.60


@dataclass(frozen=True)
class SensorErrorModel:
    """Single-axis sensor errors in working units (deg/s or m/s^2)."""

    bias: float = 0.0  # constant turn-on bias
    scale_factor_ppm: float = 0.0  # (meas - true)/true, parts per million
    white_density: float = 0.0  # N: units*sqrt(s)  (ARW / VRW)
    bias_instability: float = 0.0  # B: datasheet bias instability (Allan floor / 0.664), units
    bi_corr_time_s: float = 300.0  # centre of the flicker band (s)
    rrw: float = 0.0  # K: units/sqrt(s)

    def __post_init__(self) -> None:
        if self.white_density < 0 or self.bias_instability < 0 or self.rrw < 0:
            raise ValueError("noise densities must be >= 0")
        if self.bi_corr_time_s <= 0:
            raise ValueError("bi_corr_time_s must be positive")

    def bias_process(self, n: int, fs: float, rng: np.random.Generator) -> np.ndarray:
        """Time-varying bias: constant + Gauss-Markov + random walk."""
        dt = 1.0 / fs
        b = np.full(n, self.bias, dtype=float)
        if self.bias_instability > 0:
            for k in range(_FLICKER_N):
                tc = self.bi_corr_time_s * _FLICKER_RATIO ** (k - (_FLICKER_N - 1) / 2)
                phi = np.exp(-dt / tc)
                q = np.sqrt(1.0 - phi * phi)
                w = rng.normal(0.0, 1.0, n)
                gm = np.empty(n)
                gm[0] = w[0]  # stationary start
                if n > 1:
                    gm[1:], _ = lfilter([q], [1.0, -phi], w[1:], zi=[phi * w[0]])
                b += _FLICKER_SIGMA * self.bias_instability * gm
        if self.rrw > 0:
            b += np.cumsum(rng.normal(0.0, self.rrw * np.sqrt(dt), n))
        return b

    def apply(self, true: np.ndarray, fs: float, rng: np.random.Generator) -> dict[str, np.ndarray]:
        """Corrupt a true signal; returns measured signal and its bias history."""
        true = np.asarray(true, dtype=float)
        n = true.shape[0]
        bias = self.bias_process(n, fs, rng)
        white = rng.normal(0.0, self.white_density * np.sqrt(fs), n) if self.white_density > 0 else np.zeros(n)
        meas = (1.0 + self.scale_factor_ppm * 1e-6) * true + bias + white
        return {"meas": meas, "bias": bias}


# --- triad model (scale + misalignment) ------------------------------------------


def misalignment_matrix(mis_mrad: tuple[float, float, float, float, float, float] = (0, 0, 0, 0, 0, 0)) -> np.ndarray:
    """Small-angle non-orthogonality matrix M (I + off-diagonal terms).

    ``mis_mrad`` = (m_xy, m_xz, m_yx, m_yz, m_zx, m_zy) in milliradians: the
    sensitivity of sensor axis i to true axis j.
    """
    m = np.eye(3)
    idx = ((0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1))
    for (i, j), v in zip(idx, mis_mrad):
        m[i, j] = v * 1e-3
    return m


@dataclass(frozen=True)
class TriadErrorModel:
    """Three-axis sensor: y = (I + S) M x + b + noise."""

    axes: tuple[SensorErrorModel, SensorErrorModel, SensorErrorModel] = field(
        default_factory=lambda: (SensorErrorModel(), SensorErrorModel(), SensorErrorModel())
    )
    mis_mrad: tuple[float, float, float, float, float, float] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def gain_matrix(self) -> np.ndarray:
        s = np.diag([1.0 + a.scale_factor_ppm * 1e-6 for a in self.axes])
        return s @ misalignment_matrix(self.mis_mrad)

    def bias_vector(self) -> np.ndarray:
        return np.array([a.bias for a in self.axes], dtype=float)

    def apply(self, true_xyz: np.ndarray, fs: float, rng: np.random.Generator) -> np.ndarray:
        """``true_xyz`` shape (n, 3) -> measured (n, 3)."""
        x = np.atleast_2d(np.asarray(true_xyz, dtype=float))
        y = x @ self.gain_matrix().T
        out = np.empty_like(y)
        for k, a in enumerate(self.axes):
            # scale already in gain matrix; add bias + noise only
            noise_only = SensorErrorModel(
                bias=a.bias,
                white_density=a.white_density,
                bias_instability=a.bias_instability,
                bi_corr_time_s=a.bi_corr_time_s,
                rrw=a.rrw,
            )
            out[:, k] = noise_only.apply(y[:, k], fs, rng)["meas"]
        return out


# --- grade presets (representative, order-of-magnitude values) --------------------


@dataclass(frozen=True)
class GradeSpec:
    """Datasheet-style numbers for one IMU grade."""

    name: str
    gyro_bias_dph: float  # turn-on bias, deg/h
    gyro_arw_dpsh: float  # deg/sqrt(h)
    gyro_bi_dph: float  # bias instability, deg/h
    gyro_rrw_dphsh: float  # deg/h/sqrt(h)
    accel_bias_mg: float  # turn-on bias, mg
    accel_noise_ug_rthz: float  # ug/sqrt(Hz)
    accel_bi_ug: float  # bias instability, ug
    example: str = ""

    def gyro_model(self) -> SensorErrorModel:
        """Gyro error model in deg/s."""
        return SensorErrorModel(
            bias=dph_to_dps(self.gyro_bias_dph),
            white_density=arw_dpsh_to_dpss(self.gyro_arw_dpsh),
            bias_instability=dph_to_dps(self.gyro_bi_dph),
            rrw=rrw_dphsh_to_dpss(self.gyro_rrw_dphsh),
        )

    def accel_model(self) -> SensorErrorModel:
        """Accelerometer error model in m/s^2."""
        return SensorErrorModel(
            bias=mg_to_mps2(self.accel_bias_mg),
            white_density=ug_rthz_to_mps2_rths(self.accel_noise_ug_rthz),
            bias_instability=ug_to_mps2(self.accel_bi_ug),
        )


GRADE_PRESETS: dict[str, GradeSpec] = {
    "consumer": GradeSpec(
        name="Consumer MEMS",
        gyro_bias_dph=3600.0,
        gyro_arw_dpsh=0.3,
        gyro_bi_dph=20.0,
        gyro_rrw_dphsh=5.0,
        accel_bias_mg=40.0,
        accel_noise_ug_rthz=300.0,
        accel_bi_ug=100.0,
        example="phone / hobby IMU",
    ),
    "industrial": GradeSpec(
        name="Industrial MEMS",
        gyro_bias_dph=180.0,
        gyro_arw_dpsh=0.15,
        gyro_bi_dph=3.0,
        gyro_rrw_dphsh=1.0,
        accel_bias_mg=3.0,
        accel_noise_ug_rthz=60.0,
        accel_bi_ug=20.0,
        example="robotics / UAV module",
    ),
    "tactical": GradeSpec(
        name="Tactical",
        gyro_bias_dph=1.0,
        gyro_arw_dpsh=0.05,
        gyro_bi_dph=0.5,
        gyro_rrw_dphsh=0.1,
        accel_bias_mg=1.0,
        accel_noise_ug_rthz=30.0,
        accel_bi_ug=10.0,
        example="FOG / high-end MEMS",
    ),
}
