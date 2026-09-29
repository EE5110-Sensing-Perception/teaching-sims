"""Unit tests for frames / rotations / kinematics helpers."""

from __future__ import annotations

import numpy as np

from teaching_sims.core.imu import DEG2RAD
from teaching_sims.topics.attitude.physics import (
    T_NED_ENU,
    AttitudeParams,
    Integrator,
    Sequence,
    dcm_ned_frd_to_enu_flu,
    dcm_to_euler_zyx,
    dcm_to_quat,
    euler_ned_to_ros,
    euler_sensitivity_scan,
    euler_to_quat,
    euler_zyx_to_dcm,
    integrate_attitude,
    process,
    quat_axis_angle,
    quat_mul,
    quat_to_dcm,
    rot_x,
    rot_z,
    sequence_frames,
)


def test_dcm_orthogonal():
    r = euler_zyx_to_dcm(0.3, -0.2, 0.1)
    assert abs(np.linalg.det(r) - 1.0) < 1e-9
    assert np.allclose(r @ r.T, np.eye(3), atol=1e-9)


def test_euler_roundtrip():
    y, p, r = 0.4, -0.25, 0.15
    y2, p2, r2 = dcm_to_euler_zyx(euler_zyx_to_dcm(y, p, r))
    assert np.allclose([y2, p2, r2], [y, p, r], atol=1e-9)


def test_quat_roundtrip_and_dcm_to_quat():
    q = euler_to_quat(0.2, -0.1, 0.3)
    y, p, r = dcm_to_euler_zyx(quat_to_dcm(q))
    assert np.allclose([y, p, r], [0.2, -0.1, 0.3], atol=1e-9)
    assert np.allclose(dcm_to_quat(quat_to_dcm(q)), q, atol=1e-9)


def test_quat_double_cover():
    q = euler_to_quat(2.5, 0.3, -2.0)
    assert np.allclose(quat_to_dcm(q), quat_to_dcm(-q))


def test_quat_product_matches_dcm_product():
    qa, qb = euler_to_quat(0.3, 0.1, -0.2), euler_to_quat(-1.0, 0.4, 0.7)
    assert np.allclose(quat_to_dcm(quat_mul(qa, qb)), quat_to_dcm(qa) @ quat_to_dcm(qb))


def test_axis_angle_of_pure_yaw():
    axis, ang = quat_axis_angle(euler_to_quat(40 * DEG2RAD, 0.0, 0.0))
    assert np.allclose(axis, [0, 0, 1]) and np.isclose(ang, 40.0)


def test_ned_enu_conversion_same_physical_vectors():
    r = euler_zyx_to_dcm(0.5, 0.2, -0.3)
    r_ros = dcm_ned_frd_to_enu_flu(r)
    v_frd = np.array([1.0, 0.3, -0.2])
    v_flu = np.diag([1, -1, -1]) @ v_frd
    assert np.allclose(T_NED_ENU @ (r @ v_frd), r_ros @ v_flu)
    assert np.isclose(np.linalg.det(r_ros), 1.0)


def test_ros_euler_matches_converted_dcm():
    y, p, r = 30.0, 12.0, -8.0
    y2, p2, r2 = euler_ned_to_ros(y, p, r)
    r_ros = dcm_ned_frd_to_enu_flu(euler_zyx_to_dcm(y * DEG2RAD, p * DEG2RAD, r * DEG2RAD))
    assert np.allclose(euler_zyx_to_dcm(y2 * DEG2RAD, p2 * DEG2RAD, r2 * DEG2RAD), r_ros, atol=1e-9)


def test_intrinsic_zyx_equals_extrinsic_xyz_but_not_swapped():
    a = sequence_frames(40, 25, 30, Sequence.INTRINSIC_ZYX)["final"]
    b = sequence_frames(40, 25, 30, Sequence.EXTRINSIC_XYZ)["final"]
    c = sequence_frames(40, 25, 30, Sequence.INTRINSIC_XYZ)["final"]
    assert np.allclose(a, b)
    assert not np.allclose(a, c, atol=1e-3)
    assert np.allclose(a, euler_zyx_to_dcm(40 * DEG2RAD, 25 * DEG2RAD, 30 * DEG2RAD))


def test_rotations_do_not_commute():
    assert not np.allclose(rot_x(0.5) @ rot_z(0.5), rot_z(0.5) @ rot_x(0.5))


def test_gimbal_lock_sensitivity_grows_near_90():
    scan = euler_sensitivity_scan(20.0, 10.0, np.array([0.0, 60.0, 89.0]), 0.5)
    assert scan["dyaw_deg"][0] < 0.6
    assert scan["dyaw_deg"][2] > 10.0
    assert scan["dyaw_deg"][2] > scan["dyaw_deg"][1] > scan["dyaw_deg"][0] - 1e-9


def test_process_snapshot():
    out = process(AttitudeParams(yaw_deg=20.0, pitch_deg=10.0, roll_deg=-5.0))
    assert np.isclose(out["det_dcm"], 1.0)
    assert out["quat_neg_dcm_err"] < 1e-12
    assert np.allclose(out["euler_from_quat_deg"], [20.0, 10.0, -5.0])


def test_constant_rate_quat_exp_is_exact():
    p = AttitudeParams(yaw_deg=0, pitch_deg=0, roll_deg=0, wx_dps=10, wy_dps=-20, wz_dps=30, int_dt_s=0.1)
    out = integrate_attitude(p)
    assert out["final_angle_err_deg"] < 1e-6


def test_first_order_dcm_loses_orthonormality_and_renorm_fixes_it():
    base = dict(yaw_deg=0, pitch_deg=0, roll_deg=0, wz_dps=90.0, int_dt_s=0.05, integrator=Integrator.DCM_EULER)
    raw = integrate_attitude(AttitudeParams(**base))
    fix = integrate_attitude(AttitudeParams(**base, renormalize=True))
    assert raw["final_ortho_err"] > 0.05
    assert fix["final_ortho_err"] < 1e-9


def test_coning_with_coarse_step_drifts():
    base = dict(yaw_deg=0, pitch_deg=0, roll_deg=0, wz_dps=0.0, coning_amp_dps=60.0, coning_hz=2.0, int_duration_s=5.0)
    fine = integrate_attitude(AttitudeParams(**base, int_dt_s=0.002))
    coarse = integrate_attitude(AttitudeParams(**base, int_dt_s=0.05))
    assert coarse["final_angle_err_deg"] > 5 * fine["final_angle_err_deg"]
