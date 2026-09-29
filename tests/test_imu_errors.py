"""Unit tests for the shared sensor error model and Allan deviation."""

from __future__ import annotations

import numpy as np

from teaching_sims.core.allan import allan_deviation, read_noise_terms
from teaching_sims.core.imu_errors import (
    GRADE_PRESETS,
    SensorErrorModel,
    TriadErrorModel,
    arw_dpsh_to_dpss,
    dph_to_dps,
    misalignment_matrix,
    ug_to_mps2,
)


def _slope(taus, adev, lo, hi):
    m = (taus >= lo) & (taus <= hi)
    return np.polyfit(np.log10(taus[m]), np.log10(adev[m]), 1)[0]


def test_unit_conversions():
    assert np.isclose(dph_to_dps(3600.0), 1.0)
    assert np.isclose(arw_dpsh_to_dpss(60.0), 1.0)
    assert np.isclose(ug_to_mps2(1e6), 9.80665)


def test_white_noise_sample_std_matches_density():
    fs = 200.0
    m = SensorErrorModel(white_density=0.02)
    y = m.apply(np.zeros(200_000), fs, np.random.default_rng(0))["meas"]
    assert np.isclose(np.std(y), 0.02 * np.sqrt(fs), rtol=0.02)


def test_scale_factor_and_bias():
    m = SensorErrorModel(bias=0.5, scale_factor_ppm=1e4)
    y = m.apply(np.full(10, 100.0), 100.0, np.random.default_rng(0))["meas"]
    assert np.allclose(y, 101.0 + 0.5)


def test_allan_white_noise_slope_and_N():
    fs, n = 100.0, 400_000
    y = SensorErrorModel(white_density=0.01).apply(np.zeros(n), fs, np.random.default_rng(1))["meas"]
    tau, ad = allan_deviation(y, fs)
    assert abs(_slope(tau, ad, 0.05, 50.0) + 0.5) < 0.05
    assert np.isclose(read_noise_terms(tau, ad)["N"], 0.01, rtol=0.1)


def test_allan_rate_random_walk_slope():
    fs, n = 10.0, 400_000
    y = SensorErrorModel(rrw=1e-3).apply(np.zeros(n), fs, np.random.default_rng(2))["meas"]
    tau, ad = allan_deviation(y, fs)
    assert abs(_slope(tau, ad, 10.0, 3000.0) - 0.5) < 0.1


def test_gauss_markov_stationary_std():
    m = SensorErrorModel(bias_instability=0.3, bi_corr_time_s=1.0)
    b = m.bias_process(300_000, 100.0, np.random.default_rng(3))
    assert np.isclose(np.std(b), 0.3, rtol=0.1)


def test_triad_misalignment_couples_axes():
    tri = TriadErrorModel(mis_mrad=(10.0, 0, 0, 0, 0, 0))
    y = tri.apply(np.array([[0.0, 1.0, 0.0]]), 100.0, np.random.default_rng(0))
    assert np.isclose(y[0, 0], 0.01)
    assert np.allclose(misalignment_matrix(), np.eye(3))


def test_grade_presets_are_ordered():
    arw = [GRADE_PRESETS[k].gyro_arw_dpsh for k in ("consumer", "industrial", "tactical")]
    bi = [GRADE_PRESETS[k].gyro_bi_dph for k in ("consumer", "industrial", "tactical")]
    assert arw == sorted(arw, reverse=True)
    assert bi == sorted(bi, reverse=True)
