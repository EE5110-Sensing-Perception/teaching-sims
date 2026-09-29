"""Unit tests for strapdown INS."""

from __future__ import annotations

import numpy as np

from teaching_sims.topics.ins.physics import Aiding, INSParams, PathProfile, ZuptDetector, process


def test_perfect_circle_stays_close():
    out = process(
        INSParams(
            profile=PathProfile.CIRCLE,
            perfect_attitude=True,
            gyro_bias_dps=0.0,
            accel_bias_x_mps2=0.0,
            accel_bias_y_mps2=0.0,
            accel_noise_mps2=0.0,
            gyro_noise_dps=0.0,
            duration_s=40.0,
            fs_hz=50.0,
        )
    )
    assert out["final_pos_err_m"] < 3.0


def test_accel_bias_grows_error():
    clean = process(
        INSParams(
            profile=PathProfile.STRAIGHT,
            perfect_attitude=True,
            accel_bias_x_mps2=0.0,
            accel_noise_mps2=0.0,
            gyro_noise_dps=0.0,
            duration_s=20.0,
        )
    )
    biased = process(
        INSParams(
            profile=PathProfile.STRAIGHT,
            perfect_attitude=True,
            accel_bias_x_mps2=0.1,
            accel_noise_mps2=0.0,
            gyro_noise_dps=0.0,
            duration_s=20.0,
        )
    )
    assert biased["final_pos_err_m"] > clean["final_pos_err_m"] + 5.0


def test_gyro_bias_hurts_circle():
    out = process(
        INSParams(
            profile=PathProfile.CIRCLE,
            perfect_attitude=False,
            gyro_bias_dps=0.5,
            accel_bias_x_mps2=0.0,
            accel_bias_y_mps2=0.0,
            accel_noise_mps2=0.0,
            gyro_noise_dps=0.0,
            duration_s=40.0,
        )
    )
    assert out["final_pos_err_m"] > 5.0


def _quiet(**kw):
    base = dict(perfect_attitude=True, gyro_bias_dps=0.0, accel_bias_x_mps2=0.0, accel_bias_y_mps2=0.0,
                accel_noise_mps2=0.0, gyro_noise_dps=0.0)
    base.update(kw)
    return INSParams(**base)


def test_accel_bias_matches_half_b_t2():
    out = process(_quiet(profile=PathProfile.STRAIGHT, accel_bias_x_mps2=0.1, duration_s=20.0))
    assert np.isclose(out["final_pos_err_m"], 0.5 * 0.1 * 20.0**2, rtol=0.03)


def test_tilt_leaks_gravity_like_bias():
    tilt = process(_quiet(profile=PathProfile.STRAIGHT, tilt0_deg=0.1, duration_s=30.0))
    ref = tilt["references"]["initial tilt"][-1]
    assert np.isclose(tilt["final_pos_err_m"], ref, rtol=0.05)


def test_pitch_gyro_bias_grows_cubically():
    out = process(_quiet(profile=PathProfile.STRAIGHT, gyro_pitch_bias_dps=0.01, duration_s=60.0))
    t, e = out["t_s"], out["pos_err_m"]
    i30, i60 = np.searchsorted(t, 30.0), len(t) - 1
    assert np.isclose(e[i60] / e[i30], 8.0, rtol=0.1)
    assert np.isclose(e[i60], out["references"]["pitch gyro bias"][-1], rtol=0.05)


def test_zupt_bounds_stop_and_go_drift():
    base = dict(profile=PathProfile.STOP_AND_GO, accel_bias_x_mps2=0.06, duration_s=45.0)
    free = process(_quiet(**base))
    zupt = process(_quiet(**base, aiding=Aiding.ZUPT))
    tail = free["t_s"] > 30.0
    # after the stop, free INS keeps drifting; ZUPT holds position
    assert free["pos_err_m"][-1] - free["pos_err_m"][tail][0] > 5.0
    assert zupt["pos_err_m"][-1] - zupt["pos_err_m"][tail][0] < 0.5


def test_imu_zupt_detector_fires_during_cruise():
    out = process(_quiet(profile=PathProfile.STRAIGHT, accel_noise_mps2=0.02, gyro_noise_dps=0.05,
                         aiding=Aiding.ZUPT, zupt_detector=ZuptDetector.IMU, duration_s=20.0))
    assert out["zupt_mask"].mean() > 0.5  # constant-velocity cruise looks stationary
    assert out["final_pos_err_m"] > 50.0


def test_position_fixes_bound_error():
    base = dict(profile=PathProfile.CIRCLE, perfect_attitude=False, gyro_bias_dps=0.4, accel_bias_x_mps2=0.05,
                duration_s=60.0)
    free = process(INSParams(**base))
    aided = process(INSParams(**base, aiding=Aiding.POSITION, fix_interval_s=5.0, fix_sigma_m=2.0))
    assert free["final_pos_err_m"] > 20.0
    assert aided["max_pos_err_m"] < 0.4 * free["max_pos_err_m"]
