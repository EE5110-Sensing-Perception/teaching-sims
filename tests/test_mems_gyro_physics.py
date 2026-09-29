"""Unit tests for the Coriolis vibratory gyroscope model."""

from __future__ import annotations

import numpy as np

from teaching_sims.topics.mems_gyro.physics import (
    MEMSGyroParams,
    RateProfile,
    process,
    rate_bandwidth_hz,
    rate_frequency_response,
    sensitivity_nm_per_dps,
)


def test_zero_rate_zero_output():
    out = process(MEMSGyroParams(profile=RateProfile.ZERO))
    assert np.max(np.abs(out["y_nm"])) < 1e-9
    assert abs(out["bias_dps"]) < 1e-6


def test_step_rate_recovered():
    out = process(MEMSGyroParams(profile=RateProfile.STEP, rate_dps=100.0))
    assert abs(out["bias_dps"]) < 0.5


def test_quadrature_rejected_with_correct_phase():
    out = process(MEMSGyroParams(profile=RateProfile.ZERO, quadrature_dps=200.0))
    assert abs(out["bias_dps"]) < 0.5
    tail = out["t_s"] > 0.2
    assert abs(np.mean(out["quad_channel_dps"][tail]) - 200.0) < 5.0


def test_phase_error_leaks_quadrature_into_bias():
    p = MEMSGyroParams(profile=RateProfile.ZERO, quadrature_dps=200.0, demod_phase_err_deg=3.0)
    out = process(p)
    assert np.isclose(out["bias_dps"], out["expected_bias_dps"], rtol=0.05)
    assert out["expected_bias_dps"] < -10.0


def test_rate_response_unity_at_dc():
    g = rate_frequency_response(MEMSGyroParams(), np.array([1e-3]), include_lpf=False)
    assert np.isclose(abs(g[0]), 1.0, atol=1e-3)


def test_mode_matching_trades_bandwidth_for_sensitivity():
    split = MEMSGyroParams(sense_split_hz=300.0, q_sense=200.0)
    matched = MEMSGyroParams(sense_split_hz=0.0, q_sense=200.0)
    assert sensitivity_nm_per_dps(matched) > 10 * sensitivity_nm_per_dps(split)
    assert rate_bandwidth_hz(matched, include_lpf=False) < rate_bandwidth_hz(split, include_lpf=False)
