"""Unit tests for magnetometer / heading."""

from __future__ import annotations

from teaching_sims.topics.magnetometer.physics import MagParams, process


def test_level_heading_ok():
    out = process(MagParams(pitch_deg=0.0, roll_deg=0.0, noise_ut=0.0, tilt_compensate=True))
    assert out["rms_err_deg"] < 1.0


def test_pitch_without_tc_errs():
    raw = process(
        MagParams(pitch_deg=30.0, roll_deg=0.0, noise_ut=0.0, tilt_compensate=False, soft_xx=1.0, soft_yy=1.0)
    )
    tc = process(
        MagParams(pitch_deg=30.0, roll_deg=0.0, noise_ut=0.0, tilt_compensate=True, soft_xx=1.0, soft_yy=1.0)
    )
    assert tc["rms_err_deg"] < raw["rms_err_deg"]


def test_hard_iron_raises_error():
    clean = process(MagParams(noise_ut=0.0, hard_x_ut=0.0, hard_y_ut=0.0))
    dirty = process(MagParams(noise_ut=0.0, hard_x_ut=10.0, hard_y_ut=-8.0))
    assert dirty["rms_err_deg"] > clean["rms_err_deg"]


def test_default_field_matches_legacy_vector():
    import numpy as np

    from teaching_sims.topics.magnetometer.physics import earth_field_ned

    assert np.allclose(earth_field_ned(MagParams()), [20.0, 0.0, 45.0], atol=0.05)


def test_ellipse_calibration_recovers_hard_iron_and_fixes_heading():
    import numpy as np

    from teaching_sims.topics.magnetometer.physics import compass_swing

    p = MagParams(noise_ut=0.1, hard_x_ut=8.0, hard_y_ut=-5.0, soft_xx=1.2, soft_yy=0.85, soft_xy=0.1)
    cal = compass_swing(p)
    assert np.allclose(cal["centre"], [8.0, -5.0], atol=0.3)
    raw = process(p)
    fixed = process(p, cal=cal)
    assert raw["rms_err_deg"] > 5.0
    assert fixed["rms_err_deg"] < 1.0


def test_declination_offsets_heading():
    raw = process(MagParams(noise_ut=0.0, declination_deg=12.0, apply_declination=False))
    ok = process(MagParams(noise_ut=0.0, declination_deg=12.0, apply_declination=True))
    assert abs(raw["rms_err_deg"] - 12.0) < 0.5
    assert ok["rms_err_deg"] < 0.5


def test_world_disturbance_detected_and_not_calibratable():
    from teaching_sims.topics.magnetometer.physics import compass_swing

    p = MagParams(noise_ut=0.0, dist_e_ut=8.0, dist_d_ut=-6.0)
    out = process(p, cal=compass_swing(p))
    assert out["rms_err_deg"] > 5.0
    assert not out["field_check"]["ok"]
    assert process(MagParams(noise_ut=0.0))["field_check"]["ok"]
