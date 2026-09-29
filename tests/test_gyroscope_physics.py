"""Unit tests for gyroscope physics."""

from __future__ import annotations

import numpy as np

from teaching_sims.topics.gyroscope.physics import GyroParams, MotionProfile, process


def test_clean_integration_step():
    p = GyroParams(
        profile=MotionProfile.STEP_TURN,
        bias_dps=0.0,
        arw_deg_per_sqrt_s=0.0,
        rate_dps=30.0,
        duration_s=8.0,
    )
    out = process(p)
    # 3 s * 30 deg/s = 90 deg
    assert abs(out["angle_true_deg"][-1] - 90.0) < 0.5
    assert abs(out["final_err_deg"]) < 0.5


def test_bias_causes_ramp():
    p = GyroParams(
        profile=MotionProfile.CONSTANT,
        rate_dps=0.0,
        bias_dps=1.0,
        arw_deg_per_sqrt_s=0.0,
        duration_s=10.0,
    )
    out = process(p)
    assert abs(out["final_err_deg"] - 10.0) < 0.2


def test_bias_compensation():
    p = GyroParams(
        profile=MotionProfile.STEP_TURN,
        bias_dps=2.0,
        arw_deg_per_sqrt_s=0.0,
        compensate_bias=True,
    )
    out = process(p)
    assert abs(out["final_err_deg"]) < 0.5


def test_arw_ensemble_std_grows_like_sqrt_t():
    from teaching_sims.topics.gyroscope.physics import monte_carlo_errors

    p = GyroParams(profile=MotionProfile.CONSTANT, rate_dps=0.0, bias_dps=0.0, arw_deg_per_sqrt_s=0.2,
                   duration_s=16.0)
    errs = monte_carlo_errors(p, n_runs=200)
    fs = p.fs_hz
    s4, s16 = np.std(errs[:, int(4 * fs) - 1]), np.std(errs[:, int(16 * fs) - 1])
    assert np.isclose(s16 / s4, 2.0, rtol=0.2)
    assert np.isclose(s16, 0.2 * 4.0, rtol=0.2)


def test_compensation_misses_in_run_bias():
    base = dict(profile=MotionProfile.CONSTANT, rate_dps=0.0, bias_dps=1.0, arw_deg_per_sqrt_s=0.0,
                compensate_bias=True, duration_s=60.0, bi_corr_time_s=20.0)
    clean = process(GyroParams(**base))
    wander = process(GyroParams(**base, bias_instability_dps=0.2))
    assert abs(clean["final_err_deg"]) < 1e-9
    assert abs(wander["final_err_deg"]) > 0.5


def test_scale_factor_error_scales_with_turn():
    p = GyroParams(profile=MotionProfile.STEP_TURN, rate_dps=30.0, bias_dps=0.0, arw_deg_per_sqrt_s=0.0,
                   scale_ppm=10_000.0)
    assert np.isclose(process(p)["final_err_deg"], 0.9, atol=0.02)  # 1% of 90 deg


def test_static_allan_reads_back_datasheet_arw():
    from teaching_sims.topics.gyroscope.physics import datasheet_units, params_for_grade, static_allan

    p = params_for_grade(GyroParams(), "industrial")
    al = static_allan(p, record_s=3600.0)
    ds = datasheet_units(p)
    assert np.isclose(al["terms"]["N"] * 60.0, ds["arw_dpsh"], rtol=0.15)
