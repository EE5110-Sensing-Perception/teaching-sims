"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable


def _load_phased_array():
    from teaching_sims.topics.phased_array.scenarios import list_scenarios
    from teaching_sims.ui.desktop.phased_array_app import run_app

    return list_scenarios, run_app


def _load_beamforming():
    from teaching_sims.topics.beamforming.scenarios import list_scenarios
    from teaching_sims.ui.desktop.beamforming_app import run_app

    return list_scenarios, run_app


def _load_pulsed_ranging():
    from teaching_sims.topics.pulsed_ranging.scenarios import list_scenarios
    from teaching_sims.ui.desktop.pulsed_ranging_app import run_app

    return list_scenarios, run_app


def _load_pulse_doppler():
    from teaching_sims.topics.pulse_doppler.scenarios import list_scenarios
    from teaching_sims.ui.desktop.pulse_doppler_app import run_app

    return list_scenarios, run_app


def _load_cfar():
    from teaching_sims.topics.cfar.scenarios import list_scenarios
    from teaching_sims.ui.desktop.cfar_app import run_app

    return list_scenarios, run_app


def _load_fmcw():
    from teaching_sims.topics.fmcw.scenarios import list_scenarios
    from teaching_sims.ui.desktop.fmcw_app import run_app

    return list_scenarios, run_app


def _load_sar():
    from teaching_sims.topics.sar.scenarios import list_scenarios
    from teaching_sims.ui.desktop.sar_app import run_app

    return list_scenarios, run_app


def _load_target_returns():
    from teaching_sims.topics.target_returns.scenarios import list_scenarios
    from teaching_sims.ui.desktop.target_returns_app import run_app

    return list_scenarios, run_app


def _load_accelerometer():
    from teaching_sims.topics.accelerometer.scenarios import list_scenarios
    from teaching_sims.ui.desktop.accelerometer_app import run_app

    return list_scenarios, run_app


def _load_gyroscope():
    from teaching_sims.topics.gyroscope.scenarios import list_scenarios
    from teaching_sims.ui.desktop.gyroscope_app import run_app

    return list_scenarios, run_app


def _load_attitude():
    from teaching_sims.topics.attitude.scenarios import list_scenarios
    from teaching_sims.ui.desktop.attitude_app import run_app

    return list_scenarios, run_app


def _load_complementary():
    from teaching_sims.topics.complementary.scenarios import list_scenarios
    from teaching_sims.ui.desktop.complementary_app import run_app

    return list_scenarios, run_app


def _load_magnetometer():
    from teaching_sims.topics.magnetometer.scenarios import list_scenarios
    from teaching_sims.ui.desktop.magnetometer_app import run_app

    return list_scenarios, run_app


def _load_ins():
    from teaching_sims.topics.ins.scenarios import list_scenarios
    from teaching_sims.ui.desktop.ins_app import run_app

    return list_scenarios, run_app


def _load_mems_accel():
    from teaching_sims.topics.mems_accel.scenarios import list_scenarios
    from teaching_sims.ui.desktop.mems_accel_app import run_app

    return list_scenarios, run_app


def _load_mems_gyro():
    from teaching_sims.topics.mems_gyro.scenarios import list_scenarios
    from teaching_sims.ui.desktop.mems_gyro_app import run_app

    return list_scenarios, run_app


# Canonical topic id -> (aliases, loader)
TOPICS: dict[str, tuple[tuple[str, ...], Callable]] = {
    "phased-array": (("phased-array", "phased_array"), _load_phased_array),
    "beamforming": (("beamforming", "beamformer"), _load_beamforming),
    "pulsed-ranging": (("pulsed-ranging", "pulsed_ranging", "ranging"), _load_pulsed_ranging),
    "pulse-doppler": (("pulse-doppler", "pulse_doppler", "doppler", "mti"), _load_pulse_doppler),
    "cfar": (("cfar", "detection"), _load_cfar),
    "fmcw": (("fmcw", "automotive"), _load_fmcw),
    "sar": (("sar", "stripmap"), _load_sar),
    "target-returns": (("target-returns", "target_returns", "rcs", "echo-returns"), _load_target_returns),
    "accelerometer": (("accelerometer", "accel"), _load_accelerometer),
    "gyroscope": (("gyroscope", "gyro"), _load_gyroscope),
    "attitude": (("attitude", "rotations", "dcm"), _load_attitude),
    "complementary": (("complementary", "comp-filter", "ahrs-lite"), _load_complementary),
    "magnetometer": (("magnetometer", "mag", "heading"), _load_magnetometer),
    "ins": (("ins", "dead-reckoning", "strapdown"), _load_ins),
    "mems-accel": (("mems-accel", "mems_accel", "comb-drive", "mems"), _load_mems_accel),
    "mems-gyro": (("mems-gyro", "mems_gyro", "coriolis", "vibratory-gyro"), _load_mems_gyro),
}

ALIAS_TO_TOPIC = {
    alias: canonical for canonical, (aliases, _) in TOPICS.items() for alias in aliases
}

RADAR_TOPICS = (
    "phased-array",
    "beamforming",
    "pulsed-ranging",
    "target-returns",
    "pulse-doppler",
    "cfar",
    "fmcw",
    "sar",
)
IMU_TOPICS = (
    "attitude",
    "mems-accel",
    "mems-gyro",
    "accelerometer",
    "gyroscope",
    "magnetometer",
    "complementary",
    "ins",
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="teaching-sims",
        description="Interactive radar and IMU teaching simulations (Dear PyGui).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Launch an interactive demo")
    demo.add_argument(
        "topic",
        choices=sorted(ALIAS_TO_TOPIC),
        help="Topic to launch (see `teaching-sims list`)",
    )
    demo.add_argument("--scenario", default=None, help="Optional scripted scenario id")
    demo.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List scenarios for the topic and exit",
    )

    sub.add_parser("list", help="List available demos / topics")
    return p


def _print_topics() -> None:
    print("Radar track:\n")
    for name in RADAR_TOPICS:
        print(f"  teaching-sims demo {name}")
    print("\nIMU track:\n")
    for name in IMU_TOPICS:
        print(f"  teaching-sims demo {name}")
    print("\nList scenarios: teaching-sims demo <topic> --list-scenarios")
    print("Tutorials: see tutorials/README.md")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list":
        _print_topics()
        return 0

    if args.command != "demo":
        print(f"unknown command: {args.command}", file=sys.stderr)
        return 1

    canonical = ALIAS_TO_TOPIC[args.topic]
    list_scenarios, run_app = TOPICS[canonical][1]()

    if args.list_scenarios:
        for sc in list_scenarios():
            print(f"{sc.id:24s}  {sc.title}")
            print(f"  {sc.teaching_point}")
        return 0

    run_app(scenario_id=args.scenario)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
