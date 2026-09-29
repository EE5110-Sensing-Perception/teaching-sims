"""Dear PyGui desktop app for accelerometer teaching."""

from __future__ import annotations

import math
from dataclasses import replace

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.core.imu import G0
from teaching_sims.topics.accelerometer.physics import (
    AccelParams,
    process,
    six_position_calibration,
    tilt_error_curve,
    tilt_from_accel,
)
from teaching_sims.topics.accelerometer.scenarios import SCENARIOS, get_scenario
from teaching_sims.ui.desktop import imu_style
from teaching_sims.ui.desktop.imu_style import bind_role, draw_vector, rgba
from teaching_sims.ui.desktop.plot_utils import fit_axes, fxy as _fxy
from teaching_sims.ui.external.cube_view import CubeAttitudeView

DRAW_W, DRAW_H = 700, 300
PANE_W = DRAW_W // 2
PX_PER_MPS2 = 9.0  # vector scale in the schematic

# (tag, label, attribute, lo, hi, format)
ERROR_SLIDERS = (
    ("bias_x", "Bias X (m/s^2)", "bias_x_mps2", -1.0, 1.0, "%.2f"),
    ("bias_y", "Bias Y (m/s^2)", "bias_y_mps2", -1.0, 1.0, "%.2f"),
    ("bias_z", "Bias Z (m/s^2)", "bias_z_mps2", -1.0, 1.0, "%.2f"),
    ("scale_x", "Scale X (%)", "scale_x_pct", -5.0, 5.0, "%.1f"),
    ("scale_y", "Scale Y (%)", "scale_y_pct", -5.0, 5.0, "%.1f"),
    ("scale_z", "Scale Z (%)", "scale_z_pct", -5.0, 5.0, "%.1f"),
    ("mis_xy", "Misalign x<-y (mrad)", "mis_xy_mrad", -20.0, 20.0, "%.1f"),
    ("mis_xz", "Misalign x<-z (mrad)", "mis_xz_mrad", -20.0, 20.0, "%.1f"),
    ("mis_yz", "Misalign y<-z (mrad)", "mis_yz_mrad", -20.0, 20.0, "%.1f"),
)
MOTION_SLIDERS = (
    ("ax", "Surge ax (m/s^2)", "ax_mps2", -5.0, 5.0, "%.2f"),
    ("ay", "Sway ay (m/s^2)", "ay_mps2", -5.0, 5.0, "%.2f"),
    ("az", "Heave az (m/s^2)", "az_mps2", -5.0, 5.0, "%.2f"),
    ("vibe_amp", "Vibration amp (m/s^2)", "vibe_amp_mps2", 0.0, 5.0, "%.2f"),
    ("vibe_hz", "Vibration Hz", "vibe_hz", 1.0, 45.0, "%.1f"),
    ("lever_x", "Lever arm x (m)", "lever_x_m", -1.0, 1.0, "%.2f"),
    ("lever_y", "Lever arm y (m)", "lever_y_m", -1.0, 1.0, "%.2f"),
    ("yaw_rate", "Yaw rate (deg/s)", "yaw_rate_dps", -180.0, 180.0, "%.0f"),
    ("yaw_acc", "Yaw accel (deg/s^2)", "yaw_accel_dps2", -180.0, 180.0, "%.0f"),
)
ADVANCED_SLIDERS = (
    ("noise", "Noise sigma (m/s^2)", "noise_mps2", 0.0, 0.5, "%.3f"),
    ("avg_win", "Average window (s)", "avg_window_s", 0.05, 3.0, "%.2f"),
    ("duration", "Duration (s)", "duration_s", 1.0, 10.0, "%.1f"),
)
ALL_SLIDERS = (
    ("yaw", "Yaw (deg)", "yaw_deg", -180.0, 180.0, "%.1f"),
    ("roll", "Roll (deg)", "roll_deg", -60.0, 60.0, "%.1f"),
    ("pitch", "Pitch (deg)", "pitch_deg", -80.0, 80.0, "%.1f"),
) + ERROR_SLIDERS + MOTION_SLIDERS + ADVANCED_SLIDERS


class AccelApp:
    def __init__(self, initial: AccelParams | None = None, scenario_id: str | None = None) -> None:
        self.params = initial or AccelParams()
        self.scenario_id = scenario_id
        self._seed = self.params.seed
        self._cube_view = CubeAttitudeView()
        self._suppress = False
        self._cal: dict[str, object] | None = None
        if scenario_id:
            sc = get_scenario(scenario_id)
            self.params = sc.params
            self._title = sc.title
            self._note = f"{sc.teaching_point}\n{sc.notes}"
        else:
            self._title = "Accelerometer / specific force"
            self._note = "Gravity, tilt from accel, sensor errors, calibration and linear-acceleration contamination."

    # --- controls ---------------------------------------------------------------------
    def _read_controls(self) -> AccelParams:
        kw = {attr: float(dpg.get_value(tag)) for tag, _l, attr, *_ in ALL_SLIDERS}
        return replace(
            self.params,
            **kw,
            compensate_lever=bool(dpg.get_value("comp_lever")),
            seed=self._seed,
        )

    def _push_controls(self, p: AccelParams) -> None:
        self._suppress = True
        try:
            for tag, _l, attr, *_ in ALL_SLIDERS:
                dpg.set_value(tag, float(getattr(p, attr)))
            dpg.set_value("comp_lever", p.compensate_lever)
            self._seed = p.seed
        finally:
            self._suppress = False

    def _apply_scenario(self, scenario_id: str) -> None:
        sc = get_scenario(scenario_id)
        self.scenario_id = scenario_id
        self.params = sc.params
        self._title = sc.title
        self._note = f"{sc.teaching_point}\n{sc.notes}"
        self._cal = None
        self._push_controls(self.params)
        dpg.set_value("apply_cal", False)
        dpg.set_value("banner_title", self._title)
        dpg.set_value("banner_body", self._note)
        dpg.set_value("scenario_text", self._note)
        self._show_cal_results()
        self.refresh()

    def _set_presenter(self, _s=None, app_data=None, _u=None) -> None:
        on = bool(app_data if app_data is not None else dpg.get_value("presenter_mode"))
        dpg.configure_item("advanced_controls", show=not on)
        dpg.configure_item("banner_panel", height=110 if on else 72)
        imu_style.apply_presenter(on)

    def _toggle_3d(self, _s=None, app_data=None, _u=None) -> None:
        want = bool(app_data if app_data is not None else dpg.get_value("show_3d"))
        self._cube_view.set_enabled(want)
        self.refresh()

    def _resample(self) -> None:
        self._seed += 1
        self.refresh()

    def _on_change(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self.refresh()

    # --- calibration ------------------------------------------------------------------
    def _run_calibration(self) -> None:
        try:
            p = self._read_controls()
        except ValueError:
            return
        self._cal = six_position_calibration(p, samples_per_pose=int(dpg.get_value("cal_samples")))
        self._show_cal_results()
        self.refresh()

    def _show_cal_results(self) -> None:
        if self._cal is None:
            dpg.set_value("cal_text", "Not run yet. Press the button to tumble the IMU through six poses.")
            for tag in ("cal_true", "cal_est"):
                dpg.set_value(tag, [[0.0], [0.0]])
            return
        c = self._cal
        lines = ["pose            mean reading (m/s^2)"]
        for lab, y in zip(c["labels"], c["y_mean"]):
            lines.append(f"{lab:15s} [{y[0]:+6.2f} {y[1]:+6.2f} {y[2]:+6.2f}]")
        g_est, g_true = c["gain"], c["true_gain"]
        b_est, b_true = c["bias"], c["true_bias"]
        lines.append("")
        lines.append("param        true      estimate")
        for k, ax in enumerate("xyz"):
            lines.append(f"bias {ax} mg  {b_true[k] / G0 * 1e3:+8.1f}  {b_est[k] / G0 * 1e3:+8.1f}")
        for k, ax in enumerate("xyz"):
            lines.append(f"scale {ax} %  {(g_true[k, k] - 1) * 100:+8.2f}  {(g_est[k, k] - 1) * 100:+8.2f}")
        for (i, j), nm in (((0, 1), "x<-y"), ((0, 2), "x<-z"), ((1, 2), "y<-z")):
            lines.append(f"mis {nm} mrad{g_true[i, j] / g_true[i, i] * 1e3:+7.1f}  {g_est[i, j] / g_est[i, i] * 1e3:+8.1f}")
        lines.append(f"fit residual rms: {c['residual_rms'] * 1e3:.2f} mm/s^2")
        dpg.set_value("cal_text", "\n".join(lines))
        xs = np.arange(9, dtype=float)
        def vec(g, b):
            return np.concatenate([b / G0 * 1e3, (np.diag(g) - 1) * 100 * 10, [g[0, 1] * 1e3, g[0, 2] * 1e3, g[1, 2] * 1e3]])
        dpg.set_value("cal_true", [list(xs - 0.18), list(map(float, vec(g_true, b_true)))])
        dpg.set_value("cal_est", [list(xs + 0.18), list(map(float, vec(g_est, b_est)))])
        fit_axes("cal_x", "cal_y")

    # --- schematic --------------------------------------------------------------------
    def _draw_plane(self, x0: float, title: str, angle_deg: float, f_a: float, f_z: float,
                    est_angle_deg: float, disturb: tuple[float, float], a_label: str, rear: bool) -> None:
        """One vertical-plane view. Screen: right = horizontal, down = gravity.

        ``angle_deg`` rotates the body axis 'a' (x for the side view, y for the
        rear view) from the horizontal; ``f_a``/``f_z`` are measured specific
        force components along body a and z.
        """
        tag = "accel_draw"
        cx, cy = x0 + PANE_W / 2, DRAW_H * 0.55
        a = math.radians(angle_deg)
        # body a-axis and z-axis in screen coordinates (y down)
        if rear:  # roll: positive = right side down
            ua = (math.cos(a), math.sin(a))
        else:  # pitch: positive = nose up
            ua = (math.cos(a), -math.sin(a))
        uz = (-ua[1], ua[0]) if not rear else (-ua[1], ua[0])
        dpg.draw_text((x0 + 10, 8), title, color=(220, 220, 230, 255), size=15, parent=tag)
        # true horizon
        dpg.draw_line((x0 + 20, cy), (x0 + PANE_W - 20, cy), color=(90, 95, 105, 255), thickness=1, parent=tag)
        dpg.draw_text((x0 + PANE_W - 70, cy + 4), "true level", color=(120, 125, 135, 255), size=12, parent=tag)
        # apparent level: body a-axis rotated back by the estimated tilt
        e = math.radians(est_angle_deg)
        ca, sa = math.cos(e if not rear else -e), math.sin(e if not rear else -e)
        ux_app = (ua[0] * ca - ua[1] * sa, ua[0] * sa + ua[1] * ca)
        L = PANE_W * 0.42
        dpg.draw_line((cx - L * ux_app[0], cy - L * ux_app[1]), (cx + L * ux_app[0], cy + L * ux_app[1]),
                      color=rgba("cursor", 200), thickness=2, parent=tag)
        dpg.draw_text((cx + L * ux_app[0] - 80, cy + L * ux_app[1] - 22), "apparent level",
                      color=rgba("cursor"), size=12, parent=tag)
        # body block
        hw, hh = 70.0, 18.0
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        pts = [(cx + p * ua[0] + q * uz[0], cy + p * ua[1] + q * uz[1]) for p, q in corners]
        dpg.draw_polygon(pts + [pts[0]], color=(210, 210, 220, 255), fill=(90, 95, 110, 160), thickness=2, parent=tag)
        nose = (cx + hw * ua[0], cy + hw * ua[1])
        dpg.draw_circle(nose, 5, color=rgba("fused"), fill=rgba("fused"), parent=tag)
        draw_vector(tag, (cx, cy), (95 * ua[0], 95 * ua[1]), (240, 85, 85, 255), label=a_label, size=13, thickness=2)
        draw_vector(tag, (cx, cy), (60 * uz[0], 60 * uz[1]), (90, 150, 245, 255), label="z", size=13, thickness=2)
        # gravity (down) and measured specific force
        draw_vector(tag, (x0 + 34, cy - 60), (0.0, G0 * PX_PER_MPS2 * 0.6), rgba("reference"), label="g",
                    size=13, label_offset=(6, -12))
        fx_s = f_a * ua[0] + f_z * uz[0]
        fy_s = f_a * ua[1] + f_z * uz[1]
        draw_vector(tag, (cx, cy), (fx_s * PX_PER_MPS2, fy_s * PX_PER_MPS2), rgba("accel"), label="f meas",
                    size=14, thickness=4, label_offset=(-70, -18))
        # the part of f that is not gravity: errors / motion, drawn at the tip of the gravity-only vector
        d_a, d_z = disturb
        if abs(d_a) + abs(d_z) > 1e-3:
            g_a, g_z = f_a - d_a, f_z - d_z
            tip = (cx + (g_a * ua[0] + g_z * uz[0]) * PX_PER_MPS2, cy + (g_a * ua[1] + g_z * uz[1]) * PX_PER_MPS2)
            dvec = ((d_a * ua[0] + d_z * uz[0]) * PX_PER_MPS2, (d_a * ua[1] + d_z * uz[1]) * PX_PER_MPS2)
            draw_vector(tag, tip, dvec, rgba("error"), label="bias+motion", size=12, thickness=3, head=8,
                        label_offset=(14, 8))
        dpg.draw_text((x0 + 10, DRAW_H - 44), f"true {angle_deg:+.1f} deg   accel says {est_angle_deg:+.1f} deg",
                      color=(230, 230, 235, 255), size=15, parent=tag)
        err = est_angle_deg - angle_deg
        dpg.draw_text((x0 + 10, DRAW_H - 24), f"error {err:+.2f} deg",
                      color=rgba("error") if abs(err) > 0.5 else (160, 200, 160, 255), size=15, parent=tag)

    def _draw_schematic(self, out: dict[str, object]) -> None:
        tag = "accel_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (DRAW_W, DRAW_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        dpg.draw_line((PANE_W, 0), (PANE_W, DRAW_H), color=(60, 60, 70, 255), parent=tag)
        p = self.params
        f = np.asarray(out["mean_f_body"], dtype=float)
        # disturbance = everything except pure gravity (in body axes)
        from teaching_sims.topics.accelerometer.physics import gravity_specific_force_body

        dist = f - gravity_specific_force_body(p.yaw_deg, p.pitch_deg, p.roll_deg)
        roll_hat, pitch_hat = tilt_from_accel(*f)
        self._draw_plane(0, "Side view (pitch plane)", p.pitch_deg, f[0], f[2], pitch_hat, (dist[0], dist[2]),
                         "x fwd", rear=False)
        self._draw_plane(PANE_W, "Rear view (roll plane)", p.roll_deg, f[1], f[2], roll_hat, (dist[1], dist[2]),
                         "y right", rear=True)

    # --- refresh ---------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            self.params = self._read_controls()
        except ValueError as exc:
            dpg.set_value("status_text", f"Invalid settings: {exc}")
            return
        p = self.params
        cal = None
        if self._cal is not None and bool(dpg.get_value("apply_cal")):
            cal = {"gain": self._cal["gain"], "bias": self._cal["bias"]}
        out = process(p, cal=cal)
        t = out["t_s"]
        dpg.set_value("fx_series", _fxy(t, out["fx"]))
        dpg.set_value("fy_series", _fxy(t, out["fy"]))
        dpg.set_value("fz_series", _fxy(t, out["fz"]))
        dpg.set_value("roll_series", _fxy(t, out["roll_est_deg"]))
        dpg.set_value("pitch_series", _fxy(t, out["pitch_est_deg"]))
        dpg.set_value("roll_avg", _fxy(t, out["roll_avg_deg"]))
        dpg.set_value("pitch_avg", _fxy(t, out["pitch_avg_deg"]))
        dpg.set_value("roll_true", [[0.0, float(t[-1])], [p.roll_deg, p.roll_deg]])
        dpg.set_value("pitch_true", [[0.0, float(t[-1])], [p.pitch_deg, p.pitch_deg]])
        fit_axes("acc_t", "acc_y", "tilt_t", "tilt_y")

        d = np.linspace(-3.0, 3.0, 121)
        curve = tilt_error_curve(p, d)
        dpg.set_value("sens_curve", _fxy(curve["d_mps2"], curve["pitch_err_deg"]))
        from teaching_sims.topics.accelerometer.physics import gravity_specific_force_body

        dist_x = float(out["mean_f_body"][0] - gravity_specific_force_body(p.yaw_deg, p.pitch_deg, p.roll_deg)[0])
        dpg.set_value("sens_mark", [[dist_x], [float(out["pitch_err_deg"])]])
        fit_axes("sens_x", "sens_y")

        self._draw_schematic(out)
        if self._cube_view.enabled or (dpg.does_item_exist("show_3d") and dpg.get_value("show_3d")):
            if bool(dpg.get_value("show_3d")) != self._cube_view.enabled:
                self._cube_view.set_enabled(bool(dpg.get_value("show_3d")))
            if self._cube_view.enabled:
                self._cube_view.update(p.yaw_deg, p.pitch_deg, p.roll_deg)
        if self._cube_view.last_error:
            dpg.set_value("show_3d", False)
            self._cube_view.set_enabled(False)

        lev = out["lever_accel"]
        cal_note = "  (calibrated)" if cal is not None else ""
        dpg.set_value(
            "status_text",
            (
                f"True roll/pitch:  {p.roll_deg:+.1f} / {p.pitch_deg:+.1f} deg (yaw {p.yaw_deg:.0f} unobservable)\n"
                f"Mean estimate:    {out['roll_mean_deg']:+.1f} / {out['pitch_mean_deg']:+.1f} deg{cal_note}\n"
                f"Error:            {out['roll_err_deg']:+.2f} / {out['pitch_err_deg']:+.2f} deg\n"
                f"Mean f (m/s^2):   [{out['mean_f_body'][0]:+.2f}, {out['mean_f_body'][1]:+.2f}, "
                f"{out['mean_f_body'][2]:+.2f}]\n"
                f"Lever-arm accel:  [{lev[0]:+.2f}, {lev[1]:+.2f}, {lev[2]:+.2f}]"
                f"{' (compensated)' if p.compensate_lever else ''}"
                + (f"\n3D window: {self._cube_view.last_error}" if self._cube_view.last_error else "")
            ),
        )

    # --- layout ----------------------------------------------------------------------
    def _slider(self, spec) -> None:
        tag, label, attr, lo, hi, fmt = spec
        dpg.add_slider_float(tag=tag, label=label, default_value=float(getattr(self.params, attr)),
                             min_value=lo, max_value=hi, format=fmt, callback=self._on_change)

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Teaching Sims - Accelerometer", width=1520, height=990)
        imu_style.bind_base_theme()

        try:
            with dpg.window(tag="primary", label="Accelerometer"):
                with dpg.child_window(tag="banner_panel", height=72, border=True):
                    dpg.add_text(self._title, tag="banner_title")
                    dpg.add_text(self._note, tag="banner_body", wrap=1100)
                with dpg.group(horizontal=True):
                    with dpg.child_window(width=370, border=True):
                        dpg.add_checkbox(tag="presenter_mode", label="Presenter mode (hide advanced)",
                                         default_value=False, callback=self._set_presenter)
                        dpg.add_checkbox(tag="show_3d", label="Show 3D attitude window (matplotlib)",
                                         default_value=False, callback=self._toggle_3d)
                        dpg.add_button(label="Resample noise", width=-1, callback=lambda: self._resample())
                        dpg.add_separator()
                        dpg.add_text("Attitude (truth)")
                        for spec in ALL_SLIDERS[:3]:
                            self._slider(spec)
                        dpg.add_text("Linear motion")
                        for spec in MOTION_SLIDERS[:1]:
                            self._slider(spec)
                        dpg.add_text("Sensor errors")
                        for spec in ERROR_SLIDERS[:1]:
                            self._slider(spec)
                        with dpg.group(tag="advanced_controls"):
                            dpg.add_separator()
                            dpg.add_text("More errors")
                            for spec in ERROR_SLIDERS[1:]:
                                self._slider(spec)
                            dpg.add_text("More motion / lever arm")
                            for spec in MOTION_SLIDERS[1:]:
                                self._slider(spec)
                            dpg.add_checkbox(tag="comp_lever", label="Compensate lever arm (known w, r)",
                                             default_value=self.params.compensate_lever, callback=self._on_change)
                            dpg.add_text("Advanced")
                            for spec in ADVANCED_SLIDERS:
                                self._slider(spec)
                        dpg.add_separator()
                        dpg.add_text("Lecture scenarios")
                        for sid, sc in SCENARIOS.items():
                            dpg.add_button(label=sc.title, width=-1, user_data=sid,
                                           callback=lambda s, a, u: self._apply_scenario(u))
                        dpg.add_separator()
                        dpg.add_text(self._note, tag="scenario_text", wrap=340)
                        dpg.add_separator()
                        dpg.add_text("", tag="status_text", wrap=350)

                    with dpg.child_window(border=False):
                        with dpg.group(horizontal=True):
                            dpg.add_drawlist(width=DRAW_W, height=DRAW_H, tag="accel_draw")
                            with dpg.plot(label="Pitch error vs extra x specific force", height=DRAW_H, width=-1):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="bias = surge = lever arm (m/s^2)", tag="sens_x")
                                with dpg.plot_axis(dpg.mvYAxis, label="pitch error (deg)", tag="sens_y"):
                                    dpg.add_line_series([0.0], [0.0], label="atan model", tag="sens_curve")
                                    dpg.add_scatter_series([0.0], [0.0], label="now", tag="sens_mark")
                        with dpg.plot(label="Specific force (body)", height=220, width=-1):
                            dpg.add_plot_legend()
                            dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="acc_t")
                            with dpg.plot_axis(dpg.mvYAxis, label="m/s^2", tag="acc_y"):
                                dpg.add_line_series([0.0], [0.0], label="fx", tag="fx_series")
                                dpg.add_line_series([0.0], [0.0], label="fy", tag="fy_series")
                                dpg.add_line_series([0.0], [0.0], label="fz", tag="fz_series")
                        with dpg.tab_bar(tag="acc_tabs"):
                            with dpg.tab(label="Tilt from accelerometer", tag="tab_tilt"):
                                with dpg.plot(height=-1, width=-1):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="tilt_t")
                                    with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="tilt_y"):
                                        dpg.add_line_series([0.0], [0.0], label="roll instant", tag="roll_series")
                                        dpg.add_line_series([0.0], [0.0], label="pitch instant", tag="pitch_series")
                                        dpg.add_line_series([0.0], [0.0], label="roll averaged", tag="roll_avg")
                                        dpg.add_line_series([0.0], [0.0], label="pitch averaged", tag="pitch_avg")
                                        dpg.add_line_series([0.0], [0.0], label="roll true", tag="roll_true")
                                        dpg.add_line_series([0.0], [0.0], label="pitch true", tag="pitch_true")
                            with dpg.tab(label="Six-position calibration", tag="tab_cal"):
                                with dpg.group(horizontal=True):
                                    with dpg.child_window(width=440, border=True):
                                        dpg.add_button(label="Run six-position calibration", width=-1,
                                                       callback=lambda: self._run_calibration())
                                        dpg.add_slider_int(tag="cal_samples", label="Samples per pose",
                                                           default_value=200, min_value=10, max_value=2000)
                                        dpg.add_checkbox(tag="apply_cal", label="Apply calibration to live data",
                                                         default_value=False, callback=self._on_change)
                                        dpg.add_text("", tag="cal_text")
                                    with dpg.plot(label="True vs estimated (bias mg, scale %x10, mis mrad)",
                                                  height=-1, width=-1):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, tag="cal_x", no_tick_labels=False)
                                        dpg.set_axis_ticks("cal_x", tuple(
                                            (lab, float(i)) for i, lab in enumerate(
                                                ["bx", "by", "bz", "sx", "sy", "sz", "xy", "xz", "yz"])))
                                        with dpg.plot_axis(dpg.mvYAxis, tag="cal_y"):
                                            dpg.add_bar_series([0.0], [0.0], weight=0.35, label="true", tag="cal_true")
                                            dpg.add_bar_series([0.0], [0.0], weight=0.35, label="estimate",
                                                               tag="cal_est")

            for tag, role in (("fx_series", "error"), ("fy_series", "accel"), ("fz_series", "gyro"),
                              ("roll_series", "measured"), ("pitch_series", "measured"),
                              ("roll_avg", "accel"), ("pitch_avg", "fused"), ("roll_true", "truth"),
                              ("pitch_true", "truth"), ("sens_curve", "fused")):
                bind_role(tag, role, weight=1.2 if tag in ("roll_series", "pitch_series") else 2.0)
            bind_role("sens_mark", "cursor", kind="scatter", weight=4.0)
            bind_role("cal_true", "truth", kind="bar")
            bind_role("cal_est", "fused", kind="bar")

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("primary", True)
            self._push_controls(self.params)
            self._show_cal_results()
            self.refresh()

            while dpg.is_dearpygui_running():
                dpg.render_dearpygui_frame()
        finally:
            self._cube_view.close()
            dpg.destroy_context()
            imu_style.reset_bindings()


def run_app(scenario_id: str | None = None, params: AccelParams | None = None) -> None:
    if scenario_id and params is None:
        params = get_scenario(scenario_id).params
    AccelApp(initial=params, scenario_id=scenario_id).run()
