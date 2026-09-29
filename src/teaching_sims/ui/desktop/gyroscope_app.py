"""Dear PyGui desktop app for gyroscope teaching."""

from __future__ import annotations

from dataclasses import replace

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.core.imu_errors import GRADE_PRESETS
from teaching_sims.topics.gyroscope.physics import (
    GyroParams,
    MotionProfile,
    datasheet_units,
    monte_carlo_errors,
    params_for_grade,
    process,
    static_allan,
)
from teaching_sims.topics.gyroscope.scenarios import SCENARIOS, get_scenario
from teaching_sims.ui.desktop import imu_style
from teaching_sims.ui.desktop.imu_style import bind_role, draw_dial, rgba
from teaching_sims.ui.desktop.playback import Playback
from teaching_sims.ui.desktop.plot_utils import fit_axes, fxy as _fxy
from teaching_sims.ui.external.cube_view import CubeAttitudeView

PROFILE_LABELS = {
    "Step turn": MotionProfile.STEP_TURN,
    "Constant rate": MotionProfile.CONSTANT,
    "Sine": MotionProfile.SINE,
}
LABEL_FOR_PROFILE = {v: k for k, v in PROFILE_LABELS.items()}
GRADE_LABELS = {"Custom": None} | {spec.name: key for key, spec in GRADE_PRESETS.items()}
MC_MAX = 40
DIAL_W, DIAL_H = 300, 300

# (tag, label, attribute, lo, hi, format)
SLIDERS = (
    ("rate", "Rate amp (deg/s)", "rate_dps", -90.0, 90.0, "%.1f"),
    ("bias", "Bias (deg/s)", "bias_dps", -3.0, 3.0, "%.3f"),
    ("arw", "ARW (deg/sqrt(s))", "arw_deg_per_sqrt_s", 0.0, 1.0, "%.3f"),
    ("bi", "Bias instability (deg/s)", "bias_instability_dps", 0.0, 0.5, "%.4f"),
    ("rrw", "Rate random walk (deg/s/sqrt(s))", "rrw_dps_per_sqrt_s", 0.0, 0.05, "%.4f"),
    ("scale", "Scale factor (ppm)", "scale_ppm", -20000.0, 20000.0, "%.0f"),
    ("sine_hz", "Sine Hz", "sine_hz", 0.1, 2.0, "%.2f"),
    ("duration", "Duration (s)", "duration_s", 2.0, 120.0, "%.0f"),
    ("bi_tau", "BI correlation time (s)", "bi_corr_time_s", 1.0, 300.0, "%.0f"),
)


class GyroApp:
    def __init__(self, initial: GyroParams | None = None, scenario_id: str | None = None) -> None:
        self.params = initial or GyroParams()
        self.scenario_id = scenario_id
        self._seed = self.params.seed
        self._cube_view = CubeAttitudeView()
        self._suppress = False
        self._out: dict[str, object] | None = None
        self._grade = "Custom"
        self._tab = "tab_err"
        self.playback = Playback("gy", on_time=self._on_time, speed=1.0, speed_range=(0.1, 8.0))
        if scenario_id:
            sc = get_scenario(scenario_id)
            self.params = sc.params
            self._tab = sc.tab or self._tab
            self._title = sc.title
            self._note = f"{sc.teaching_point}\n{sc.notes}"
        else:
            self._title = "Gyroscope / rate integration"
            self._note = (
                "Integrate omega -> theta about Down. Bias ramps heading; ARW wanders; "
                "bias instability drifts even after calibration."
            )

    # --- controls ---------------------------------------------------------------------
    def _read_controls(self) -> GyroParams:
        kw = {attr: float(dpg.get_value(tag)) for tag, _l, attr, *_ in SLIDERS}
        return replace(
            self.params,
            **kw,
            profile=PROFILE_LABELS[dpg.get_value("profile")],
            compensate_bias=bool(dpg.get_value("comp_bias")),
            seed=self._seed,
        )

    def _push_controls(self, p: GyroParams) -> None:
        self._suppress = True
        try:
            for tag, _l, attr, *_ in SLIDERS:
                dpg.set_value(tag, float(getattr(p, attr)))
            dpg.set_value("profile", LABEL_FOR_PROFILE[p.profile])
            dpg.set_value("comp_bias", p.compensate_bias)
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
        dpg.set_value("show_mc", sc.show_mc)
        dpg.set_value("banner_title", self._title)
        dpg.set_value("banner_body", self._note)
        dpg.set_value("scenario_text", self._note)
        if sc.tab:
            dpg.set_value("gy_tabs", sc.tab)
        self.refresh()
        if sc.tab == "tab_allan":
            self._run_allan()
        self.playback.play()

    def _on_grade(self, *_a, **_k) -> None:
        if self._suppress:
            return
        key = GRADE_LABELS[dpg.get_value("grade")]
        if key is None:
            return
        self.params = params_for_grade(self._read_controls(), key)
        self._push_controls(self.params)
        self.refresh()
        if dpg.get_value("gy_tabs") == "tab_allan":
            self._run_allan()

    def _set_presenter(self, _s=None, app_data=None, _u=None) -> None:
        on = bool(app_data if app_data is not None else dpg.get_value("presenter_mode"))
        dpg.configure_item("advanced_controls", show=not on)
        dpg.configure_item("banner_panel", height=110 if on else 72)
        imu_style.apply_presenter(on)

    def _toggle_3d(self, _s=None, app_data=None, _u=None) -> None:
        want = bool(app_data if app_data is not None else dpg.get_value("show_3d"))
        self._cube_view.set_enabled(want)
        if want:
            self.playback.play()
        self.refresh()

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

    # --- time ------------------------------------------------------------------------
    def _on_time(self, i: int, t: float) -> None:
        if self._out is None:
            return
        th_true = float(self._out["angle_true_deg"][i])
        th_est = float(self._out["angle_est_deg"][i])
        err = float(self._out["angle_err_deg"][i])
        tag = "dial_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (DIAL_W, DIAL_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        dpg.draw_text((10, 8), "Heading (top view)", color=(220, 220, 230, 255), size=15, parent=tag)
        draw_dial(tag, (DIAL_W / 2, DIAL_H / 2 + 8), 105,
                  [(th_true, imu_style.rgba("truth"), "truth"), (th_est, imu_style.rgba("gyro"), "gyro")])
        dpg.draw_text((10, DIAL_H - 44), f"t = {t:6.2f} s", color=(200, 200, 210, 255), size=15, parent=tag)
        dpg.draw_text((10, DIAL_H - 24), f"error = {err:+.2f} deg",
                      color=rgba("error") if abs(err) > 1 else (160, 200, 160, 255), size=15, parent=tag)
        if self._cube_view.enabled:
            self._cube_view.update_gyro_compare(th_true, th_est, t_s=t, err_deg=err)

    # --- Allan ------------------------------------------------------------------------
    def _run_allan(self) -> None:
        try:
            p = self._read_controls()
        except ValueError:
            return
        record_s = float(dpg.get_value("allan_minutes")) * 60.0
        al = static_allan(p, record_s=record_s)
        taus, adev = al["taus"], al["adev"]
        dpg.set_value("allan_curve", _fxy(taus, adev * 3600.0))
        tr = al["terms"]
        ref_t = np.logspace(np.log10(taus[0]), np.log10(taus[-1]), 50)
        n, b, k = tr["N"], tr["B"], tr["K"]
        dpg.set_value("allan_n", _fxy(ref_t, (n / np.sqrt(ref_t) if np.isfinite(n) else ref_t * np.nan) * 3600.0))
        dpg.set_value("allan_b", _fxy(ref_t, np.full_like(ref_t, 0.664 * b) * 3600.0))
        dpg.set_value("allan_k", _fxy(ref_t, (k * np.sqrt(ref_t / 3.0) if np.isfinite(k) else ref_t * np.nan) * 3600.0))
        fit_axes("allan_x", "allan_y")
        ds = datasheet_units(p)

        def fmt(v: float, scale: float) -> str:
            return f"{v * scale:9.3f}" if np.isfinite(v) else "      n/a"

        dpg.set_value(
            "allan_text",
            (
                "Datasheet -> simulation -> Allan read-off\n\n"
                "term                     model      read-off\n"
                f"ARW N  (deg/sqrt(h))  {ds['arw_dpsh']:9.3f}  {fmt(n, 60.0)}\n"
                f"Bias instab. B (deg/h){ds['bi_dph']:9.3f}  {fmt(b, 3600.0)}\n"
                f"RRW K (deg/h/sqrt(h)) {ds['rrw_dphsh']:9.3f}  {fmt(k, 3600.0 * 60.0)}\n"
                f"Turn-on bias (deg/h)  {ds['bias_dph']:9.1f}   (invisible to Allan)\n\n"
                f"Record: {record_s / 60:.0f} min at 20 Hz; curve trusted to T/10.\n"
                "N: slope -1/2 line at tau = 1 s\n"
                "B: flat floor / 0.664\n"
                "K: slope +1/2 line at tau = 3 s"
            ),
        )

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
        dpg.set_value("rate_true", _fxy(t, out["rate_true_dps"]))
        dpg.set_value("rate_meas", _fxy(t, out["rate_meas_dps"]))
        dpg.set_value("ang_true", _fxy(t, out["angle_true_deg"]))
        dpg.set_value("ang_est", _fxy(t, out["angle_est_deg"]))
        dpg.set_value("ang_err", _fxy(t, out["angle_err_deg"]))
        env = out["arw_envelope_deg"]
        dpg.set_value("arw_hi", _fxy(t, env))
        dpg.set_value("arw_lo", _fxy(t, -env))

        show_mc = bool(dpg.get_value("show_mc"))
        stride = max(1, len(t) // 800)
        if show_mc:
            runs = monte_carlo_errors(p, n_runs=int(dpg.get_value("mc_runs")))
            sd = runs.std(axis=0)
            mu = runs.mean(axis=0)
            dpg.set_value("mc_band", [list(map(float, t[::stride])), list(map(float, (mu + 2 * sd)[::stride])),
                                      list(map(float, (mu - 2 * sd)[::stride]))])
            for k in range(MC_MAX):
                if k < runs.shape[0]:
                    dpg.set_value(f"mc_{k}", _fxy(t[::stride], runs[k, ::stride]))
                    dpg.configure_item(f"mc_{k}", show=True)
                else:
                    dpg.configure_item(f"mc_{k}", show=False)
            dpg.configure_item("mc_band", show=True)
        else:
            for k in range(MC_MAX):
                dpg.configure_item(f"mc_{k}", show=False)
            dpg.configure_item("mc_band", show=False)
        fit_axes("rate_t", "rate_y", "ang_t", "ang_y", "err_t", "err_y")

        self.playback.set_times(t)
        self.playback.set_cursor_span("ang_cursor", out["angle_true_deg"], out["angle_est_deg"])
        self.playback.set_cursor_span("err_cursor", out["angle_err_deg"])
        if not self.playback.playing:
            self.playback.seek(self.playback.t_view)

        if self._cube_view.last_error and dpg.does_item_exist("show_3d"):
            dpg.set_value("show_3d", False)
            self._cube_view.set_enabled(False)

        ds = datasheet_units(p)
        dpg.set_value(
            "status_text",
            (
                f"Final angle error: {out['final_err_deg']:+.2f} deg\n"
                f"Bias {p.bias_dps:+.3f} deg/s = {ds['bias_dph']:+.0f} deg/h"
                f"  ({'compensated' if p.compensate_bias else 'uncompensated'})\n"
                f"ARW {p.arw_deg_per_sqrt_s:.3f} deg/sqrt(s) = {ds['arw_dpsh']:.2f} deg/sqrt(h)\n"
                f"Bias instability {ds['bi_dph']:.2f} deg/h   RRW {ds['rrw_dphsh']:.2f} deg/h/sqrt(h)\n"
                f"Sample noise sigma: {out['sigma_rate_dps']:.3f} deg/s at {p.fs_hz:.0f} Hz"
                + (f"\n3D window: {self._cube_view.last_error}" if self._cube_view.last_error else "")
            ),
        )

    # --- layout ----------------------------------------------------------------------
    def _slider(self, tag: str) -> None:
        spec = next(s for s in SLIDERS if s[0] == tag)
        _t, label, attr, lo, hi, fmt = spec
        dpg.add_slider_float(tag=tag, label=label, default_value=float(getattr(self.params, attr)),
                             min_value=lo, max_value=hi, format=fmt, callback=self._on_change)

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Teaching Sims - Gyroscope", width=1520, height=990)
        imu_style.bind_base_theme()
        sc_mc = get_scenario(self.scenario_id).show_mc if self.scenario_id else False

        try:
            with dpg.window(tag="primary", label="Gyroscope"):
                with dpg.child_window(tag="banner_panel", height=72, border=True):
                    dpg.add_text(self._title, tag="banner_title")
                    dpg.add_text(self._note, tag="banner_body", wrap=1100)
                with dpg.group(horizontal=True):
                    with dpg.child_window(width=380, border=True):
                        dpg.add_checkbox(tag="presenter_mode", label="Presenter mode (hide advanced)",
                                         default_value=False, callback=self._set_presenter)
                        dpg.add_checkbox(tag="show_3d", label="Show 3D heading window (matplotlib)",
                                         default_value=False, callback=self._toggle_3d)
                        dpg.add_checkbox(tag="comp_bias", label="Compensate turn-on bias",
                                         default_value=self.params.compensate_bias, callback=self._on_change)
                        dpg.add_button(label="Resample noise", width=-1, callback=lambda: self._resample())
                        dpg.add_separator()
                        self.playback.build_controls("Playback (dial / 3D)")
                        dpg.add_separator()
                        dpg.add_combo(tag="profile", label="Motion", items=list(PROFILE_LABELS),
                                      default_value=LABEL_FOR_PROFILE[self.params.profile], callback=self._on_change)
                        dpg.add_combo(tag="grade", label="IMU grade", items=list(GRADE_LABELS),
                                      default_value="Custom", callback=self._on_grade)
                        for tag in ("rate", "bias", "arw", "bi"):
                            self._slider(tag)
                        dpg.add_checkbox(tag="show_mc", label="Monte Carlo ensemble", default_value=sc_mc,
                                         callback=self._on_change)
                        with dpg.group(tag="advanced_controls"):
                            dpg.add_separator()
                            dpg.add_text("Advanced")
                            for tag in ("rrw", "scale", "bi_tau", "sine_hz", "duration"):
                                self._slider(tag)
                            dpg.add_slider_int(tag="mc_runs", label="Ensemble runs", default_value=25,
                                               min_value=5, max_value=MC_MAX, callback=self._on_change)
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
                            dpg.add_drawlist(width=DIAL_W, height=DIAL_H, tag="dial_draw")
                            with dpg.plot(label="Integrated angle", height=DIAL_H, width=-1):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="ang_t")
                                with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="ang_y"):
                                    dpg.add_line_series([0.0], [0.0], label="true", tag="ang_true")
                                    dpg.add_line_series([0.0], [0.0], label="gyro integral", tag="ang_est")
                                    dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="ang_cursor")
                        with dpg.tab_bar(tag="gy_tabs"):
                            with dpg.tab(label="Angle error", tag="tab_err"):
                                with dpg.plot(height=-1, width=-1):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="err_t")
                                    with dpg.plot_axis(dpg.mvYAxis, label="deg (unwrapped)", tag="err_y"):
                                        dpg.add_shade_series([0.0], [0.0], y2=[0.0], label="ensemble +/-2 sigma",
                                                             tag="mc_band")
                                        for k in range(MC_MAX):
                                            dpg.add_line_series([0.0], [0.0], tag=f"mc_{k}", show=False)
                                        dpg.add_line_series([0.0], [0.0], label="+/- N sqrt(t) (ARW only)",
                                                            tag="arw_hi")
                                        dpg.add_line_series([0.0], [0.0], tag="arw_lo")
                                        dpg.add_line_series([0.0], [0.0], label="this run", tag="ang_err")
                                        dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="err_cursor")
                            with dpg.tab(label="Rate", tag="tab_rate"):
                                with dpg.plot(height=-1, width=-1):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="rate_t")
                                    with dpg.plot_axis(dpg.mvYAxis, label="deg/s", tag="rate_y"):
                                        dpg.add_line_series([0.0], [0.0], label="measured", tag="rate_meas")
                                        dpg.add_line_series([0.0], [0.0], label="true", tag="rate_true")
                            with dpg.tab(label="Allan deviation", tag="tab_allan"):
                                with dpg.group(horizontal=True):
                                    with dpg.child_window(width=430, border=True):
                                        dpg.add_slider_float(tag="allan_minutes", label="Static record (min)",
                                                             default_value=60.0, min_value=10.0, max_value=240.0,
                                                             format="%.0f")
                                        dpg.add_button(label="Record at rest and compute Allan deviation", width=-1,
                                                       callback=lambda: self._run_allan())
                                        dpg.add_separator()
                                        dpg.add_text("Press the button (or pick an IMU grade).", tag="allan_text")
                                    with dpg.plot(height=-1, width=-1):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, label="tau (s)", tag="allan_x",
                                                          scale=dpg.mvPlotScale_Log10)
                                        with dpg.plot_axis(dpg.mvYAxis, label="sigma_A (deg/h)", tag="allan_y",
                                                           scale=dpg.mvPlotScale_Log10):
                                            dpg.add_line_series([1.0], [1.0], label="Allan deviation",
                                                                tag="allan_curve")
                                            dpg.add_line_series([1.0], [1.0], label="N / sqrt(tau)", tag="allan_n")
                                            dpg.add_line_series([1.0], [1.0], label="0.664 B", tag="allan_b")
                                            dpg.add_line_series([1.0], [1.0], label="K sqrt(tau/3)", tag="allan_k")

            for tag, role in (("rate_true", "truth"), ("rate_meas", "measured"), ("ang_true", "truth"),
                              ("ang_est", "gyro"), ("ang_err", "error"), ("arw_hi", "reference"),
                              ("arw_lo", "reference"), ("allan_curve", "fused"), ("allan_n", "gyro"),
                              ("allan_b", "mag"), ("allan_k", "accel")):
                bind_role(tag, role, weight=1.3 if tag in ("rate_meas", "allan_n", "allan_b", "allan_k") else 2.0)
            bind_role("mc_band", "gyro", kind="shade", alpha=60)
            for k in range(MC_MAX):
                bind_role(f"mc_{k}", "gyro", weight=1.0, alpha=110)
            bind_role("ang_cursor", "cursor", weight=1.5)
            bind_role("err_cursor", "cursor", weight=1.5)

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("primary", True)
            self._push_controls(self.params)
            dpg.set_value("gy_tabs", self._tab)
            self.refresh()
            if self._tab == "tab_allan":
                self._run_allan()
            self.playback.play()
            while dpg.is_dearpygui_running():
                self.playback.tick()
                dpg.render_dearpygui_frame()
        finally:
            self._cube_view.close()
            dpg.destroy_context()
            imu_style.reset_bindings()


def run_app(scenario_id: str | None = None, params: GyroParams | None = None) -> None:
    if scenario_id and params is None:
        params = get_scenario(scenario_id).params
    GyroApp(initial=params, scenario_id=scenario_id).run()
