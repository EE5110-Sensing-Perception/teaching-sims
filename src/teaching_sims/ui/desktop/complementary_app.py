"""Dear PyGui desktop app: attitude fusion (complementary, Kalman, Mahony)."""

from __future__ import annotations

from dataclasses import replace

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.core.imu import DEG2RAD
from teaching_sims.topics.attitude.physics import euler_zyx_to_dcm
from teaching_sims.topics.complementary.mahony import MahonyParams, simulate_mahony
from teaching_sims.topics.complementary.physics import (
    ComplementaryParams,
    PitchMotion,
    process,
    transfer_functions,
)
from teaching_sims.topics.complementary.scenarios import MODE_1DOF, MODE_3D, SCENARIOS, get_scenario
from teaching_sims.ui.desktop import imu_style
from teaching_sims.ui.desktop.imu_style import OrthoCamera, bind_role, draw_body_box, rgba
from teaching_sims.ui.desktop.playback import Playback
from teaching_sims.ui.desktop.plot_utils import fit_axes, fxy as _fxy

MODES = (MODE_1DOF, MODE_3D)
MOTION_LABELS = {"Sine": PitchMotion.SINE, "Ramp": PitchMotion.RAMP, "Step": PitchMotion.STEP}
LABEL_FOR_MOTION = {v: k for k, v in MOTION_LABELS.items()}
BLOCK_W, BLOCK_H = 600, 250
HOR = 250
VIEW3D_W, VIEW3D_H = 460, 330

# 1-DOF sliders: (tag, label, attribute, lo, hi, format)
CF_MAIN = (
    ("alpha", "alpha (gyro weight)", "alpha", 0.5, 0.999, "%.3f"),
    ("amp", "Motion amp (deg)", "amp_deg", 0.0, 60.0, "%.1f"),
    ("gyro_bias", "Gyro bias (deg/s)", "gyro_bias_dps", -2.0, 2.0, "%.2f"),
    ("surge", "Surge (m/s^2)", "surge_mps2", -6.0, 6.0, "%.2f"),
    ("kf_r", "KF R: accel tilt std (deg)", "kf_r_deg", 0.2, 20.0, "%.1f"),
)
CF_ADV = (
    ("sine_hz", "Sine Hz", "sine_hz", 0.02, 2.0, "%.2f"),
    ("gyro_noise", "Gyro noise (deg/s)", "gyro_noise_dps", 0.0, 2.0, "%.2f"),
    ("accel_noise", "Accel noise (m/s^2)", "accel_noise_mps2", 0.0, 1.0, "%.2f"),
    ("surge_start", "Surge start (s)", "surge_start_s", 0.0, 30.0, "%.1f"),
    ("surge_dur", "Surge duration (s, 0=all)", "surge_dur_s", 0.0, 30.0, "%.1f"),
    ("gate_thr", "Gate threshold (m/s^2)", "gate_threshold_mps2", 0.05, 2.0, "%.2f"),
    ("kf_q", "KF Q: bias walk (deg/s/sqrt(s))", "kf_q_bias_dps_rts", 0.0, 0.2, "%.3f"),
    ("duration", "Duration (s)", "duration_s", 4.0, 60.0, "%.0f"),
)
MH_MAIN = (
    ("mh_kp", "Kp", "kp", 0.0, 5.0, "%.2f"),
    ("mh_ki", "Ki", "ki", 0.0, 0.5, "%.3f"),
    ("mh_bz", "Gyro bias z (deg/s)", "bias_z_dps", -2.0, 2.0, "%.2f"),
    ("mh_surge", "Surge (m/s^2)", "surge_mps2", -6.0, 6.0, "%.2f"),
)
MH_ADV = (
    ("mh_bx", "Gyro bias x (deg/s)", "bias_x_dps", -2.0, 2.0, "%.2f"),
    ("mh_by", "Gyro bias y (deg/s)", "bias_y_dps", -2.0, 2.0, "%.2f"),
    ("mh_yawrate", "Yaw rate (deg/s)", "yaw_rate_dps", -30.0, 30.0, "%.1f"),
    ("mh_dur", "Duration (s)", "duration_s", 20.0, 180.0, "%.0f"),
)


class ComplementaryApp:
    def __init__(self, initial: ComplementaryParams | None = None, scenario_id: str | None = None) -> None:
        self.params = initial or ComplementaryParams()
        self.mparams = MahonyParams()
        self.scenario_id = scenario_id
        self._mode = MODES[0]
        self._seed = self.params.seed
        self._suppress = False
        self._out: dict | None = None
        self._mout: dict | None = None
        self.playback = Playback("cf", on_time=self._on_time, speed=1.0, speed_range=(0.1, 10.0))
        self.cam = OrthoCamera(origin=(VIEW3D_W * 0.5, VIEW3D_H * 0.47), scale=85.0)
        if scenario_id:
            sc = get_scenario(scenario_id)
            self._load_scenario_fields(sc)
        else:
            self._title = "Attitude fusion: complementary, Kalman, Mahony"
            self._note = "Fuse gyro (fast, drifts) with accelerometer (absolute, noisy, spoofed by acceleration)."

    def _load_scenario_fields(self, sc) -> None:
        self._mode = sc.mode
        if sc.params is not None:
            self.params = sc.params
        if sc.mparams is not None:
            self.mparams = sc.mparams
        self._title = sc.title
        self._note = f"{sc.teaching_point}\n{sc.notes}"

    # --- controls ---------------------------------------------------------------------
    def _read_controls(self) -> None:
        kw = {attr: float(dpg.get_value(tag)) for tag, _l, attr, *_ in CF_MAIN + CF_ADV}
        self.params = replace(
            self.params, **kw, motion=MOTION_LABELS[dpg.get_value("motion")],
            gate_accel=bool(dpg.get_value("gate")), seed=self._seed,
        )
        mkw = {attr: float(dpg.get_value(tag)) for tag, _l, attr, *_ in MH_MAIN + MH_ADV}
        self.mparams = replace(
            self.mparams, **mkw, use_mag=bool(dpg.get_value("mh_mag")), gate_accel=bool(dpg.get_value("gate")),
            seed=self._seed,
        )

    def _push_controls(self) -> None:
        self._suppress = True
        try:
            dpg.set_value("mode", self._mode)
            for tag, _l, attr, *_ in CF_MAIN + CF_ADV:
                dpg.set_value(tag, float(getattr(self.params, attr)))
            for tag, _l, attr, *_ in MH_MAIN + MH_ADV:
                dpg.set_value(tag, float(getattr(self.mparams, attr)))
            dpg.set_value("motion", LABEL_FOR_MOTION[self.params.motion])
            dpg.set_value("gate", self.params.gate_accel if self._mode == MODES[0] else self.mparams.gate_accel)
            dpg.set_value("mh_mag", self.mparams.use_mag)
        finally:
            self._suppress = False

    def _apply_scenario(self, scenario_id: str) -> None:
        sc = get_scenario(scenario_id)
        self.scenario_id = scenario_id
        self._load_scenario_fields(sc)
        self._push_controls()
        dpg.set_value("banner_title", self._title)
        dpg.set_value("banner_body", self._note)
        dpg.set_value("scenario_text", self._note)
        self._sync_mode()
        self.refresh()
        self.playback.play()

    def _sync_mode(self) -> None:
        one = self._mode == MODES[0]
        for tag in ("cf_group", "view_1dof"):
            dpg.configure_item(tag, show=one)
        for tag in ("mh_group", "view_3d"):
            dpg.configure_item(tag, show=not one)

    def _on_mode(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self._mode = str(dpg.get_value("mode"))
        self._sync_mode()
        self.refresh()
        self.playback.play()

    def _set_presenter(self, _s=None, app_data=None, _u=None) -> None:
        on = bool(app_data if app_data is not None else dpg.get_value("presenter_mode"))
        for tag in ("cf_adv", "mh_adv"):
            dpg.configure_item(tag, show=not on)
        dpg.configure_item("banner_panel", height=110 if on else 72)
        imu_style.apply_presenter(on)

    def _resample(self) -> None:
        self._seed += 1
        self.refresh()

    def _on_change(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self.playback.pause()
        self.refresh()

    # --- drawing: block diagram and horizon ----------------------------------------------
    def _box(self, tag: str, p0, p1, text: str, col=(200, 200, 210, 255), sub: str = "") -> None:
        dpg.draw_rectangle(p0, p1, color=col, fill=(40, 44, 54, 255), thickness=2, parent=tag)
        dpg.draw_text((p0[0] + 8, p0[1] + 6), text, color=col, size=14, parent=tag)
        if sub:
            dpg.draw_text((p0[0] + 8, p0[1] + 24), sub, color=(170, 170, 180, 255), size=12, parent=tag)

    def _draw_block(self, accel_on: bool) -> None:
        tag = "block_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (BLOCK_W, BLOCK_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        p, o = self.params, self._out
        g, a, f = rgba("gyro"), rgba("accel"), rgba("fused")
        dpg.draw_text((10, 8), "Complementary filter = high-pass(gyro angle) + low-pass(accel angle)",
                      color=(220, 220, 230, 255), size=14, parent=tag)
        y1, y2 = 44, 132
        self._box(tag, (10, y1), (110, y1 + 50), "gyro w", g)
        self._box(tag, (150, y1), (250, y1 + 50), "integrate", g, "sum w dt")
        self._box(tag, (290, y1), (430, y1 + 50), "high-pass", g, "a(1-z^-1)/(1-a z^-1)")
        self._box(tag, (10, y2), (110, y2 + 50), "accel f", a)
        self._box(tag, (150, y2), (250, y2 + 50), "atan2", a, "tilt from g")
        self._box(tag, (290, y2), (430, y2 + 50), "low-pass", a, "(1-a)/(1-a z^-1)")
        for yy, col in ((y1 + 25, g), (y2 + 25, a)):
            dpg.draw_arrow((150, yy), (110, yy), color=col, thickness=2, size=7, parent=tag)
            dpg.draw_arrow((290, yy), (250, yy), color=col, thickness=2, size=7, parent=tag)
        # gate switch on the accel path
        if p.gate_accel:
            if accel_on:
                dpg.draw_line((250, y2 + 25), (290, y2 + 25), color=a, thickness=2, parent=tag)
            else:
                dpg.draw_line((255, y2 + 25), (282, y2 + 8), color=rgba("error"), thickness=3, parent=tag)
                dpg.draw_text((238, y2 + 56), "GATED: |f| != g", color=rgba("error"), size=13, parent=tag)
        cx, cy = 490, (y1 + y2) / 2 + 25
        dpg.draw_circle((cx, cy), 18, color=f, thickness=2, parent=tag)
        dpg.draw_text((cx - 6, cy - 10), "+", color=f, size=20, parent=tag)
        dpg.draw_arrow((cx - 18, cy - 6), (430, y1 + 25), color=g, thickness=2, size=7, parent=tag)
        dpg.draw_arrow((cx - 18, cy + 6), (430, y2 + 25), color=a, thickness=2, size=7, parent=tag)
        dpg.draw_arrow((BLOCK_W - 20, cy), (cx + 18, cy), color=f, thickness=3, size=9, parent=tag)
        dpg.draw_text((BLOCK_W - 60, cy - 26), "theta", color=f, size=14, parent=tag)
        if o is not None:
            tau = o["tau_s"]
            dpg.draw_text((10, BLOCK_H - 44),
                          f"alpha = {p.alpha:.3f}   tau = a dt/(1-a) = {tau:.2f} s   f_c = {o['fc_hz']:.3f} Hz",
                          color=(230, 230, 235, 255), size=14, parent=tag)
            dpg.draw_text((10, BLOCK_H - 24),
                          f"KF steady state: K = {o['kf_gain_ss']:.4f} -> alpha_eq = {o['kf_alpha_eq']:.3f}, "
                          f"tau_eq = {o['kf_tau_eq_s']:.2f} s", color=rgba("kalman"), size=14, parent=tag)

    def _draw_horizon(self, true_deg: float, cf_deg: float, kf_deg: float) -> None:
        tag = "horizon_draw"
        dpg.delete_item(tag, children_only=True)
        c = HOR / 2
        k = 3.0  # px per degree
        dpg.draw_rectangle((0, 0), (HOR, HOR), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        y_h = c + true_deg * k  # nose up -> horizon moves down
        dpg.draw_rectangle((10, 10), (HOR - 10, min(max(y_h, 10), HOR - 10)), fill=(40, 80, 130, 255),
                           color=(0, 0, 0, 0), parent=tag)
        dpg.draw_rectangle((10, min(max(y_h, 10), HOR - 10)), (HOR - 10, HOR - 10), fill=(110, 80, 50, 255),
                           color=(0, 0, 0, 0), parent=tag)
        for val, col, lab in ((cf_deg, rgba("fused"), "CF"), (kf_deg, rgba("kalman"), "KF")):
            yy = c + val * k  # where the filter believes the horizon is
            dpg.draw_line((30, yy), (HOR - 30, yy), color=col, thickness=3, parent=tag)
            dpg.draw_text((HOR - 28, yy - 8), lab, color=col, size=13, parent=tag)
        dpg.draw_line((c - 40, c), (c - 12, c), color=(250, 220, 90, 255), thickness=4, parent=tag)
        dpg.draw_line((c + 12, c), (c + 40, c), color=(250, 220, 90, 255), thickness=4, parent=tag)
        dpg.draw_circle((c, c), 3, color=(250, 220, 90, 255), fill=(250, 220, 90, 255), parent=tag)
        dpg.draw_text((12, 12), f"pitch {true_deg:+.1f}", color=(240, 240, 245, 255), size=14, parent=tag)

    def _draw_3d(self, i: int) -> None:
        tag = "view3d_draw"
        dpg.delete_item(tag, children_only=True)
        dpg.draw_rectangle((0, 0), (VIEW3D_W, VIEW3D_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        o = self._mout
        if o is None:
            return
        cam = self.cam
        for kk in np.linspace(-1.4, 1.4, 5):
            dpg.draw_line(cam.project([kk, -1.4, 0]), cam.project([kk, 1.4, 0]), color=(55, 58, 68, 255), parent=tag)
            dpg.draw_line(cam.project([-1.4, kk, 0]), cam.project([1.4, kk, 0]), color=(55, 58, 68, 255), parent=tag)
        for kk, lab in enumerate("NED"):
            tip = np.eye(3)[kk] * 1.6
            dpg.draw_arrow(cam.project(tip), cam.project([0, 0, 0]), color=(170, 170, 180, 255), thickness=2, size=8,
                           parent=tag)
            px, py = cam.project(tip * 1.1)
            dpg.draw_text((px - 5, py - 9), lab, color=(170, 170, 180, 255), size=15, parent=tag)
        draw_body_box(tag, cam, o["r_true"][i], wire_only=True)
        y, p_, r = o["euler_est_deg"][i] * DEG2RAD
        draw_body_box(tag, cam, euler_zyx_to_dcm(y, p_, r))
        err = o["euler_err_deg"][i]
        dpg.draw_text((10, 8), "estimate (solid) vs truth (ghost)", color=(220, 220, 230, 255), size=14, parent=tag)
        dpg.draw_text((10, VIEW3D_H - 24), f"err yaw {err[0]:+.1f}  pitch {err[1]:+.1f}  roll {err[2]:+.1f} deg",
                      color=rgba("error") if abs(err[0]) > 5 else (160, 200, 160, 255), size=14, parent=tag)

    # --- time ------------------------------------------------------------------------
    def _on_time(self, i: int, _t: float) -> None:
        if self._mode == MODES[0] and self._out is not None:
            o = self._out
            self._draw_horizon(float(o["pitch_true_deg"][i]), float(o["comp_deg"][i]), float(o["kf_deg"][i]))
            self._draw_block(bool(o["accel_used"][i]))
        elif self._mout is not None:
            self._draw_3d(i)

    # --- refresh ---------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            self._read_controls()
        except ValueError as exc:
            dpg.set_value("status_text", f"Invalid settings: {exc}")
            return
        if self._mode == MODES[0]:
            self._refresh_1dof()
        else:
            self._refresh_3d()

    def _refresh_1dof(self) -> None:
        p = self.params
        out = process(p)
        self._out = out
        t = out["t_s"]
        dpg.set_value("true_series", _fxy(t, out["pitch_true_deg"]))
        dpg.set_value("gyro_series", _fxy(t, out["gyro_only_deg"]))
        dpg.set_value("accel_series", _fxy(t, out["accel_tilt_deg"]))
        dpg.set_value("comp_series", _fxy(t, out["comp_deg"]))
        dpg.set_value("kf_series", _fxy(t, out["kf_deg"]))
        s = 2.0 * out["kf_sigma_deg"]
        dpg.set_value("kf_band", [list(map(float, t)), list(map(float, out["kf_deg"] + s)),
                                  list(map(float, out["kf_deg"] - s))])
        for tag, key in (("err_gyro", "err_gyro_deg"), ("err_accel", "err_accel_deg"), ("err_comp", "err_comp_deg"),
                         ("err_kf", "err_kf_deg")):
            dpg.set_value(tag, _fxy(t, out[key]))
        dpg.set_value("bias_true", [[0.0, float(t[-1])], [p.gyro_bias_dps, p.gyro_bias_dps]])
        dpg.set_value("bias_kf", _fxy(t, out["kf_bias_dps"]))
        sb = 2.0 * out["kf_bias_sigma_dps"]
        dpg.set_value("bias_band", [list(map(float, t)), list(map(float, out["kf_bias_dps"] + sb)),
                                    list(map(float, out["kf_bias_dps"] - sb))])
        gated = np.where(out["accel_used"], np.nan, 0.0)
        dpg.set_value("surge_series", _fxy(t, out["surge_mps2"]))
        dpg.set_value("gated_series", _fxy(t, np.nan_to_num(gated, nan=-1e9)))
        fit_axes("pitch_t", "pitch_y", "err_t", "bias_t", "bias_y")
        # scale the error axis to the fused estimates; gyro-only drift runs off the top
        fused = np.concatenate([out["err_comp_deg"], out["err_kf_deg"]])
        lim = max(3.0, 1.3 * float(np.percentile(np.abs(fused), 99.5)))
        dpg.set_axis_limits("err_y", -lim, lim)

        f = np.logspace(-3, np.log10(0.5 * p.fs_hz), 400)
        tf = transfer_functions(p.alpha, p.dt, f)
        dpg.set_value("bode_lp", _fxy(f, np.maximum(tf["lowpass"], 1e-4)))
        dpg.set_value("bode_hp", _fxy(f, np.maximum(tf["highpass"], 1e-4)))
        fc = out["fc_hz"]
        dpg.set_value("bode_fc", [[fc, fc], [1e-4, 2.0]])
        if p.motion == PitchMotion.SINE:
            dpg.set_value("bode_motion", [[p.sine_hz, p.sine_hz], [1e-4, 2.0]])
        dpg.configure_item("bode_motion", show=p.motion == PitchMotion.SINE)
        fit_axes("bode_x", "bode_y")

        self.playback.set_times(t)
        self.playback.set_cursor_span("pitch_cursor", out["pitch_true_deg"], out["comp_deg"])
        self.playback.set_cursor_span("err_cursor", out["err_comp_deg"], out["err_kf_deg"])
        self._on_time(self.playback.index, self.playback.t_view)
        dpg.set_value(
            "status_text",
            (
                f"RMS error (deg)\n  gyro only {out['rms_gyro_deg']:6.2f}\n  accel     {out['rms_accel_deg']:6.2f}\n"
                f"  CF        {out['rms_comp_deg']:6.2f}\n  KF        {out['rms_kf_deg']:6.2f}\n"
                f"CF tau {out['tau_s']:.2f} s, f_c {out['fc_hz']:.3f} Hz\n"
                f"KF bias estimate {out['kf_bias_final_dps']:+.3f} deg/s (true {p.gyro_bias_dps:+.3f})\n"
                f"Accel gated {100 * out['gated_fraction']:.0f}% of samples"
            ),
        )

    def _refresh_3d(self) -> None:
        m = self.mparams
        o = simulate_mahony(m)
        self._mout = o
        t = o["t_s"]
        names = ("yaw", "pitch", "roll")
        for k, nm in enumerate(names):
            dpg.set_value(f"mh_true_{nm}", _fxy(t, o["euler_true_deg"][:, k]))
            dpg.set_value(f"mh_est_{nm}", _fxy(t, o["euler_est_deg"][:, k]))
            dpg.set_value(f"mh_err_{nm}", _fxy(t, o["euler_err_deg"][:, k]))
        for k, ax in enumerate("xyz"):
            dpg.set_value(f"mh_b_{ax}", _fxy(t, o["bias_est_dps"][:, k]))
            dpg.set_value(f"mh_bt_{ax}", [[0.0, float(t[-1])], [float(o["bias_true_dps"][k])] * 2])
        fit_axes("mh_eul_t", "mh_eul_y", "mh_err_t", "mh_err_y", "mhb_t", "mhb_y")
        self.playback.set_times(t)
        self.playback.set_cursor_span("mh_err_cursor", o["euler_err_deg"])
        self._on_time(self.playback.index, self.playback.t_view)
        rt = o["rms_tail_deg"]
        be = o["bias_est_dps"][-1]
        bt = o["bias_true_dps"]
        dpg.set_value(
            "status_text",
            (
                f"Magnetometer: {'ON' if m.use_mag else 'OFF'}   Kp {m.kp:.2f}  Ki {m.ki:.3f}\n"
                f"RMS error, last 25% (deg):\n  yaw {rt[0]:6.2f}  pitch {rt[1]:5.2f}  roll {rt[2]:5.2f}\n"
                f"Bias estimate vs true (deg/s):\n"
                f"  x {be[0]:+.2f}/{bt[0]:+.2f}  y {be[1]:+.2f}/{bt[1]:+.2f}  z {be[2]:+.2f}/{bt[2]:+.2f}\n"
                + ("Yaw and z-bias are unobservable from gravity alone." if not m.use_mag else "")
            ),
        )

    # --- layout ----------------------------------------------------------------------
    def _slider(self, spec, obj) -> None:
        tag, label, attr, lo, hi, fmt = spec
        dpg.add_slider_float(tag=tag, label=label, default_value=float(getattr(obj, attr)), min_value=lo,
                             max_value=hi, format=fmt, callback=self._on_change)

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Teaching Sims - Attitude Fusion", width=1540, height=990)
        imu_style.bind_base_theme()
        try:
            with dpg.window(tag="primary", label="Attitude fusion"):
                with dpg.child_window(tag="banner_panel", height=72, border=True):
                    dpg.add_text(self._title, tag="banner_title")
                    dpg.add_text(self._note, tag="banner_body", wrap=1100)
                with dpg.group(horizontal=True):
                    with dpg.child_window(width=380, border=True):
                        dpg.add_checkbox(tag="presenter_mode", label="Presenter mode", default_value=False,
                                         callback=self._set_presenter)
                        dpg.add_combo(tag="mode", label="Mode", items=list(MODES), default_value=self._mode,
                                      callback=self._on_mode)
                        dpg.add_checkbox(tag="gate", label="Gate accel when |f| != g", default_value=False,
                                         callback=self._on_change)
                        dpg.add_button(label="Resample noise", width=-1, callback=lambda: self._resample())
                        dpg.add_separator()
                        self.playback.build_controls()
                        dpg.add_separator()
                        with dpg.group(tag="cf_group"):
                            dpg.add_combo(tag="motion", label="Pitch motion", items=list(MOTION_LABELS),
                                          default_value=LABEL_FOR_MOTION[self.params.motion], callback=self._on_change)
                            for spec in CF_MAIN:
                                self._slider(spec, self.params)
                            with dpg.group(tag="cf_adv"):
                                dpg.add_text("Advanced")
                                for spec in CF_ADV:
                                    self._slider(spec, self.params)
                        with dpg.group(tag="mh_group"):
                            dpg.add_checkbox(tag="mh_mag", label="Use magnetometer", default_value=False,
                                             callback=self._on_change)
                            for spec in MH_MAIN:
                                self._slider(spec, self.mparams)
                            with dpg.group(tag="mh_adv"):
                                dpg.add_text("Advanced")
                                for spec in MH_ADV:
                                    self._slider(spec, self.mparams)
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
                        with dpg.group(tag="view_1dof"):
                            with dpg.group(horizontal=True):
                                dpg.add_drawlist(width=BLOCK_W, height=BLOCK_H, tag="block_draw")
                                dpg.add_drawlist(width=HOR, height=HOR, tag="horizon_draw")
                                with dpg.plot(label="Filter split (Bode magnitude)", height=BLOCK_H, width=-1):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label="f (Hz)", tag="bode_x",
                                                      scale=dpg.mvPlotScale_Log10)
                                    with dpg.plot_axis(dpg.mvYAxis, tag="bode_y", scale=dpg.mvPlotScale_Log10):
                                        dpg.add_line_series([1.0], [1.0], label="accel: low-pass", tag="bode_lp")
                                        dpg.add_line_series([1.0], [1.0], label="gyro: high-pass", tag="bode_hp")
                                        dpg.add_line_series([1.0], [1.0], label="f_c", tag="bode_fc")
                                        dpg.add_line_series([1.0], [1.0], label="motion", tag="bode_motion")
                            with dpg.plot(label="Pitch estimates", height=300, width=-1):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="pitch_t")
                                with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="pitch_y"):
                                    dpg.add_shade_series([0.0], [0.0], y2=[0.0], label="KF +/-2 sigma", tag="kf_band")
                                    dpg.add_line_series([0.0], [0.0], label="accel tilt", tag="accel_series")
                                    dpg.add_line_series([0.0], [0.0], label="gyro only", tag="gyro_series")
                                    dpg.add_line_series([0.0], [0.0], label="true", tag="true_series")
                                    dpg.add_line_series([0.0], [0.0], label="complementary", tag="comp_series")
                                    dpg.add_line_series([0.0], [0.0], label="Kalman", tag="kf_series")
                                    dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="pitch_cursor")
                            with dpg.tab_bar():
                                with dpg.tab(label="Errors"):
                                    with dpg.plot(height=-1, width=-1):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="err_t")
                                        with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="err_y"):
                                            dpg.add_line_series([0.0], [0.0], label="accel", tag="err_accel")
                                            dpg.add_line_series([0.0], [0.0], label="gyro only", tag="err_gyro")
                                            dpg.add_line_series([0.0], [0.0], label="CF", tag="err_comp")
                                            dpg.add_line_series([0.0], [0.0], label="KF", tag="err_kf")
                                            dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="err_cursor")
                                with dpg.tab(label="KF bias estimate"):
                                    with dpg.plot(height=-1, width=-1):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="bias_t")
                                        with dpg.plot_axis(dpg.mvYAxis, label="deg/s", tag="bias_y"):
                                            dpg.add_shade_series([0.0], [0.0], y2=[0.0], label="+/-2 sigma",
                                                                 tag="bias_band")
                                            dpg.add_line_series([0.0], [0.0], label="true bias", tag="bias_true")
                                            dpg.add_line_series([0.0], [0.0], label="KF estimate", tag="bias_kf")
                                with dpg.tab(label="Surge and gating"):
                                    with dpg.plot(height=-1, width=-1):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="surge_t")
                                        with dpg.plot_axis(dpg.mvYAxis, label="m/s^2", tag="surge_y"):
                                            dpg.add_line_series([0.0], [0.0], label="surge", tag="surge_series")
                                            dpg.add_scatter_series([0.0], [0.0], label="accel gated",
                                                                   tag="gated_series")
                                        dpg.set_axis_limits("surge_y", -6.5, 6.5)
                        with dpg.group(tag="view_3d"):
                            with dpg.group(horizontal=True):
                                dpg.add_drawlist(width=VIEW3D_W, height=VIEW3D_H, tag="view3d_draw")
                                with dpg.plot(label="Euler angles: truth vs Mahony", height=VIEW3D_H, width=-1):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="mh_eul_t")
                                    with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="mh_eul_y"):
                                        for nm in ("yaw", "pitch", "roll"):
                                            dpg.add_line_series([0.0], [0.0], label=f"{nm} true", tag=f"mh_true_{nm}")
                                            dpg.add_line_series([0.0], [0.0], label=f"{nm} est", tag=f"mh_est_{nm}")
                            with dpg.plot(label="Attitude error", height=250, width=-1):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="mh_err_t")
                                with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="mh_err_y"):
                                    for nm in ("yaw", "pitch", "roll"):
                                        dpg.add_line_series([0.0], [0.0], label=nm, tag=f"mh_err_{nm}")
                                    dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="mh_err_cursor")
                            with dpg.plot(label="Gyro bias estimates", height=-1, width=-1):
                                dpg.add_plot_legend()
                                dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="mhb_t")
                                with dpg.plot_axis(dpg.mvYAxis, label="deg/s", tag="mhb_y"):
                                    for ax in "xyz":
                                        dpg.add_line_series([0.0], [0.0], label=f"b_{ax} est", tag=f"mh_b_{ax}")
                                        dpg.add_line_series([0.0], [0.0], label=f"b_{ax} true", tag=f"mh_bt_{ax}")

            for tag, role in (("true_series", "truth"), ("gyro_series", "gyro"), ("accel_series", "accel"),
                              ("comp_series", "fused"), ("kf_series", "kalman"), ("err_gyro", "gyro"),
                              ("err_accel", "accel"), ("err_comp", "fused"), ("err_kf", "kalman"),
                              ("bias_true", "truth"), ("bias_kf", "kalman"), ("bode_lp", "accel"),
                              ("bode_hp", "gyro"), ("bode_fc", "fused"), ("bode_motion", "cursor"),
                              ("surge_series", "error")):
                bind_role(tag, role, weight=1.0 if tag in ("accel_series", "err_accel") else 2.0)
            bind_role("kf_band", "kalman", kind="shade", alpha=60)
            bind_role("bias_band", "kalman", kind="shade", alpha=60)
            bind_role("gated_series", "error", kind="scatter", weight=2.0)
            for tag in ("pitch_cursor", "err_cursor", "mh_err_cursor"):
                bind_role(tag, "cursor", weight=1.5)
            axis_roles = {"yaw": "mag", "pitch": "gyro", "roll": "accel"}
            for nm, role in axis_roles.items():
                bind_role(f"mh_true_{nm}", role, weight=1.0, alpha=140)
                bind_role(f"mh_est_{nm}", role, weight=2.2)
                bind_role(f"mh_err_{nm}", role)
            for ax, role in zip("xyz", ("accel", "gyro", "mag")):
                bind_role(f"mh_b_{ax}", role, weight=2.2)
                bind_role(f"mh_bt_{ax}", role, weight=1.0, alpha=140)

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("primary", True)
            self._push_controls()
            self._sync_mode()
            self.refresh()
            self.playback.play()
            while dpg.is_dearpygui_running():
                self.playback.tick()
                dpg.render_dearpygui_frame()
        finally:
            dpg.destroy_context()
            imu_style.reset_bindings()


def run_app(scenario_id: str | None = None, params: ComplementaryParams | None = None) -> None:
    app = ComplementaryApp(initial=params, scenario_id=scenario_id)
    app.run()
