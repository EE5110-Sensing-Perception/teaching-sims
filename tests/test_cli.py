"""CLI smoke tests (no GUI launch)."""

from __future__ import annotations

from teaching_sims.ui.cli import main


def test_list_topics(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "phased-array" in out
    assert "sar" in out
    assert "target-returns" in out
    assert "accelerometer" in out
    assert "mems-accel" in out
    assert "ins" in out
    assert "IMU track" in out


def test_list_scenarios_cfar(capsys):
    assert main(["demo", "cfar", "--list-scenarios"]) == 0
    out = capsys.readouterr().out
    assert "ca_two_targets" in out


def test_list_scenarios_target_returns(capsys):
    assert main(["demo", "target-returns", "--list-scenarios"]) == 0
    out = capsys.readouterr().out
    assert "plate_vs_sphere" in out
    assert "extended_smear" in out


def test_list_scenarios_ins(capsys):
    assert main(["demo", "ins", "--list-scenarios"]) == 0
    out = capsys.readouterr().out
    assert "accel_bias_straight" in out


def test_list_scenarios_accel_alias(capsys):
    assert main(["demo", "accel", "--list-scenarios"]) == 0
    out = capsys.readouterr().out
    assert "static_tilt" in out


def test_list_scenarios_mems_accel(capsys):
    assert main(["demo", "mems-accel", "--list-scenarios"]) == 0
    out = capsys.readouterr().out
    assert "impulse_ring" in out
    assert "output_bias" in out


def test_list_scenarios_mems_gyro(capsys):
    assert main(["demo", "mems-gyro", "--list-scenarios"]) == 0
    out = capsys.readouterr().out
    assert "quadrature_bias" in out
