"""Dear PyGui desktop app for magnetometer / heading teaching."""

from __future__ import annotations

import math
from dataclasses import replace

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.core.imu import wrap_180
from teaching_sims.topics.magnetometer.physics import MagParams, compass_swing, earth_field_ned, process
from teaching_sims.topics.magnetometer.scenarios import SCENARIOS, get_scenario
from teaching_sims.ui.desktop import imu_style
from teaching_sims.ui.desktop.imu_style import bind_role, draw_dial, draw_vector, rgba
from teaching_sims.ui.desktop.plot_utils import fit_axes, fxy as _fxy

PANEL = 310

# (tag, label, attribute, lo, hi, format)
MAIN_SLIDERS = (
    ("yaw", "True heading (deg)", "yaw_deg", -180.0, 180.0, "%.1f"),
    ("pitch", "Pitch (deg)", "pitch_deg", -60.0, 60.0, "%.1f"),
    ("roll", "Roll (deg)", "roll_deg", -60.0, 60.0, "%.1f"),
    ("hard_x", "Hard-iron X (uT)", "hard_x_ut", -20.0, 20.0, "%.1f"),
    ("hard_y", "Hard-iron Y (uT)", "hard_y_ut", -20.0, 20.0, "%.1f"),
    ("decl", "Declination (deg)", "declination_deg", -30.0, 30.0, "%.1f"),
)
ADV_SLIDERS = (
    ("incl", "Inclination / dip (deg)", "inclination_deg", 0.0, 85.0, "%.1f"),
    ("hard_z", "Hard-iron Z (uT)", "hard_z_ut", -20.0, 20.0, "%.1f"),
    ("soft_xx", "Soft-iron xx", "soft_xx", 0.5, 1.5, "%.2f"),
    ("soft_yy", "Soft-iron yy", "soft_yy", 0.5, 1.5, "%.2f"),
    ("soft_xy", "Soft-iron xy", "soft_xy", -0.4, 0.4, "%.2f"),
    ("dist_n", "Disturbance N (uT)", "dist_n_ut", -15.0, 15.0, "%.1f"),
    ("dist_e", "Disturbance E (uT)", "dist_e_ut", -15.0, 15.0, "%.1f"),
    ("dist_d", "Disturbance D (uT)", "dist_d_ut", -15.0, 15.0, "%.1f"),
    ("noise", "Noise sigma (uT)", "noise_ut", 0.0, 2.0, "%.2f"),
)
SLIDERS = MAIN_SLIDERS + ADV_SLIDERS


class MagApp:
    def __init__(self, initial: MagParams | None = None, scenario_id: str | None = None) -> None:
        self.params = initial or MagParams()
        self.scenario_id = scenario_id
        self._seed = self.params.seed
        self._suppress = False
        self._cal: dict | None = None
        self._auto_cal = False
        if scenario_id:
            sc = get_scenario(scenario_id)
            self.params = sc.params
            self._auto_cal = sc.auto_calibrate
            self._title = sc.title
            self._note = f"{sc.teaching_point}\n{sc.notes}"
        else:
            self._title = "Magnetometer / tilt-compensated heading"
            self._note = "Earth field in body frame, hard/soft iron, tilt compensation, declination and disturbances."

    # --- controls ---------------------------------------------------------------------
    def _read_controls(self) -> MagParams:
        kw = {attr: float(dpg.get_value(tag)) for tag, _l, attr, *_ in SLIDERS}
        return replace(
            self.params,
            **kw,
            tilt_compensate=bool(dpg.get_value("tilt_comp")),
            apply_declination=bool(dpg.get_value("apply_decl")),
            sweep_yaw=True,
            n_sweep=72,
            seed=self._seed,
        )

    def _push_controls(self, p: MagParams) -> None:
        self._suppress = True
        try:
            for tag, _l, attr, *_ in SLIDERS:
                dpg.set_value(tag, float(getattr(p, attr)))
            dpg.set_value("tilt_comp", p.tilt_compensate)
            dpg.set_value("apply_decl", p.apply_declination)
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
        if sc.auto_calibrate:
            self._calibrate(apply=True)
        else:
            self.refresh()

    def _calibrate(self, apply: bool = True) -> None:
        try:
            self.params = self._read_controls()
        except ValueError:
            return
        self._cal = compass_swing(self.params)
        dpg.set_value("apply_cal", apply)
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
        self.refresh()

    # --- drawing ---------------------------------------------------------------------
    def _draw_compass(self, out: dict) -> None:
        tag = "compass_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (PANEL, PANEL), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        dpg.draw_text((10, 8), "Compass (true north up)", color=(220, 220, 230, 255), size=15, parent=tag)
        p = self.params
        needles = [(p.yaw_deg, rgba("truth"), "truth")]
        needles.append((float(out["snapshot_tc_deg"]), rgba("mag"), "tilt-comp"))
        needles.append((float(out["snapshot_raw_deg"]), rgba("error"), "raw"))
        draw_dial(tag, (PANEL / 2, PANEL / 2 + 10), 110, needles)
        if abs(p.declination_deg) > 0.05:
            ox, oy = imu_style.heading_to_screen(p.declination_deg, 128)
            c = (PANEL / 2, PANEL / 2 + 10)
            dpg.draw_line(c, (c[0] + ox, c[1] + oy), color=(200, 160, 255, 160), thickness=1, parent=tag)
            dpg.draw_text((c[0] + ox + 4, c[1] + oy - 16), "mag N", color=(200, 160, 255, 255), size=13, parent=tag)
        fc = out["field_check"]
        status = "field OK" if fc["ok"] else "DISTURBED: reject"
        col = (160, 200, 160, 255) if fc["ok"] else rgba("error")
        dpg.draw_text((10, PANEL - 44), f"|B| {fc['magnitude_ut']:.1f} uT ({fc['d_mag_pct']:+.1f}%)  "
                      f"dip {fc['dip_deg']:.1f} ({fc['d_dip_deg']:+.1f})", color=(200, 200, 210, 255), size=13,
                      parent=tag)
        dpg.draw_text((10, PANEL - 24), status, color=col, size=15, parent=tag)

    def _draw_dip(self) -> None:
        """Side view in the vertical plane containing body x (heading plane)."""
        tag = "dip_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (PANEL, PANEL), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        dpg.draw_text((10, 8), "Side view: dip and pitch", color=(220, 220, 230, 255), size=15, parent=tag)
        p = self.params
        b_n = earth_field_ned(p)
        # component of the field along the body heading direction, and down
        psi = math.radians(p.yaw_deg)
        b_fwd = b_n[0] * math.cos(psi) + b_n[1] * math.sin(psi)
        b_down = b_n[2]
        c = (PANEL * 0.3, PANEL * 0.42)
        k = 2.6  # px per uT
        dpg.draw_line((20, c[1]), (PANEL - 20, c[1]), color=(90, 95, 105, 255), parent=tag)
        dpg.draw_text((20, c[1] - 18), "level", color=(120, 125, 135, 255), size=12, parent=tag)
        draw_vector(tag, c, (k * b_fwd, 0.0), rgba("accel"), label="H", size=13, thickness=3,
                    label_offset=(-14, 6))
        draw_vector(tag, c, (k * b_fwd, k * b_down), rgba("mag"), label="B (Earth)", size=13, thickness=4)
        # body x axis at pitch
        th = math.radians(p.pitch_deg)
        ux = (math.cos(th), -math.sin(th))
        draw_vector(tag, c, (150 * ux[0], 150 * ux[1]), (240, 85, 85, 255), label="body x", size=13, thickness=2,
                    label_offset=(-30, -26))
        # projection of B on body x
        proj = b_fwd * math.cos(th) - b_down * math.sin(th)
        dpg.draw_line((c[0] + k * proj * ux[0], c[1] + k * proj * ux[1]),
                      (c[0] + k * b_fwd, c[1] + k * b_down), color=(150, 150, 160, 160), thickness=1, parent=tag)
        dpg.draw_circle((c[0] + k * proj * ux[0], c[1] + k * proj * ux[1]), 4, color=(240, 85, 85, 255),
                        fill=(240, 85, 85, 255), parent=tag)
        horiz = b_fwd
        dpg.draw_text((10, PANEL - 64), f"dip {p.inclination_deg:.0f} deg: vertical/horizontal = "
                      f"{abs(b_down) / max(math.hypot(b_n[0], b_n[1]), 1e-6):.1f}", color=(200, 200, 210, 255),
                      size=13, parent=tag)
        dpg.draw_text((10, PANEL - 44), f"bx measured {proj:+.1f} uT vs level {horiz:+.1f} uT",
                      color=(240, 85, 85, 255), size=13, parent=tag)
        dpg.draw_text((10, PANEL - 24), "pitch leaks the vertical field into bx", color=(170, 170, 180, 255),
                      size=13, parent=tag)

    # --- refresh ---------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            self.params = self._read_controls()
        except ValueError as exc:
            dpg.set_value("status_text", f"Invalid settings: {exc}")
            return
        p = self.params
        use_cal = self._cal if (self._cal is not None and bool(dpg.get_value("apply_cal"))) else None
        out = process(p, cal=use_cal)
        dpg.set_value("polar", _fxy(out["bx"], out["by"]))
        if self._cal is not None:
            dpg.set_value("ellipse", _fxy(self._cal["ellipse_x"], self._cal["ellipse_y"]))
            dpg.set_value("centre", [[float(self._cal["centre"][0])], [float(self._cal["centre"][1])]])
        else:
            dpg.set_value("ellipse", [[0.0], [0.0]])
            dpg.set_value("centre", [[0.0], [0.0]])
        if use_cal is not None:
            dpg.set_value("polar_cal", _fxy(out["bx_cal"], out["by_cal"]))
        else:
            dpg.set_value("polar_cal", [[0.0], [0.0]])
        for tag in ("ellipse", "centre"):
            dpg.configure_item(tag, show=self._cal is not None)
        dpg.configure_item("polar_cal", show=use_cal is not None)

        yaws = out["yaw_sweep_deg"]
        dpg.set_value("yaw_line", _fxy(yaws, yaws))
        dpg.set_value("hdg_raw", _fxy(yaws, out["heading_raw_deg"]))
        dpg.set_value("hdg_tc", _fxy(yaws, out["heading_tc_deg"]))
        dpg.set_value("hdg_cal", _fxy(yaws, out["heading_cal_deg"]) if use_cal is not None else [[0.0], [0.0]])
        dpg.configure_item("hdg_cal", show=use_cal is not None)
        dpg.set_value("err_raw", _fxy(yaws, wrap_180(out["heading_raw_deg"] - yaws)))
        dpg.set_value("err_tc", _fxy(yaws, wrap_180(out["heading_tc_deg"] - yaws)))
        dpg.set_value("err_cal", _fxy(yaws, wrap_180(out["heading_cal_deg"] - yaws)) if use_cal is not None
                      else [[0.0], [0.0]])
        dpg.configure_item("err_cal", show=use_cal is not None)
        fit_axes("bx_ax", "by_ax", "hdg_x", "hdg_y", "err_x", "err_y")
        self._draw_compass(out)
        self._draw_dip()

        cal_txt = "none"
        if self._cal is not None:
            c = self._cal["centre"]
            cal_txt = f"centre ({c[0]:+.1f}, {c[1]:+.1f}) uT, radius {self._cal['radius']:.1f}"
            cal_txt += " [applied]" if use_cal is not None else " [not applied]"
        dpg.set_value(
            "status_text",
            (
                f"Snapshot heading: {out['snapshot_heading_deg']:.1f} deg (true {p.yaw_deg:.1f})\n"
                f"Snapshot error: {out['snapshot_err_deg']:+.2f} deg\n"
                f"RMS error over sweep: {out['rms_err_deg']:.2f} deg\n"
                f"Tilt comp: {'ON' if p.tilt_compensate else 'OFF'}   "
                f"Declination: {'applied' if p.apply_declination else 'ignored'}\n"
                f"Calibration: {cal_txt}"
            ),
        )

    # --- layout ----------------------------------------------------------------------
    def _slider(self, spec) -> None:
        tag, label, attr, lo, hi, fmt = spec
        dpg.add_slider_float(tag=tag, label=label, default_value=float(getattr(self.params, attr)),
                             min_value=lo, max_value=hi, format=fmt, callback=self._on_change)

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Teaching Sims - Magnetometer", width=1520, height=980)
        imu_style.bind_base_theme()
        try:
            with dpg.window(tag="primary", label="Magnetometer"):
                with dpg.child_window(tag="banner_panel", height=72, border=True):
                    dpg.add_text(self._title, tag="banner_title")
                    dpg.add_text(self._note, tag="banner_body", wrap=1100)
                with dpg.group(horizontal=True):
                    with dpg.child_window(width=370, border=True):
                        dpg.add_checkbox(tag="presenter_mode", label="Presenter mode (hide advanced)",
                                         default_value=False, callback=self._set_presenter)
                        dpg.add_checkbox(tag="tilt_comp", label="Tilt-compensated heading",
                                         default_value=self.params.tilt_compensate, callback=self._on_change)
                        dpg.add_checkbox(tag="apply_decl", label="Apply declination (true heading)",
                                         default_value=self.params.apply_declination, callback=self._on_change)
                        dpg.add_button(label="Resample noise", width=-1, callback=lambda: self._resample())
                        dpg.add_separator()
                        for spec in MAIN_SLIDERS:
                            self._slider(spec)
                        dpg.add_separator()
                        dpg.add_text("Hard/soft-iron calibration")
                        dpg.add_button(label="Compass swing + ellipse fit", width=-1,
                                       callback=lambda: self._calibrate(apply=True))
                        dpg.add_checkbox(tag="apply_cal", label="Apply calibration", default_value=False,
                                         callback=self._on_change)
                        with dpg.group(tag="advanced_controls"):
                            dpg.add_separator()
                            dpg.add_text("Advanced")
                            for spec in ADV_SLIDERS:
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
                            dpg.add_drawlist(width=PANEL, height=PANEL, tag="compass_draw")
                            dpg.add_drawlist(width=PANEL, height=PANEL, tag="dip_draw")
                            with dpg.plot(label="Horizontal field locus (bx, by), yaw sweep", height=PANEL,
                                          width=-1, equal_aspects=True):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="bx (uT)", tag="bx_ax")
                                with dpg.plot_axis(dpg.mvYAxis, label="by (uT)", tag="by_ax"):
                                    dpg.add_scatter_series([0.0], [0.0], label="raw", tag="polar")
                                    dpg.add_line_series([0.0], [0.0], label="fitted ellipse", tag="ellipse")
                                    dpg.add_scatter_series([0.0], [0.0], label="hard-iron centre", tag="centre")
                                    dpg.add_scatter_series([0.0], [0.0], label="calibrated", tag="polar_cal")
                        with dpg.plot(label="Heading vs true heading", height=260, width=-1):
                            dpg.add_plot_legend()
                            dpg.add_plot_axis(dpg.mvXAxis, label="true heading (deg)", tag="hdg_x")
                            with dpg.plot_axis(dpg.mvYAxis, label="heading (deg)", tag="hdg_y"):
                                dpg.add_line_series([0.0], [0.0], label="truth", tag="yaw_line")
                                dpg.add_line_series([0.0], [0.0], label="raw", tag="hdg_raw")
                                dpg.add_line_series([0.0], [0.0], label="tilt-comp", tag="hdg_tc")
                                dpg.add_line_series([0.0], [0.0], label="calibrated", tag="hdg_cal")
                        with dpg.plot(label="Heading error", height=-1, width=-1):
                            dpg.add_plot_legend()
                            dpg.add_plot_axis(dpg.mvXAxis, label="true heading (deg)", tag="err_x")
                            with dpg.plot_axis(dpg.mvYAxis, label="error (deg)", tag="err_y"):
                                dpg.add_line_series([0.0], [0.0], label="raw", tag="err_raw")
                                dpg.add_line_series([0.0], [0.0], label="tilt-comp", tag="err_tc")
                                dpg.add_line_series([0.0], [0.0], label="calibrated", tag="err_cal")

            for tag, role in (("yaw_line", "truth"), ("hdg_raw", "error"), ("hdg_tc", "mag"), ("hdg_cal", "fused"),
                              ("err_raw", "error"), ("err_tc", "mag"), ("err_cal", "fused"), ("ellipse", "mag")):
                bind_role(tag, role)
            bind_role("polar", "measured", kind="scatter", weight=2.0)
            bind_role("polar_cal", "fused", kind="scatter", weight=2.0)
            bind_role("centre", "cursor", kind="scatter", weight=4.0)

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("primary", True)
            self._push_controls(self.params)
            if self._auto_cal:
                self._calibrate(apply=True)
            else:
                self.refresh()
            while dpg.is_dearpygui_running():
                dpg.render_dearpygui_frame()
        finally:
            dpg.destroy_context()
            imu_style.reset_bindings()


def run_app(scenario_id: str | None = None, params: MagParams | None = None) -> None:
    if scenario_id and params is None:
        params = get_scenario(scenario_id).params
    MagApp(initial=params, scenario_id=scenario_id).run()
