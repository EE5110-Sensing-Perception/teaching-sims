"""Unit tests for accelerometer physics."""

from __future__ import annotations

import numpy as np

from teaching_sims.core.imu import G0
from teaching_sims.topics.accelerometer.physics import AccelParams, process, tilt_from_accel, true_specific_force_body


def test_level_specific_force():
    f = true_specific_force_body(AccelParams(roll_deg=0.0, pitch_deg=0.0))
    assert abs(f[0]) < 1e-9
    assert abs(f[1]) < 1e-9
    assert abs(f[2] + G0) < 1e-9


def test_tilt_roundtrip_static():
    p = AccelParams(roll_deg=18.0, pitch_deg=-12.0, noise_mps2=0.0, vibe_amp_mps2=0.0)
    f = true_specific_force_body(p)
    roll, pitch = tilt_from_accel(f[0], f[1], f[2])
    assert abs(roll - 18.0) < 1e-6
    assert abs(pitch - (-12.0)) < 1e-6


def test_bias_looks_like_pitch():
    p = AccelParams(roll_deg=0.0, pitch_deg=0.0, bias_x_mps2=0.5, noise_mps2=0.0)
    out = process(p)
    assert abs(out["pitch_mean_deg"]) > 2.0


def test_surge_contaminates_pitch():
    p = AccelParams(roll_deg=0.0, pitch_deg=0.0, ax_mps2=2.0, noise_mps2=0.0)
    out = process(p)
    assert abs(out["pitch_mean_deg"]) > 5.0


def test_yaw_invisible_to_accel():
    """Gravity specific force depends on roll/pitch only, not yaw."""
    base = AccelParams(yaw_deg=0.0, roll_deg=15.0, pitch_deg=-8.0, noise_mps2=0.0)
    turned = AccelParams(yaw_deg=60.0, roll_deg=15.0, pitch_deg=-8.0, noise_mps2=0.0)
    f0 = true_specific_force_body(base)
    f1 = true_specific_force_body(turned)
    assert np.allclose(f0, f1)
    r0, p0 = tilt_from_accel(f0[0], f0[1], f0[2])
    r1, p1 = tilt_from_accel(f1[0], f1[1], f1[2])
    assert abs(r0 - 15.0) < 1e-6
    assert abs(p0 + 8.0) < 1e-6
    assert abs(r0 - r1) < 1e-6
    assert abs(p0 - p1) < 1e-6


def test_vibration_mean_recovers():
    p = AccelParams(
        roll_deg=10.0,
        pitch_deg=5.0,
        vibe_amp_mps2=3.0,
        vibe_hz=40.0,
        noise_mps2=0.0,
        duration_s=2.0,
        fs_hz=200.0,
    )
    out = process(p)
    assert abs(out["roll_mean_deg"] - 10.0) < 0.5
    assert abs(out["pitch_mean_deg"] - 5.0) < 0.5


def test_forward_acceleration_reads_nose_up():
    """Somatogravic illusion: surge forward looks like pitch up."""
    out = process(AccelParams(roll_deg=0.0, pitch_deg=0.0, ax_mps2=1.0, noise_mps2=0.0))
    assert out["pitch_mean_deg"] > 5.0


def test_scale_and_misalignment_model():
    p = AccelParams(scale_x_pct=2.0, mis_xz_mrad=10.0)
    g = p.gain_matrix()
    assert np.isclose(g[0, 0], 1.02)
    assert np.isclose(g[0, 2], 1.02 * 0.01)


def test_six_position_recovers_bias_scale_misalignment():
    from teaching_sims.topics.accelerometer.physics import six_position_calibration

    p = AccelParams(
        bias_x_mps2=0.2, bias_y_mps2=-0.1, bias_z_mps2=0.3,
        scale_x_pct=1.5, scale_y_pct=-1.0, scale_z_pct=0.5,
        mis_xy_mrad=5.0, mis_xz_mrad=-3.0, mis_yz_mrad=4.0,
        noise_mps2=0.02,
    )
    cal = six_position_calibration(p, samples_per_pose=500)
    assert np.allclose(cal["bias"], p.bias, atol=5e-3)
    assert np.allclose(cal["gain"], p.gain_matrix(), atol=1e-3)


def test_calibration_removes_tilt_error():
    from teaching_sims.topics.accelerometer.physics import six_position_calibration

    p = AccelParams(roll_deg=20.0, pitch_deg=-10.0, bias_x_mps2=0.3, scale_z_pct=2.0, mis_xz_mrad=8.0,
                    noise_mps2=0.01)
    raw = process(p)
    cal = six_position_calibration(p, samples_per_pose=500)
    fixed = process(p, cal={"gain": cal["gain"], "bias": cal["bias"]})
    assert abs(raw["pitch_err_deg"]) > 1.0
    assert abs(fixed["pitch_err_deg"]) < 0.1
    assert abs(fixed["roll_err_deg"]) < 0.1


def test_lever_arm_centripetal_and_compensation():
    base = dict(roll_deg=0.0, pitch_deg=0.0, noise_mps2=0.0, lever_x_m=0.5, yaw_rate_dps=120.0)
    out = process(AccelParams(**base))
    w = 120.0 * np.pi / 180.0
    assert np.isclose(out["lever_accel"][0], -w * w * 0.5)
    assert out["pitch_mean_deg"] < -5.0  # centripetal toward the centre looks nose-down
    comp = process(AccelParams(**base, compensate_lever=True))
    assert abs(comp["pitch_mean_deg"]) < 1e-6


def test_moving_average_tilt_reduces_vibration_jitter():
    p = AccelParams(roll_deg=8.0, pitch_deg=5.0, vibe_amp_mps2=2.0, vibe_hz=30.0, noise_mps2=0.05, avg_window_s=1.0)
    out = process(p)
    tail = out["t_s"] > 1.5
    assert np.std(out["pitch_avg_deg"][tail]) < 0.2 * np.std(out["pitch_est_deg"][tail])
