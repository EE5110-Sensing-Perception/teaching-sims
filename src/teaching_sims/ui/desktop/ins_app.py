"""Dear PyGui desktop app for strapdown INS teaching."""

from __future__ import annotations

import math
from dataclasses import replace

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.core.imu_errors import GRADE_PRESETS
from teaching_sims.topics.ins.physics import (
    Aiding,
    INSParams,
    PathProfile,
    ZuptDetector,
    params_for_grade,
    process,
)
from teaching_sims.topics.ins.scenarios import SCENARIOS, get_scenario
from teaching_sims.ui.desktop import imu_style
from teaching_sims.ui.desktop.imu_style import bind_role, rgba
from teaching_sims.ui.desktop.playback import Playback
from teaching_sims.ui.desktop.plot_utils import fit_axes, fxy as _fxy

PROFILE_LABELS = {"Circle": PathProfile.CIRCLE, "Straight": PathProfile.STRAIGHT, "Stop-and-go": PathProfile.STOP_AND_GO}
LABEL_FOR_PROFILE = {v: k for k, v in PROFILE_LABELS.items()}
AIDING_LABELS = {"None (unaided)": Aiding.NONE, "ZUPT": Aiding.ZUPT, "Position fixes": Aiding.POSITION}
LABEL_FOR_AIDING = {v: k for k, v in AIDING_LABELS.items()}
DETECTOR_LABELS = {"Oracle (true stops)": ZuptDetector.ORACLE, "IMU thresholds": ZuptDetector.IMU}
LABEL_FOR_DETECTOR = {v: k for k, v in DETECTOR_LABELS.items()}
GRADE_LABELS = {"Custom": None} | {spec.name: key for key, spec in GRADE_PRESETS.items()}
REF_ROLES = {
    "init velocity": "reference",
    "accel bias": "accel",
    "initial tilt": "mag",
    "pitch gyro bias": "kalman",
    "yaw gyro bias": "gyro",
}
BLOCK_W, BLOCK_H = 640, 230

# (tag, label, attribute, lo, hi, format)
MAIN = (
    ("abx", "Accel bias fwd (m/s^2)", "accel_bias_x_mps2", -0.2, 0.2, "%.3f"),
    ("gyro_bias", "Yaw gyro bias (deg/s)", "gyro_bias_dps", -1.0, 1.0, "%.3f"),
    ("tilt0", "Initial tilt error (deg)", "tilt0_deg", -1.0, 1.0, "%.3f"),
    ("pitch_bias", "Pitch gyro bias (deg/s)", "gyro_pitch_bias_dps", -0.05, 0.05, "%.4f"),
    ("fix_int", "Fix interval (s)", "fix_interval_s", 0.5, 30.0, "%.1f"),
)
ADV = (
    ("speed", "Speed (m/s)", "speed_mps", 0.5, 20.0, "%.1f"),
    ("radius", "Radius (m)", "radius_m", 10.0, 100.0, "%.0f"),
    ("duration", "Duration (s)", "duration_s", 10.0, 300.0, "%.0f"),
    ("aby", "Accel bias right (m/s^2)", "accel_bias_y_mps2", -0.2, 0.2, "%.3f"),
    ("an", "Accel noise (m/s^2)", "accel_noise_mps2", 0.0, 0.2, "%.3f"),
    ("gn", "Gyro noise (deg/s)", "gyro_noise_dps", 0.0, 0.5, "%.3f"),
    ("v0", "Initial velocity error (m/s)", "init_vel_err_mps", -1.0, 1.0, "%.2f"),
    ("fix_sigma", "Fix noise (m)", "fix_sigma_m", 0.1, 10.0, "%.1f"),
    ("zupt_acc", "ZUPT accel threshold (m/s^2)", "zupt_acc_thr_mps2", 0.01, 1.0, "%.2f"),
)


class INSApp:
    def __init__(self, initial: INSParams | None = None, scenario_id: str | None = None) -> None:
        self.params = initial or INSParams()
        self.scenario_id = scenario_id
        self._seed = self.params.seed
        self._suppress = False
        self._out: dict | None = None
        self.playback = Playback("ins", on_time=self._on_time, speed=4.0, speed_range=(0.5, 30.0))
        if scenario_id:
            sc = get_scenario(scenario_id)
            self.params = sc.params
            self._title = sc.title
            self._note = f"{sc.teaching_point}\n{sc.notes}"
        else:
            self._title = "Strapdown INS / dead reckoning"
            self._note = "Rotate f to nav, remove g, integrate twice - and watch every error source grow."

    # --- controls ---------------------------------------------------------------------
    def _read_controls(self) -> INSParams:
        kw = {attr: float(dpg.get_value(tag)) for tag, _l, attr, *_ in MAIN + ADV}
        return replace(
            self.params,
            **kw,
            profile=PROFILE_LABELS[dpg.get_value("profile")],
            aiding=AIDING_LABELS[dpg.get_value("aiding")],
            zupt_detector=DETECTOR_LABELS[dpg.get_value("detector")],
            perfect_attitude=bool(dpg.get_value("perfect_att")),
            seed=self._seed,
        )

    def _push_controls(self, p: INSParams) -> None:
        self._suppress = True
        try:
            for tag, _l, attr, *_ in MAIN + ADV:
                dpg.set_value(tag, float(getattr(p, attr)))
            dpg.set_value("profile", LABEL_FOR_PROFILE[p.profile])
            dpg.set_value("aiding", LABEL_FOR_AIDING[p.aiding])
            dpg.set_value("detector", LABEL_FOR_DETECTOR[p.zupt_detector])
            dpg.set_value("perfect_att", p.perfect_attitude)
            self._seed = p.seed
        finally:
            self._suppress = False

    def _apply_scenario(self, scenario_id: str) -> None:
        sc = get_scenario(scenario_id)
        self.scenario_id = scenario_id
        self.params = sc.params
        self._title = sc.title
        self._note = f"{sc.teaching_point}\n{sc.notes}"
        self._push_controls(self.params)
        dpg.set_value("grade", "Custom")
        dpg.set_value("banner_title", self._title)
        dpg.set_value("banner_body", self._note)
        dpg.set_value("scenario_text", self._note)
        self.refresh()
        self.playback.play()

    def _on_grade(self, *_a, **_k) -> None:
        if self._suppress:
            return
        key = GRADE_LABELS[dpg.get_value("grade")]
        if key is None:
            return
        self.params = params_for_grade(self._read_controls(), key, calibrated=bool(dpg.get_value("calibrated")))
        self._push_controls(self.params)
        self.refresh()

    def _set_presenter(self, _s=None, app_data=None, _u=None) -> None:
        on = bool(app_data if app_data is not None else dpg.get_value("presenter_mode"))
        dpg.configure_item("advanced_controls", show=not on)
        dpg.configure_item("banner_panel", height=110 if on else 72)
        imu_style.apply_presenter(on)

    def _resample(self) -> None:
        self._seed += 1
        self.refresh()

    def _on_change(self, *_a, **_k) -> None:
        if self._suppress:
            return
        if dpg.does_item_exist("grade"):
            dpg.set_value("grade", "Custom")
        self.playback.pause()
        self.refresh()

    # --- drawing ---------------------------------------------------------------------
    def _box(self, p0, p1, text: str, col, sub: str = "", glow: bool = False) -> None:
        tag = "mech_draw"
        dpg.draw_rectangle(p0, p1, color=col, fill=(60, 64, 40, 255) if glow else (40, 44, 54, 255),
                           thickness=3 if glow else 2, parent=tag)
        dpg.draw_text((p0[0] + 6, p0[1] + 5), text, color=col, size=13, parent=tag)
        if sub:
            dpg.draw_text((p0[0] + 6, p0[1] + 22), sub, color=(170, 170, 180, 255), size=11, parent=tag)

    def _draw_mechanisation(self, i: int) -> None:
        tag = "mech_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (BLOCK_W, BLOCK_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        g, a, f, e = rgba("gyro"), rgba("accel"), rgba("fused"), rgba("error")
        o, p = self._out, self.params
        dpg.draw_text((10, 6), "Strapdown mechanisation (planar + tilt channel)", color=(220, 220, 230, 255),
                      size=14, parent=tag)
        self._box((10, 36), (110, 76), "gyro", g, "yaw, pitch")
        self._box((140, 36), (270, 76), "integrate", g, "heading, tilt")
        self._box((10, 110), (110, 150), "accel", a, "f_body")
        self._box((140, 110), (270, 150), "rotate to nav", f, "R(psi, theta) f")
        self._box((300, 110), (390, 150), "+ g", f, "remove gravity")
        self._box((420, 110), (510, 150), "integrate", f, "v")
        self._box((540, 110), (630, 150), "integrate", f, "p")
        dpg.draw_arrow((140, 56), (110, 56), color=g, thickness=2, size=6, parent=tag)
        dpg.draw_arrow((205, 110), (205, 76), color=g, thickness=2, size=6, parent=tag)
        for x0, x1 in ((110, 140), (270, 300), (390, 420), (510, 540)):
            dpg.draw_arrow((x1, 130), (x0, 130), color=f, thickness=2, size=6, parent=tag)
        zupt_now = bool(o["zupt_mask"][i]) if o is not None else False
        fix_recent = False
        if o is not None and p.aiding == Aiding.POSITION:
            k = int(round(0.5 * p.fs_hz))
            fix_recent = bool(np.any(o["fix_mask"][max(0, i - k) : i + 1]))
        if p.aiding == Aiding.ZUPT:
            self._box((380, 180), (530, 220), "ZUPT: v := 0", e if zupt_now else (120, 120, 130, 255),
                      "stationary detected" if zupt_now else "moving", glow=zupt_now)
            dpg.draw_arrow((465, 150), (465, 180), color=e if zupt_now else (90, 90, 100, 255), thickness=2,
                           size=6, parent=tag)
        elif p.aiding == Aiding.POSITION:
            self._box((440, 180), (630, 220), "position fix -> KF", e if fix_recent else (120, 120, 130, 255),
                      f"every {p.fix_interval_s:.1f} s", glow=fix_recent)
            dpg.draw_arrow((585, 150), (585, 180), color=e if fix_recent else (90, 90, 100, 255), thickness=2,
                           size=6, parent=tag)
            dpg.draw_arrow((465, 150), (465, 180), color=e if fix_recent else (90, 90, 100, 255), thickness=2,
                           size=6, parent=tag)
        else:
            dpg.draw_text((300, 190), "unaided: nothing bounds the drift", color=(170, 170, 180, 255), size=13,
                          parent=tag)
        if o is not None:
            tilt = float(o["tilt_err_deg"][i])
            dpg.draw_text((10, 170), f"tilt error {tilt:+.3f} deg -> leaks {9.81 * math.sin(math.radians(tilt)):+.3f} m/s^2",
                          color=rgba("mag"), size=13, parent=tag)
            dpg.draw_text((10, 190), f"heading error {float(o['hdg_est_deg'][i] - o['hdg_true_deg'][i]):+.2f} deg",
                          color=g, size=13, parent=tag)

    def _on_time(self, i: int, _t: float) -> None:
        o = self._out
        if o is None:
            return
        for pre, nkey, ekey, hkey in (("truth", "north_true_m", "east_true_m", "hdg_true_deg"),
                                      ("ins", "north_est_m", "east_est_m", "hdg_est_deg")):
            n_, e_ = float(o[nkey][i]), float(o[ekey][i])
            dpg.set_value(f"{pre}_marker", [[e_], [n_]])
            h = math.radians(float(o[hkey][i]))
            L = self._arrow_len
            dpg.set_value(f"{pre}_arrow", [[e_, e_ + L * math.sin(h)], [n_, n_ + L * math.cos(h)]])
        self._draw_mechanisation(i)

    # --- refresh ---------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            self.params = self._read_controls()
        except ValueError as exc:
            dpg.set_value("status_text", f"Invalid settings: {exc}")
            return
        p = self.params
        out = process(p)
        self._out = out
        t = out["t_s"]
        span = max(np.ptp(out["north_true_m"]), np.ptp(out["east_true_m"]), 10.0)
        self._arrow_len = 0.08 * span
        dpg.set_value("path_true", _fxy(out["east_true_m"], out["north_true_m"]))
        dpg.set_value("path_est", _fxy(out["east_est_m"], out["north_est_m"]))
        fm = out["fix_mask"]
        if np.any(fm):
            dpg.set_value("fix_pts", _fxy(out["fix_e"][fm], out["fix_n"][fm]))
        dpg.configure_item("fix_pts", show=bool(np.any(fm)))
        zm = out["zupt_mask"]
        if np.any(zm):
            dpg.set_value("zupt_pts", _fxy(out["east_est_m"][zm][::5], out["north_est_m"][zm][::5]))
        dpg.configure_item("zupt_pts", show=bool(np.any(zm)))
        fit_axes("east_ax", "north_ax")

        tt = np.maximum(t, t[1] if len(t) > 1 else 1e-3)
        dpg.set_value("err_series", _fxy(tt[1:], np.maximum(out["pos_err_m"][1:], 1e-4)))
        for name in REF_ROLES:
            ref = out["references"][name]
            tag = f"ref_{name.replace(' ', '_')}"
            show = bool(np.any(ref > 0))
            if show:
                dpg.set_value(tag, _fxy(tt[1:], np.maximum(ref[1:], 1e-4)))
            dpg.configure_item(tag, show=show)
        fit_axes("err_t", "err_y")
        dpg.set_value("verr_series", _fxy(t, out["vel_err_mps"]))
        dpg.set_value("hdg_true", _fxy(t, out["hdg_true_deg"]))
        dpg.set_value("hdg_est", _fxy(t, out["hdg_est_deg"]))
        fit_axes("verr_t", "verr_y", "hdg_t", "hdg_y")

        self.playback.set_times(t)
        self.playback.set_cursor_span("verr_cursor", out["vel_err_mps"])
        self._on_time(self.playback.index, self.playback.t_view)

        refs = out["references"]
        budget = "  ".join(f"{k}: {v[-1]:.1f}" for k, v in refs.items() if v[-1] > 0.05)
        dpg.set_value(
            "status_text",
            (
                f"Final position error: {out['final_pos_err_m']:.2f} m (max {out['max_pos_err_m']:.2f})\n"
                f"Final velocity error: {out['vel_err_mps'][-1]:.3f} m/s\n"
                f"Aiding: {LABEL_FOR_AIDING[p.aiding]}"
                + (f", ZUPT active {100 * out['zupt_mask'].mean():.0f}% of time" if p.aiding == Aiding.ZUPT else "")
                + f"\nUnaided references at end (m):\n  {budget if budget else 'all ~0'}"
            ),
        )

    # --- layout ----------------------------------------------------------------------
    def _slider(self, spec) -> None:
        tag, label, attr, lo, hi, fmt = spec
        dpg.add_slider_float(tag=tag, label=label, default_value=float(getattr(self.params, attr)), min_value=lo,
                             max_value=hi, format=fmt, callback=self._on_change)

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Teaching Sims - Strapdown INS", width=1540, height=990)
        imu_style.bind_base_theme()
        self._arrow_len = 5.0
        try:
            with dpg.window(tag="primary", label="INS"):
                with dpg.child_window(tag="banner_panel", height=72, border=True):
                    dpg.add_text(self._title, tag="banner_title")
                    dpg.add_text(self._note, tag="banner_body", wrap=1100)
                with dpg.group(horizontal=True):
                    with dpg.child_window(width=380, border=True):
                        dpg.add_checkbox(tag="presenter_mode", label="Presenter mode (hide advanced)",
                                         default_value=False, callback=self._set_presenter)
                        dpg.add_checkbox(tag="perfect_att", label="Perfect heading and tilt",
                                         default_value=self.params.perfect_attitude, callback=self._on_change)
                        dpg.add_button(label="Resample noise", width=-1, callback=lambda: self._resample())
                        dpg.add_separator()
                        self.playback.build_controls()
                        dpg.add_separator()
                        dpg.add_combo(tag="profile", label="Path", items=list(PROFILE_LABELS),
                                      default_value=LABEL_FOR_PROFILE[self.params.profile], callback=self._on_change)
                        dpg.add_combo(tag="grade", label="IMU grade", items=list(GRADE_LABELS), default_value="Custom",
                                      callback=self._on_grade)
                        dpg.add_checkbox(tag="calibrated", label="Grade: turn-on bias calibrated", default_value=True,
                                         callback=self._on_grade)
                        dpg.add_combo(tag="aiding", label="Aiding", items=list(AIDING_LABELS),
                                      default_value=LABEL_FOR_AIDING[self.params.aiding], callback=self._on_change)
                        dpg.add_combo(tag="detector", label="ZUPT detector", items=list(DETECTOR_LABELS),
                                      default_value=LABEL_FOR_DETECTOR[self.params.zupt_detector],
                                      callback=self._on_change)
                        for spec in MAIN:
                            self._slider(spec)
                        with dpg.group(tag="advanced_controls"):
                            dpg.add_separator()
                            dpg.add_text("Advanced")
                            for spec in ADV:
                                self._slider(spec)
                        dpg.add_separator()
                        dpg.add_text("Lecture scenarios")
                        for sid, sc in SCENARIOS.items():
                            dpg.add_button(label=sc.title, width=-1, user_data=sid,
                                           callback=lambda s, a, u: self._apply_scenario(u))
                        dpg.add_separator()
                        dpg.add_text(self._note, tag="scenario_text", wrap=350)
                        dpg.add_separator()
                        dpg.add_text("", tag="status_text", wrap=360)

                    with dpg.child_window(border=False):
                        with dpg.group(horizontal=True):
                            with dpg.plot(label="Horizontal path (NED)", height=420, width=560, equal_aspects=True):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="East (m)", tag="east_ax")
                                with dpg.plot_axis(dpg.mvYAxis, label="North (m)", tag="north_ax"):
                                    dpg.add_line_series([0.0], [0.0], label="truth", tag="path_true")
                                    dpg.add_line_series([0.0], [0.0], label="INS", tag="path_est")
                                    dpg.add_scatter_series([0.0], [0.0], label="position fixes", tag="fix_pts")
                                    dpg.add_scatter_series([0.0], [0.0], label="ZUPT", tag="zupt_pts")
                                    dpg.add_line_series([0.0, 0.0], [0.0, 0.0], tag="truth_arrow")
                                    dpg.add_line_series([0.0, 0.0], [0.0, 0.0], tag="ins_arrow")
                                    dpg.add_scatter_series([0.0], [0.0], tag="truth_marker")
                                    dpg.add_scatter_series([0.0], [0.0], tag="ins_marker")
                            with dpg.plot(label="Position error vs time (log-log)", height=420, width=-1):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="err_t", scale=dpg.mvPlotScale_Log10)
                                with dpg.plot_axis(dpg.mvYAxis, label="m", tag="err_y", scale=dpg.mvPlotScale_Log10):
                                    for name in REF_ROLES:
                                        dpg.add_line_series([1.0], [1.0], label=f"ref: {name}",
                                                            tag=f"ref_{name.replace(' ', '_')}")
                                    dpg.add_line_series([1.0], [1.0], label="|position error|", tag="err_series")
                        with dpg.group(horizontal=True):
                            dpg.add_drawlist(width=BLOCK_W, height=BLOCK_H, tag="mech_draw")
                            with dpg.tab_bar():
                                with dpg.tab(label="Velocity error"):
                                    with dpg.plot(height=-1, width=-1):
                                        dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="verr_t")
                                        with dpg.plot_axis(dpg.mvYAxis, label="m/s", tag="verr_y"):
                                            dpg.add_line_series([0.0], [0.0], tag="verr_series")
                                            dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="verr_cursor")
                                with dpg.tab(label="Heading"):
                                    with dpg.plot(height=-1, width=-1):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="hdg_t")
                                        with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="hdg_y"):
                                            dpg.add_line_series([0.0], [0.0], label="true", tag="hdg_true")
                                            dpg.add_line_series([0.0], [0.0], label="INS", tag="hdg_est")

            for tag, role in (("path_true", "truth"), ("path_est", "fused"), ("truth_arrow", "truth"),
                              ("ins_arrow", "fused"), ("err_series", "error"), ("verr_series", "error"),
                              ("hdg_true", "truth"), ("hdg_est", "gyro")):
                bind_role(tag, role, weight=3.0 if tag.endswith("arrow") else 2.0)
            for name, role in REF_ROLES.items():
                bind_role(f"ref_{name.replace(' ', '_')}", role, weight=1.2)
            bind_role("truth_marker", "truth", kind="scatter", weight=5.0)
            bind_role("ins_marker", "fused", kind="scatter", weight=5.0)
            bind_role("fix_pts", "cursor", kind="scatter", weight=2.5)
            bind_role("zupt_pts", "accel", kind="scatter", weight=2.0)
            bind_role("verr_cursor", "cursor", weight=1.5)

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("primary", True)
            self._push_controls(self.params)
            self.refresh()
            self.playback.play()
            while dpg.is_dearpygui_running():
                self.playback.tick()
                dpg.render_dearpygui_frame()
        finally:
            dpg.destroy_context()
            imu_style.reset_bindings()


def run_app(scenario_id: str | None = None, params: INSParams | None = None) -> None:
    if scenario_id and params is None:
        params = get_scenario(scenario_id).params
    INSApp(initial=params, scenario_id=scenario_id).run()
