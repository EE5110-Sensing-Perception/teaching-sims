"""Unit tests for complementary filter."""

from __future__ import annotations

from teaching_sims.topics.complementary.physics import ComplementaryParams, process


def test_comp_beats_gyro_with_bias():
    p = ComplementaryParams(
        alpha=0.98,
        gyro_bias_dps=1.5,
        gyro_noise_dps=0.05,
        accel_noise_mps2=0.05,
        surge_mps2=0.0,
        duration_s=12.0,
    )
    out = process(p)
    assert out["rms_comp_deg"] < out["rms_gyro_deg"]


def test_surge_hurts_accel():
    quiet = process(
        ComplementaryParams(alpha=0.0, surge_mps2=0.0, gyro_bias_dps=0.0, amp_deg=5.0, duration_s=6.0)
    )
    surge = process(
        ComplementaryParams(alpha=0.0, surge_mps2=3.0, gyro_bias_dps=0.0, amp_deg=5.0, duration_s=6.0)
    )
    assert surge["rms_accel_deg"] > quiet["rms_accel_deg"]


def test_forward_surge_reads_nose_up():
    import numpy as np

    out = process(ComplementaryParams(alpha=0.0, surge_mps2=2.0, amp_deg=0.0, gyro_bias_dps=0.0,
                                      accel_noise_mps2=0.0, duration_s=2.0))
    assert np.mean(out["accel_tilt_deg"]) > 10.0


def test_tau_and_crossover():
    import numpy as np

    from teaching_sims.topics.complementary.physics import alpha_for_tau, crossover_hz, filter_tau_s, transfer_functions

    dt = 0.01
    assert np.isclose(filter_tau_s(0.98, dt), 0.49)
    assert np.isclose(alpha_for_tau(0.49, dt), 0.98)
    fc = crossover_hz(0.98, dt)
    tf = transfer_functions(0.98, dt, np.array([1e-4, fc, 40.0]))
    assert np.isclose(tf["lowpass"][0], 1.0, atol=1e-3) and tf["highpass"][0] < 1e-3
    assert np.isclose(tf["lowpass"][1], tf["highpass"][1], rtol=0.05)
    assert tf["lowpass"][2] < 0.05


def test_kalman_estimates_bias_and_beats_cf():
    p = ComplementaryParams(gyro_bias_dps=1.0, alpha=0.98, duration_s=40.0, kf_r_deg=1.5, kf_q_bias_dps_rts=0.01)
    out = process(p)
    assert abs(out["kf_bias_final_dps"] - 1.0) < 0.15
    assert out["rms_kf_deg"] < out["rms_comp_deg"]


def test_gating_reduces_surge_error():
    base = dict(motion=__import__("teaching_sims.topics.complementary.physics", fromlist=["PitchMotion"]).PitchMotion.SINE,
                amp_deg=10.0, alpha=0.98, surge_mps2=4.0, surge_start_s=4.0, surge_dur_s=4.0, gyro_bias_dps=0.2,
                duration_s=12.0, gate_threshold_mps2=0.2)
    raw = process(ComplementaryParams(**base))
    gated = process(ComplementaryParams(**base, gate_accel=True))
    assert gated["rms_comp_deg"] < 0.6 * raw["rms_comp_deg"]
    assert gated["gated_fraction"] > 0.2


def test_mahony_roll_pitch_converge_yaw_needs_mag():
    import numpy as np

    from teaching_sims.topics.complementary.mahony import MahonyParams, simulate_mahony

    no_mag = simulate_mahony(MahonyParams(duration_s=60.0, use_mag=False))
    with_mag = simulate_mahony(MahonyParams(duration_s=60.0, use_mag=True))
    # roll/pitch fine either way (columns: yaw, pitch, roll)
    assert no_mag["rms_tail_deg"][1] < 1.5 and no_mag["rms_tail_deg"][2] < 1.5
    # yaw drifts without the magnetometer, holds with it
    assert abs(no_mag["final_err_deg"][0]) > 10.0
    assert with_mag["rms_tail_deg"][0] < 2.0
    # z-bias estimate only converges with the mag
    assert abs(with_mag["bias_est_dps"][-1, 2] - 0.6) < 0.15
