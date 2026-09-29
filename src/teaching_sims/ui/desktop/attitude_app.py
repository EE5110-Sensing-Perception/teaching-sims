"""Dear PyGui desktop app: frames, rotations and attitude kinematics."""

from __future__ import annotations

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.topics.attitude.physics import (
    AttitudeParams,
    Convention,
    Integrator,
    Sequence,
    T_FRD_FLU,
    T_NED_ENU,
    body_axis_labels,
    dcm_to_quat,
    integrate_attitude,
    nav_axis_labels,
    orthonormalize,
    process,
    quat_axis_angle,
    rotation_angle_deg,
    sequence_frames,
)
from teaching_sims.topics.attitude.scenarios import SCENARIOS, get_scenario
from teaching_sims.ui.desktop import imu_style
from teaching_sims.ui.desktop.imu_style import OrthoCamera, bind_role, draw_body_box
from teaching_sims.ui.desktop.playback import Playback
from teaching_sims.ui.desktop.plot_utils import fit_axes, fxy as _fxy

VIEW_W, VIEW_H = 640, 450
DCM_W, DCM_H = 400, 450

MODES = ("Pose", "Rotation sequence", "Rate integration")
CONV_LABELS = {"NED / FRD (aerospace)": Convention.NED_FRD, "ENU / FLU (ROS REP-103)": Convention.ENU_FLU}
LABEL_FOR_CONV = {v: k for k, v in CONV_LABELS.items()}
SEQ_LABELS = {
    "Intrinsic Z-Y'-X'' (yaw, pitch, roll)": Sequence.INTRINSIC_ZYX,
    "Extrinsic X-Y-Z (fixed axes)": Sequence.EXTRINSIC_XYZ,
    "Intrinsic X-Y'-Z'' (roll first)": Sequence.INTRINSIC_XYZ,
}
LABEL_FOR_SEQ = {v: k for k, v in SEQ_LABELS.items()}
INT_LABELS = {"Quaternion exp-map": Integrator.QUAT_EXP, "First-order DCM": Integrator.DCM_EULER}
LABEL_FOR_INT = {v: k for k, v in INT_LABELS.items()}

# Body axis colors follow the robotics RGB = xyz convention (rviz).
AXIS_COLORS = ((240, 85, 85, 255), (95, 210, 120, 255), (90, 150, 245, 255))
NAV_COLOR = (170, 170, 180, 255)
GHOST_COLOR = imu_style.GHOST_COLOR
HIGHLIGHT = imu_style.rgba("cursor")


class AttitudeApp:
    def __init__(self, initial: AttitudeParams | None = None, scenario_id: str | None = None) -> None:
        self.params = initial or AttitudeParams()
        self.scenario_id = scenario_id
        self._mode = "Pose"
        self._suppress = False
        self._seq: dict[str, object] | None = None
        self._ghost: np.ndarray | None = None
        self._int: dict[str, object] | None = None
        self._snap: dict[str, object] | None = None
        self.playback = Playback("att", on_time=self._on_time, speed=1.0, speed_range=(0.1, 3.0))
        self.cam = OrthoCamera(origin=(VIEW_W * 0.47, VIEW_H * 0.48), scale=120.0)
        if scenario_id:
            sc = get_scenario(scenario_id)
            self.params = sc.params
            self._mode = sc.mode
            self._title = sc.title
            self._note = f"{sc.teaching_point}\n{sc.notes}"
        else:
            self._title = "Frames, rotations and attitude kinematics"
            self._note = "Body frame in the navigation frame: DCM, Euler, quaternion, conventions and integration."

    # --- controls ---------------------------------------------------------------------
    def _read_controls(self) -> AttitudeParams:
        return AttitudeParams(
            yaw_deg=float(dpg.get_value("yaw")),
            pitch_deg=float(dpg.get_value("pitch")),
            roll_deg=float(dpg.get_value("roll")),
            convention=CONV_LABELS[dpg.get_value("convention")],
            sequence=SEQ_LABELS[dpg.get_value("sequence")],
            pitch_scan_deg=float(dpg.get_value("scan_amp")),
            perturb_deg=float(dpg.get_value("perturb")),
            wx_dps=float(dpg.get_value("wx")),
            wy_dps=float(dpg.get_value("wy")),
            wz_dps=float(dpg.get_value("wz")),
            coning_amp_dps=float(dpg.get_value("coning_amp")),
            coning_hz=float(dpg.get_value("coning_hz")),
            int_dt_s=float(dpg.get_value("int_dt")),
            int_duration_s=float(dpg.get_value("int_dur")),
            integrator=INT_LABELS[dpg.get_value("integrator")],
            renormalize=bool(dpg.get_value("renorm")),
        )

    def _push_controls(self, p: AttitudeParams) -> None:
        self._suppress = True
        try:
            dpg.set_value("mode", self._mode)
            dpg.set_value("yaw", p.yaw_deg)
            dpg.set_value("pitch", p.pitch_deg)
            dpg.set_value("roll", p.roll_deg)
            dpg.set_value("convention", LABEL_FOR_CONV[p.convention])
            dpg.set_value("sequence", LABEL_FOR_SEQ[p.sequence])
            dpg.set_value("scan_amp", p.pitch_scan_deg)
            dpg.set_value("perturb", p.perturb_deg)
            dpg.set_value("wx", p.wx_dps)
            dpg.set_value("wy", p.wy_dps)
            dpg.set_value("wz", p.wz_dps)
            dpg.set_value("coning_amp", p.coning_amp_dps)
            dpg.set_value("coning_hz", p.coning_hz)
            dpg.set_value("int_dt", p.int_dt_s)
            dpg.set_value("int_dur", p.int_duration_s)
            dpg.set_value("integrator", LABEL_FOR_INT[p.integrator])
            dpg.set_value("renorm", p.renormalize)
        finally:
            self._suppress = False

    def _apply_scenario(self, scenario_id: str) -> None:
        sc = get_scenario(scenario_id)
        self.scenario_id = scenario_id
        self.params = sc.params
        self._mode = sc.mode
        self._title = sc.title
        self._note = f"{sc.teaching_point}\n{sc.notes}"
        self._push_controls(self.params)
        dpg.set_value("banner_title", self._title)
        dpg.set_value("banner_body", self._note)
        dpg.set_value("scenario_text", self._note)
        self._sync_mode_widgets()
        self.refresh()
        if self._mode in ("Rotation sequence", "Rate integration"):
            self.playback.play()

    def _set_presenter(self, _s=None, app_data=None, _u=None) -> None:
        on = bool(app_data if app_data is not None else dpg.get_value("presenter_mode"))
        dpg.configure_item("advanced_controls", show=not on)
        dpg.configure_item("banner_panel", height=120 if on else 76)
        imu_style.apply_presenter(on)

    def _on_mode(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self._mode = str(dpg.get_value("mode"))
        self._sync_mode_widgets()
        self.refresh()
        if self._mode != "Pose":
            self.playback.play()

    def _sync_mode_widgets(self) -> None:
        dpg.configure_item("seq_group", show=self._mode == "Rotation sequence")
        dpg.configure_item("rate_group", show=self._mode == "Rate integration")
        dpg.configure_item("pb_group", show=self._mode != "Pose")
        tab = "tab_rate" if self._mode == "Rate integration" else "tab_lock"
        dpg.set_value("lower_tabs", tab)

    def _on_change(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self.playback.pause()
        self.refresh()

    # --- drawing ----------------------------------------------------------------------
    def _draw_scene(self, r: np.ndarray, *, ghost: np.ndarray | None = None, axis_nav: np.ndarray | None = None,
                    caption: str = "") -> None:
        tag = "view_draw"
        dpg.delete_item(tag, children_only=True)
        conv = self.params.convention
        cam = self.cam
        dpg.draw_rectangle((0, 0), (VIEW_W, VIEW_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)

        # ground grid in the local-level plane
        for k in np.linspace(-1.5, 1.5, 7):
            dpg.draw_line(cam.project([k, -1.5, 0]), cam.project([k, 1.5, 0]), color=(55, 58, 68, 255), parent=tag)
            dpg.draw_line(cam.project([-1.5, k, 0]), cam.project([1.5, k, 0]), color=(55, 58, 68, 255), parent=tag)

        # navigation axes (physical directions in NED; labels depend on convention)
        nav_dirs_ned = np.eye(3) if conv == Convention.NED_FRD else T_NED_ENU.T  # columns: nav axes in NED
        for k, lab in enumerate(nav_axis_labels(conv)):
            tip = nav_dirs_ned[:, k] * 1.75
            dpg.draw_arrow(cam.project(tip), cam.project([0, 0, 0]), color=NAV_COLOR, thickness=2, size=9, parent=tag)
            px, py = cam.project(tip * 1.08)
            dpg.draw_text((px - 5, py - 9), lab, color=NAV_COLOR, size=17, parent=tag)

        if ghost is not None:
            self._draw_box(tag, ghost, wire_only=True)

        self._draw_box(tag, r)

        if axis_nav is not None:
            a = np.asarray(axis_nav, dtype=float)
            a = a / (np.linalg.norm(a) + 1e-12)
            dpg.draw_line(cam.project(-1.9 * a), cam.project(1.9 * a), color=HIGHLIGHT, thickness=4, parent=tag)
            px, py = cam.project(2.0 * a)
            dpg.draw_text((px + 4, py - 8), "rotation axis", color=HIGHLIGHT, size=14, parent=tag)

        # body axes: FRD columns of R, or FLU = FRD * diag(1,-1,-1)
        rb = r if conv == Convention.NED_FRD else r @ T_FRD_FLU
        for k, lab in enumerate(body_axis_labels(conv)):
            v = rb[:, k] / (np.linalg.norm(rb[:, k]) + 1e-12) * 1.3
            dpg.draw_arrow(cam.project(v), cam.project([0, 0, 0]), color=AXIS_COLORS[k], thickness=4, size=12, parent=tag)
            px, py = cam.project(v * 1.1)
            dpg.draw_text((px + 2, py - 8), lab, color=AXIS_COLORS[k], size=16, parent=tag)

        frame_name = "NED nav / FRD body" if conv == Convention.NED_FRD else "ENU nav / FLU body (ROS)"
        dpg.draw_text((10, 8), frame_name, color=(220, 220, 230, 255), size=16, parent=tag)
        if caption:
            dpg.draw_text((10, VIEW_H - 28), caption, color=HIGHLIGHT, size=16, parent=tag)
        if ghost is not None:
            dpg.draw_text((10, 30), "ghost = reference pose", color=GHOST_COLOR[:3] + (255,), size=14, parent=tag)

    def _draw_box(self, tag: str, r: np.ndarray, *, wire_only: bool = False) -> None:
        draw_body_box(tag, self.cam, r, wire_only=wire_only)

    def _draw_dcm(self, r: np.ndarray, subtitle: str = "") -> None:
        tag = "dcm_draw"
        dpg.delete_item(tag, children_only=True)
        conv = self.params.convention
        dpg.draw_rectangle((0, 0), (DCM_W, DCM_H), color=(60, 60, 70, 255), fill=(22, 24, 30, 255), parent=tag)
        r_show = r if conv == Convention.NED_FRD else T_NED_ENU @ r @ T_FRD_FLU
        nav = nav_axis_labels(conv)
        body = [b.split()[0] for b in body_axis_labels(conv)]
        title = "R^n_b : columns = body axes in nav"
        dpg.draw_text((12, 8), title, color=(220, 220, 230, 255), size=15, parent=tag)
        if subtitle:
            dpg.draw_text((12, 28), subtitle, color=HIGHLIGHT, size=14, parent=tag)
        x0, y0, cell = 70, 70, 88
        pos = imu_style.rgba("fused")
        neg = imu_style.rgba("gyro")
        for j in range(3):
            dpg.draw_text((x0 + j * cell + cell / 2 - 5, y0 - 22), body[j], color=AXIS_COLORS[j], size=16, parent=tag)
        for i in range(3):
            dpg.draw_text((x0 - 26, y0 + i * cell + cell / 2 - 9), nav[i], color=NAV_COLOR, size=16, parent=tag)
            for j in range(3):
                v = float(r_show[i, j])
                base = pos if v >= 0 else neg
                a = int(40 + 200 * min(1.0, abs(v)))
                p0 = (x0 + j * cell, y0 + i * cell)
                p1 = (p0[0] + cell - 4, p0[1] + cell - 4)
                dpg.draw_rectangle(p0, p1, color=(70, 70, 80, 255), fill=base[:3] + (a,), parent=tag)
                dpg.draw_text((p0[0] + 14, p0[1] + cell / 2 - 12), f"{v:+.2f}", color=(250, 250, 250, 255), size=18, parent=tag)

        q = dcm_to_quat(orthonormalize(r_show))
        axis, ang = quat_axis_angle(q)
        det = float(np.linalg.det(r))
        ortho = float(np.linalg.norm(r.T @ r - np.eye(3)))
        yq = y0 + 3 * cell + 14
        lines = [
            (f"q = [{q[0]:+.3f}, {q[1]:+.3f}, {q[2]:+.3f}, {q[3]:+.3f}]", (230, 230, 235, 255)),
            (f"-q = [{-q[0]:+.3f}, {-q[1]:+.3f}, {-q[2]:+.3f}, {-q[3]:+.3f}]  (same R)", (160, 160, 170, 255)),
            (f"axis [{axis[0]:+.2f}, {axis[1]:+.2f}, {axis[2]:+.2f}]  angle {ang:.1f} deg", (230, 230, 235, 255)),
            (f"det R = {det:.4f}    ||R^T R - I|| = {ortho:.1e}",
             imu_style.rgba("error") if ortho > 1e-3 else (160, 200, 160, 255)),
        ]
        for k, (txt, col) in enumerate(lines):
            dpg.draw_text((14, yq + 22 * k), txt, color=col, size=15, parent=tag)

    # --- playback -------------------------------------------------------------------
    def _on_time(self, i: int, t: float) -> None:
        if self._mode == "Rotation sequence" and self._seq is not None:
            frames = self._seq["frames"]
            stage = self._seq["stage"]
            labels = self._seq["labels"]
            i = min(i, len(frames) - 1)
            r = frames[i]
            self._draw_scene(r, ghost=self._ghost, axis_nav=self._seq["axis_nav"][i],
                             caption=f"step {int(stage[i]) + 1}/3: {labels[int(stage[i])]}")
            self._draw_dcm(r, subtitle=f"step {int(stage[i]) + 1}/3")
        elif self._mode == "Rate integration" and self._int is not None:
            est = self._int["est"][i]
            truth = self._int["truth"][i]
            err = float(self._int["angle_err_deg"][i])
            self._draw_scene(est, ghost=truth, caption=f"t = {t:5.2f} s   error vs truth = {err:.2f} deg")
            self._draw_dcm(est, subtitle="integrated estimate (may not be a rotation!)")

    # --- refresh --------------------------------------------------------------------
    def refresh(self) -> None:
        try:
            self.params = self._read_controls()
        except ValueError as exc:
            dpg.set_value("status_text", f"Invalid settings: {exc}")
            return
        p = self.params
        snap = process(p)
        self._snap = snap
        scan = snap["scan"]
        dpg.set_value("scan_dyaw", _fxy(scan["pitch_deg"], np.maximum(scan["dyaw_deg"], 1e-4)))
        dpg.set_value("scan_droll", _fxy(scan["pitch_deg"], np.maximum(scan["droll_deg"], 1e-4)))
        dpg.set_value("scan_gain", _fxy(scan["pitch_deg"], p.perturb_deg * scan["euler_rate_gain"]))
        k = int(np.argmin(np.abs(scan["pitch_deg"] - p.pitch_deg)))
        dpg.set_value("scan_marker", [[float(p.pitch_deg)], [max(float(scan["dyaw_deg"][k]), 1e-4)]])
        fit_axes("scan_x", "scan_y")

        ros = snap["euler_ros_deg"]
        base_status = (
            f"NED/FRD  y/p/r: {p.yaw_deg:6.1f} {p.pitch_deg:6.1f} {p.roll_deg:6.1f}\n"
            f"ROS FLU  y/p/r: {ros[0]:6.1f} {ros[1]:6.1f} {ros[2]:6.1f}\n"
            f"Euler-rate gain 1/cos(pitch) = {snap['euler_rate_gain']:.1f}"
        )

        if self._mode == "Pose":
            self._seq = self._int = None
            self.playback.set_times(np.zeros(1))
            self._draw_scene(snap["dcm"])
            self._draw_dcm(snap["dcm"])
            dpg.set_value("status_text", base_status)
        elif self._mode == "Rotation sequence":
            self._int = None
            self._seq = sequence_frames(p.yaw_deg, p.pitch_deg, p.roll_deg, p.sequence)
            ref = sequence_frames(p.yaw_deg, p.pitch_deg, p.roll_deg, Sequence.INTRINSIC_ZYX)["final"]
            self._ghost = ref if p.sequence != Sequence.INTRINSIC_ZYX else None
            n = len(self._seq["frames"])
            self.playback.set_times(np.arange(n) / 40.0)
            diff = rotation_angle_deg(ref, self._seq["final"])
            dpg.set_value(
                "status_text",
                base_status + f"\nFinal pose vs ZYX pose: {diff:.1f} deg apart"
                + ("  (same pose, different path)" if diff < 0.01 and p.sequence != Sequence.INTRINSIC_ZYX else ""),
            )
            self._on_time(self.playback.index, self.playback.t_view)
        else:
            self._seq = None
            self._ghost = None
            out = integrate_attitude(p)
            self._int = out
            t = out["t_s"]
            dpg.set_value("int_err", _fxy(t, out["angle_err_deg"]))
            dpg.set_value("int_ortho", _fxy(t, np.maximum(out["ortho_err"], 1e-12)))
            fit_axes("interr_x", "interr_y", "ortho_x", "ortho_y")
            self.playback.set_times(t)
            self.playback.set_cursor_span("int_err_cursor", out["angle_err_deg"])
            self.playback.set_cursor_span("int_ortho_cursor", np.maximum(out["ortho_err"], 1e-12))
            method = LABEL_FOR_INT[p.integrator]
            dpg.set_value(
                "status_text",
                (
                    f"{method}, dt = {p.int_dt_s * 1e3:.0f} ms, renormalize {'ON' if p.renormalize else 'OFF'}\n"
                    f"Final attitude error: {out['final_angle_err_deg']:.3f} deg\n"
                    f"Final ||R^T R - I||: {out['final_ortho_err']:.2e}\n"
                    "Ghost = fine-step reference attitude"
                ),
            )
            self._on_time(self.playback.index, self.playback.t_view)

    # --- layout ----------------------------------------------------------------------
    def _slider(self, tag: str, label: str, value: float, lo: float, hi: float, fmt: str = "%.2f") -> None:
        dpg.add_slider_float(tag=tag, label=label, default_value=value, min_value=lo, max_value=hi,
                             format=fmt, callback=self._on_change)

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(title="Teaching Sims - Frames & Rotations", width=1500, height=980)
        imu_style.bind_base_theme()
        p = self.params

        try:
            with dpg.window(tag="primary", label="Attitude"):
                with dpg.child_window(tag="banner_panel", height=76, border=True):
                    dpg.add_text(self._title, tag="banner_title")
                    dpg.add_text(self._note, tag="banner_body", wrap=1100)
                with dpg.group(horizontal=True):
                    with dpg.child_window(width=380, border=True):
                        dpg.add_checkbox(tag="presenter_mode", label="Presenter mode", default_value=False,
                                         callback=self._set_presenter)
                        dpg.add_combo(tag="mode", label="Mode", items=list(MODES), default_value=self._mode,
                                      callback=self._on_mode)
                        dpg.add_combo(tag="convention", label="Frames", items=list(CONV_LABELS),
                                      default_value=LABEL_FOR_CONV[p.convention], callback=self._on_change)
                        dpg.add_separator()
                        dpg.add_text("Pose (ZYX Euler, NED/FRD)")
                        self._slider("yaw", "Yaw (deg)", p.yaw_deg, -180.0, 180.0, "%.1f")
                        self._slider("pitch", "Pitch (deg)", p.pitch_deg, -90.0, 90.0, "%.1f")
                        self._slider("roll", "Roll (deg)", p.roll_deg, -180.0, 180.0, "%.1f")
                        with dpg.group(tag="seq_group"):
                            dpg.add_separator()
                            dpg.add_combo(tag="sequence", label="Order", items=list(SEQ_LABELS),
                                          default_value=LABEL_FOR_SEQ[p.sequence], callback=self._on_change)
                        with dpg.group(tag="rate_group"):
                            dpg.add_separator()
                            dpg.add_text("Body rate (deg/s)")
                            self._slider("wx", "wx", p.wx_dps, -180.0, 180.0, "%.0f")
                            self._slider("wy", "wy", p.wy_dps, -180.0, 180.0, "%.0f")
                            self._slider("wz", "wz", p.wz_dps, -180.0, 180.0, "%.0f")
                            self._slider("coning_amp", "Coning amp", p.coning_amp_dps, 0.0, 120.0, "%.0f")
                            dpg.add_combo(tag="integrator", label="Integrator", items=list(INT_LABELS),
                                          default_value=LABEL_FOR_INT[p.integrator], callback=self._on_change)
                            dpg.add_checkbox(tag="renorm", label="Renormalize each step",
                                             default_value=p.renormalize, callback=self._on_change)
                            self._slider("int_dt", "Step dt (s)", p.int_dt_s, 0.002, 0.1, "%.3f")
                        with dpg.group(tag="pb_group"):
                            dpg.add_separator()
                            self.playback.build_controls()
                        with dpg.group(tag="advanced_controls"):
                            dpg.add_separator()
                            dpg.add_text("Advanced")
                            self._slider("scan_amp", "Scan +/- pitch", p.pitch_scan_deg, 60.0, 89.9, "%.1f")
                            self._slider("perturb", "Perturbation (deg)", p.perturb_deg, 0.05, 2.0)
                            self._slider("coning_hz", "Coning Hz", p.coning_hz, 0.2, 5.0)
                            self._slider("int_dur", "Duration (s)", p.int_duration_s, 2.0, 20.0, "%.0f")
                        dpg.add_separator()
                        dpg.add_text("Lecture scenarios")
                        for sid, sc in SCENARIOS.items():
                            dpg.add_button(label=sc.title, width=-1, user_data=sid,
                                           callback=lambda s, a, u: self._apply_scenario(u))
                        dpg.add_separator()
                        dpg.add_text(self._note, tag="scenario_text", wrap=350)
                        dpg.add_separator()
                        dpg.add_text("", tag="status_text", wrap=350)

                    with dpg.child_window(border=False):
                        with dpg.group(horizontal=True):
                            dpg.add_drawlist(width=VIEW_W, height=VIEW_H, tag="view_draw")
                            dpg.add_drawlist(width=DCM_W, height=DCM_H, tag="dcm_draw")
                        with dpg.tab_bar(tag="lower_tabs"):
                            with dpg.tab(label="Gimbal lock", tag="tab_lock"):
                                with dpg.plot(label="Euler change for a 0.5 deg body rotation", height=-1, width=-1):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label="pitch (deg)", tag="scan_x")
                                    with dpg.plot_axis(dpg.mvYAxis, label="|change| (deg)", tag="scan_y",
                                                       scale=dpg.mvPlotScale_Log10):
                                        dpg.add_line_series([0.0], [1.0], label="yaw", tag="scan_dyaw")
                                        dpg.add_line_series([0.0], [1.0], label="roll", tag="scan_droll")
                                        dpg.add_line_series([0.0], [1.0], label="perturb / cos(pitch)", tag="scan_gain")
                                        dpg.add_scatter_series([0.0], [1.0], label="current pitch", tag="scan_marker")
                            with dpg.tab(label="Rate integration", tag="tab_rate"):
                                with dpg.group(horizontal=True):
                                    with dpg.plot(label="Attitude error vs reference", height=-1, width=520):
                                        dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="interr_x")
                                        with dpg.plot_axis(dpg.mvYAxis, label="deg", tag="interr_y"):
                                            dpg.add_line_series([0.0], [0.0], tag="int_err")
                                            dpg.add_line_series([0.0, 0.0], [0.0, 1.0], tag="int_err_cursor")
                                    with dpg.plot(label="Orthonormality ||R^T R - I||", height=-1, width=-1):
                                        dpg.add_plot_axis(dpg.mvXAxis, label="t (s)", tag="ortho_x")
                                        with dpg.plot_axis(dpg.mvYAxis, tag="ortho_y", scale=dpg.mvPlotScale_Log10):
                                            dpg.add_line_series([0.0], [1e-12], tag="int_ortho")
                                            dpg.add_line_series([0.0, 0.0], [1e-12, 1.0], tag="int_ortho_cursor")

            bind_role("scan_dyaw", "gyro")
            bind_role("scan_droll", "accel")
            bind_role("scan_gain", "reference", weight=1.5)
            bind_role("scan_marker", "cursor", kind="scatter", weight=4.0)
            bind_role("int_err", "error")
            bind_role("int_ortho", "fused")
            bind_role("int_err_cursor", "cursor", weight=1.5)
            bind_role("int_ortho_cursor", "cursor", weight=1.5)

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("primary", True)
            self._push_controls(self.params)
            self._sync_mode_widgets()
            self.refresh()
            if self._mode != "Pose":
                self.playback.play()
            while dpg.is_dearpygui_running():
                self.playback.tick()
                dpg.render_dearpygui_frame()
        finally:
            dpg.destroy_context()
            imu_style.reset_bindings()


def run_app(scenario_id: str | None = None, params: AttitudeParams | None = None) -> None:
    if scenario_id and params is None:
        params = get_scenario(scenario_id).params
    AttitudeApp(initial=params, scenario_id=scenario_id).run()
