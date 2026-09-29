"""Dear PyGui demo: MEMS Coriolis vibratory gyroscope."""

from __future__ import annotations

import math
import time
from dataclasses import replace

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.topics.mems_gyro.physics import (
    MEMSGyroParams,
    RateProfile,
    envelope,
    process,
    rate_frequency_response,
)
from teaching_sims.topics.mems_gyro.scenarios import SCENARIOS, get_scenario
from teaching_sims.ui.desktop import imu_style
from teaching_sims.ui.desktop.imu_style import bind_role, draw_vector, rgba
from teaching_sims.ui.desktop.playback import Playback
from teaching_sims.ui.desktop.plot_utils import fit_axes, fxy as _fxy

DRAW_W, DRAW_H = 640, 340
VISUAL_HZ = 0.7  # stroboscopic drive frequency on screen

PROFILE_LABELS = {"Zero": RateProfile.ZERO, "Step": RateProfile.STEP, "Sine": RateProfile.SINE}
LABEL_FOR_PROFILE = {v: k for k, v in PROFILE_LABELS.items()}


class MEMSGyroApp:
    def __init__(self, initial: MEMSGyroParams | None = None, scenario_id: str | None = None) -> None:
        self.params = initial or MEMSGyroParams()
        self.scenario_id = scenario_id
        self._suppress = False
        self._out: dict[str, object] | None = None
        self._y_scale = 1.0
        self.playback = Playback("mg", on_time=self._on_time, speed=0.03, speed_range=(0.005, 0.3))
        if scenario_id:
            sc = get_scenario(scenario_id)
            self.params = sc.params
            self._title = sc.title
            self._note = f"{sc.teaching_point}\n{sc.notes}"
        else:
            self._title = "MEMS Coriolis vibratory gyroscope"
            self._note = "Drive the mass along x; rotation deflects it along y (Coriolis). Demodulate to get rate."

    # --- controls ---------------------------------------------------------------------
    def _read_controls(self) -> MEMSGyroParams:
        return replace(
            self.params,
            profile=PROFILE_LABELS[dpg.get_value("profile")],
            rate_dps=float(dpg.get_value("rate")),
            rate_hz=float(dpg.get_value("rate_hz")),
            sense_split_hz=float(dpg.get_value("split")),
            q_sense=float(dpg.get_value("q_sense")),
            quadrature_dps=float(dpg.get_value("quad")),
            demod_phase_err_deg=float(dpg.get_value("phase_err")),
            pickoff_noise_pm=float(dpg.get_value("noise_pm")),
            lpf_hz=float(dpg.get_value("lpf")),
            drive_amp_um=float(dpg.get_value("drive_amp")),
        )

    def _push_controls(self, p: MEMSGyroParams) -> None:
        self._suppress = True
        try:
            dpg.set_value("profile", LABEL_FOR_PROFILE[p.profile])
            dpg.set_value("rate", p.rate_dps)
            dpg.set_value("rate_hz", p.rate_hz)
            dpg.set_value("split", p.sense_split_hz)
            dpg.set_value("q_sense", p.q_sense)
            dpg.set_value("quad", p.quadrature_dps)
            dpg.set_value("phase_err", p.demod_phase_err_deg)
            dpg.set_value("noise_pm", p.pickoff_noise_pm)
            dpg.set_value("lpf", p.lpf_hz)
            dpg.set_value("drive_amp", p.drive_amp_um)
        finally:
            self._suppress = False

    def _apply_scenario(self, scenario_id: str) -> None:
        sc = get_scenario(scenario_id)
        self.scenario_id = scenario_id
        self.params = sc.params
        self._title = sc.title
        self._note = f"{sc.teaching_point}\n{sc.notes}"
        self._push_controls(self.params)
        dpg.set_value("banner_title", self._title)
        dpg.set_value("banner_body", self._note)
        dpg.set_value("scenario_text", self._note)
        self.refresh()
        self.playback.play()

    def _set_presenter(self, _s=None, app_data=None, _u=None) -> None:
        on = bool(app_data if app_data is not None else dpg.get_value("presenter_mode"))
        dpg.configure_item("advanced_controls", show=not on)
        dpg.configure_item("banner_panel", height=110 if on else 72)
        imu_style.apply_presenter(on)

    def _on_change(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self.playback.pause()
        self.refresh()

    # --- time / animation -------------------------------------------------------------
    def _amplitudes_at(self, i: int) -> tuple[float, float, float]:
        """(rate_true, rate_est, quad_est) at sample i."""
        o = self._out
        assert o is not None
        return (
            float(o["rate_true_dps"][i]),
            float(o["rate_est_dps"][i]),
            float(o["quad_channel_dps"][i]),
        )

    def _on_time(self, i: int, t: float) -> None:
        if self._out is None:
            return
        o = self._out
        fs = self.params.fs_hz
        n_cyc = int(round(2.0 * fs / self.params.drive_hz))
        a = max(0, i - n_cyc)
        b = min(len(o["t_s"]), a + 2 * n_cyc)
        dpg.set_value("liss", _fxy(o["x_um"][a:b], o["y_nm"][a:b]))
        dpg.set_value("scope_x", _fxy((o["t_s"][a:b] - t) * 1e3, o["x_um"][a:b] / max(self.params.drive_amp_um, 1e-9)))
        ymax = float(np.max(np.abs(o["y_nm"]))) or 1.0
        dpg.set_value("scope_y", _fxy((o["t_s"][a:b] - t) * 1e3, o["y_nm"][a:b] / ymax))
        fit_axes("liss_x", "liss_y")

    def _animate(self) -> None:
        if self._out is None:
            return
        i = self.playback.index
        rate_true, _rate_est, _q = self._amplitudes_at(i)
        o = self._out
        sens = float(o["sens_nm_per_dps"])
        phase = 2.0 * math.pi * VISUAL_HZ * time.monotonic()
        # Coriolis force is in phase with drive velocity (cos), quadrature with
        # displacement (sin); both then lag through the sense mode.
        lag = math.radians(float(o["sense_phase_deg"]))
        y_cor = -sens * rate_true * math.cos(phase + lag)
        y_quad = -sens * self.params.quadrature_dps * math.sin(phase + lag)
        self._draw_structure(math.sin(phase), (y_cor + y_quad) * self._y_scale, math.cos(phase), rate_true)

    # --- drawing ---------------------------------------------------------------------
    @staticmethod
    def _spring(parent: str, p0, p1, *, coils: int = 6, amp: float = 7.0, color=(150, 190, 240, 255)) -> None:
        x0, y0 = p0
        x1, y1 = p1
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        pts = [(x0, y0)]
        for k in range(1, 2 * coils):
            s = k / (2 * coils)
            side = amp if k % 2 else -amp
            pts.append((x0 + dx * s + nx * side, y0 + dy * s + ny * side))
        pts.append((x1, y1))
        dpg.draw_polyline(pts, color=color, thickness=2, parent=parent)

    def _draw_structure(self, x_norm: float, y_px: float, v_norm: float, rate_dps: float) -> None:
        tag = "gyro_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (DRAW_W, DRAW_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        cx, cy = DRAW_W * 0.5, DRAW_H * 0.55
        dx = 70.0 * x_norm
        y_px = float(np.clip(y_px, -42.0, 42.0))
        anchor = (80, 80, 92, 255)
        edge = (180, 180, 190, 255)

        # anchors + drive springs
        fw, fh = 190.0, 150.0
        for side in (-1, 1):
            ax = cx + side * 250
            dpg.draw_rectangle((ax - 16, cy - 40), (ax + 16, cy + 40), fill=anchor, color=edge, parent=tag)
            fx = cx + dx + side * fw / 2
            self._spring(tag, (ax - side * 16, cy - 25), (fx, cy - 25))
            self._spring(tag, (ax - side * 16, cy + 25), (fx, cy + 25))
        # drive frame
        dpg.draw_rectangle((cx + dx - fw / 2, cy - fh / 2), (cx + dx + fw / 2, cy + fh / 2),
                           color=(210, 210, 220, 255), thickness=3, parent=tag)
        # sense springs (frame -> mass)
        mw, mh = 90.0, 60.0
        mx, my = cx + dx, cy + y_px
        for side in (-1, 1):
            self._spring(tag, (mx - 25, cy + side * fh / 2), (mx - 25, my + side * mh / 2), coils=4, amp=5,
                         color=(120, 200, 170, 255))
            self._spring(tag, (mx + 25, cy + side * fh / 2), (mx + 25, my + side * mh / 2), coils=4, amp=5,
                         color=(120, 200, 170, 255))
        # proof mass
        dpg.draw_rectangle((mx - mw / 2, my - mh / 2), (mx + mw / 2, my + mh / 2), fill=(90, 140, 200, 255),
                           color=(230, 230, 240, 255), thickness=2, parent=tag)
        dpg.draw_text((mx - 38, my - 22), "PROOF MASS", size=12, color=(245, 245, 250, 255), parent=tag)
        # fixed sense electrodes (parallel plates) above / below
        for side in (-1, 1):
            yy = cy + side * (fh / 2 + 22)
            dpg.draw_rectangle((cx - 110, yy - 5), (cx + 110, yy + 5), fill=(200, 200, 210, 255), parent=tag)
        dpg.draw_text((cx + 118, cy - fh / 2 - 30), "sense electrode", size=12, color=(200, 200, 210, 255), parent=tag)

        # velocity and Coriolis force arrows
        draw_vector(tag, (mx, my + mh / 2 + 12), (60.0 * v_norm, 0.0), rgba("gyro"), label="v", size=13,
                    label_offset=(4, -8))
        f_y = -np.sign(rate_dps) * v_norm * min(1.0, abs(rate_dps) / 100.0) * 55.0
        if abs(rate_dps) > 1e-6:
            draw_vector(tag, (mx, my), (0.0, -f_y), rgba("fused"), label="F_coriolis", size=13,
                        label_offset=(6, -6))
        # rotation indicator
        dpg.draw_text((14, 10), f"Omega = {rate_dps:+.1f} deg/s about z (out of screen)", size=16,
                      color=(230, 230, 235, 255), parent=tag)
        dpg.draw_text((14, 32), "drive x (AGC), sense y: motion exaggerated, slow motion", size=13,
                      color=(160, 160, 170, 255), parent=tag)
        if abs(rate_dps) > 1e-6:
            r = 22
            c0 = (DRAW_W - 50, 40)
            pts = [(c0[0] + r * math.cos(a), c0[1] - np.sign(rate_dps) * r * math.sin(a)) for a in np.linspace(0.3, 5.5, 20)]
            dpg.draw_polyline(pts, color=rgba("cursor"), thickness=3, parent=tag)
            dpg.draw_arrow(pts[-1], pts[-3], color=rgba("cursor"), thickness=3, size=8, parent=tag)

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
        env = envelope(t, out["y_nm"])
        dpg.set_value("y_env", [list(map(float, env["t"])), list(map(float, env["hi"])), list(map(float, env["lo"]))])
        dpg.set_value("rate_true", _fxy(t[::20], out["rate_true_dps"][::20]))
        dpg.set_value("rate_est", _fxy(t[::20], out["rate_est_dps"][::20]))
        dpg.set_value("rate_quad", _fxy(t[::20], out["quad_channel_dps"][::20]))
        fit_axes("env_x", "env_y", "rate_x", "rate_y")

        f = np.logspace(-1, np.log10(p.drive_hz * 0.5), 400)
        g = np.abs(rate_frequency_response(p, f))
        dpg.set_value("resp", _fxy(f, np.maximum(g, 1e-4)))
        mark_f = p.rate_hz if p.profile == RateProfile.SINE else out["rate_bw_hz"]
        mark_g = float(np.abs(rate_frequency_response(p, np.array([mark_f])))[0])
        dpg.set_value("resp_mark", [[float(mark_f)], [max(mark_g, 1e-4)]])
        dpg.configure_item("resp_mark", label="input rate freq" if p.profile == RateProfile.SINE else "-3 dB")
        fit_axes("resp_x", "resp_y")

        self.playback.set_times(t)
        self.playback.set_cursor_span("rate_cursor", out["rate_true_dps"], out["rate_est_dps"], out["quad_channel_dps"])
        self.playback.set_cursor_span("env_cursor", env["lo"], env["hi"])

        # Pixel exaggeration for the sense axis, fixed per run
        peak_nm = out["sens_nm_per_dps"] * (max(abs(p.rate_dps), 1e-9) + p.quadrature_dps)
        self._y_scale = 40.0 / peak_nm if peak_nm > 0 else 1.0

        dpg.set_value(
            "status_text",
            (
                f"Sensitivity: {out['sens_nm_per_dps'] * 1e3:.1f} pm per deg/s\n"
                f"Rate bandwidth (-3 dB): {out['rate_bw_hz']:.1f} Hz\n"
                f"Sense-mode phase at drive: {out['sense_phase_deg']:.1f} deg\n"
                f"Output bias: {out['bias_dps']:+.2f} deg/s "
                f"(theory {out['expected_bias_dps']:+.2f})\n"
                f"Output noise (tail): {out['noise_dps']:.3f} deg/s rms"
            ),
        )

    # --- layout ----------------------------------------------------------------------
    def _slider(self, tag: str, label: str, value: float, lo: float, hi: float, fmt: str = "%.1f") -> None:
        dpg.add_slider_float(tag=tag, label=label, default_value=value, min_value=lo, max_value=hi,
                             format=fmt, callback=self._on_change)

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Teaching Sims - MEMS Coriolis Gyroscope", width=1520, height=980)
        imu_style.bind_base_theme()
        p = self.params
        try:
            with dpg.window(tag="primary", label="MEMS gyroscope"):
                with dpg.child_window(tag="banner_panel", height=72, border=True):
                    dpg.add_text(self._title, tag="banner_title")
                    dpg.add_text(self._note, tag="banner_body", wrap=1100)
                with dpg.group(horizontal=True):
                    with dpg.child_window(width=360, border=True):
                        dpg.add_checkbox(tag="presenter_mode", label="Presenter mode", default_value=False,
                                         callback=self._set_presenter)
                        dpg.add_separator()
                        self.playback.build_controls("Playback (simulation time)")
                        dpg.add_separator()
                        dpg.add_text("Rotation input")
                        dpg.add_combo(tag="profile", label="Profile", items=list(PROFILE_LABELS),
                                      default_value=LABEL_FOR_PROFILE[p.profile], callback=self._on_change)
                        self._slider("rate", "Rate (deg/s)", p.rate_dps, -300.0, 300.0)
                        self._slider("rate_hz", "Sine freq (Hz)", p.rate_hz, 1.0, 200.0)
                        dpg.add_separator()
                        dpg.add_text("Design")
                        self._slider("split", "Mode split (Hz)", p.sense_split_hz, 0.0, 800.0, "%.0f")
                        self._slider("q_sense", "Sense Q", p.q_sense, 5.0, 1000.0, "%.0f")
                        dpg.add_separator()
                        dpg.add_text("Imperfections")
                        self._slider("quad", "Quadrature (deg/s eq.)", p.quadrature_dps, 0.0, 500.0, "%.0f")
                        self._slider("phase_err", "Demod phase err (deg)", p.demod_phase_err_deg, -10.0, 10.0)
                        self._slider("noise_pm", "Pick-off noise (pm)", p.pickoff_noise_pm, 0.0, 100.0, "%.0f")
                        with dpg.group(tag="advanced_controls"):
                            dpg.add_separator()
                            dpg.add_text("Advanced")
                            self._slider("lpf", "Output LPF (Hz)", p.lpf_hz, 5.0, 1000.0, "%.0f")
                            self._slider("drive_amp", "Drive amp (um)", p.drive_amp_um, 1.0, 10.0)
                        dpg.add_separator()
                        dpg.add_text("Lecture scenarios")
                        for sid, sc in SCENARIOS.items():
                            dpg.add_button(label=sc.title, width=-1, user_data=sid,
                                           callback=lambda s, a, u: self._apply_scenario(u))
                        dpg.add_separator()
                        dpg.add_text(self._note, tag="scenario_text", wrap=330)
                        dpg.add_separator()
                        dpg.add_text("", tag="status_text", wrap=330)

                    with dpg.child_window(border=False):
                        with dpg.group(horizontal=True):
                            dpg.add_drawlist(width=DRAW_W, height=DRAW_H, tag="gyro_draw")
                            with dpg.group():
                                with dpg.plot(label="Mass path: x vs y (2 drive cycles)", height=DRAW_H // 2 + 20,
                                              width=-1):
                                    dpg.add_plot_axis(dpg.mvXAxis, label="x (um)", tag="liss_x")
                                    with dpg.plot_axis(dpg.mvYAxis, label="y (nm)", tag="liss_y"):
                                        dpg.add_line_series([0.0], [0.0], tag="liss")
                                with dpg.plot(label="Drive x vs sense y (normalised)", height=DRAW_H // 2 - 28,
                                              width=-1):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label="t - t_view (ms)", tag="scope_t")
                                    with dpg.plot_axis(dpg.mvYAxis, tag="scope_yax"):
                                        dpg.add_line_series([0.0], [0.0], label="x drive", tag="scope_x")
                                        dpg.add_line_series([0.0], [0.0], label="y sense", tag="scope_y")
                                    dpg.set_axis_limits("scope_yax", -1.15, 1.15)
                        with dpg.plot(label="Rate: true vs demodulated output", height=250, width=-1):
                            dpg.add_plot_legend()
                            dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="rate_x")
                            with dpg.plot_axis(dpg.mvYAxis, label="deg/s", tag="rate_y"):
                                dpg.add_line_series([0.0], [0.0], label="true rate", tag="rate_true")
                                dpg.add_line_series([0.0], [0.0], label="rate output (I)", tag="rate_est")
                                dpg.add_line_series([0.0], [0.0], label="quadrature channel (Q)", tag="rate_quad")
                                dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="rate_cursor")
                        with dpg.group(horizontal=True):
                            with dpg.plot(label="Sense displacement y (carrier envelope)", height=-1, width=620):
                                dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="env_x")
                                with dpg.plot_axis(dpg.mvYAxis, label="nm", tag="env_y"):
                                    dpg.add_shade_series([0.0], [0.0], y2=[0.0], tag="y_env")
                                    dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="env_cursor")
                            with dpg.plot(label="Rate response |output / input|", height=-1, width=-1):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="rate frequency (Hz)", tag="resp_x",
                                                  scale=dpg.mvPlotScale_Log10)
                                with dpg.plot_axis(dpg.mvYAxis, tag="resp_y", scale=dpg.mvPlotScale_Log10):
                                    dpg.add_line_series([1.0], [1.0], label="|G|", tag="resp")
                                    dpg.add_scatter_series([1.0], [1.0], label="-3 dB", tag="resp_mark")

            for tag, role in (("liss", "fused"), ("scope_x", "gyro"), ("scope_y", "fused"), ("rate_true", "truth"),
                              ("rate_est", "fused"), ("rate_quad", "mag"), ("resp", "gyro")):
                bind_role(tag, role)
            bind_role("y_env", "fused", kind="shade", alpha=140)
            bind_role("rate_cursor", "cursor", weight=1.5)
            bind_role("env_cursor", "cursor", weight=1.5)
            bind_role("resp_mark", "cursor", kind="scatter", weight=4.0)

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("primary", True)
            self._push_controls(self.params)
            self.refresh()
            self.playback.play()
            while dpg.is_dearpygui_running():
                self.playback.tick()
                self._animate()
                dpg.render_dearpygui_frame()
        finally:
            dpg.destroy_context()
            imu_style.reset_bindings()


def run_app(scenario_id: str | None = None, params: MEMSGyroParams | None = None) -> None:
    if scenario_id and params is None:
        params = get_scenario(scenario_id).params
    MEMSGyroApp(initial=params, scenario_id=scenario_id).run()
