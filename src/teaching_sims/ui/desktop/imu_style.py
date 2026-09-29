"""Shared Dear PyGui styling and drawlist helpers for the IMU demos.

* ``bind_base_theme()``      - rounded frames used by every app
* ``bind_role(tag, role)``   - color a plot series by semantic role (see ``ui.palette``)
* ``apply_presenter(on)``    - bigger fonts and thicker lines for projection
* ``draw_vector`` / ``draw_dial`` / ``iso_project`` - schematic primitives
"""

from __future__ import annotations

import math

import dearpygui.dearpygui as dpg
import numpy as np

from teaching_sims.ui.palette import DARK

_SERIES_KINDS = {
    "line": dpg.mvLineSeries,
    "scatter": dpg.mvScatterSeries,
    "shade": dpg.mvShadeSeries,
    "bar": dpg.mvBarSeries,
    "inf": dpg.mvInfLineSeries,
}

_theme_cache: dict[tuple, int] = {}
_bound: dict[str, tuple[str, str, float, int]] = {}
_presenter = False

PRESENTER_FONT_SCALE = 1.3
PRESENTER_LINE_SCALE = 1.7


def rgba(role: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = DARK[role]
    return (r, g, b, alpha)


def bind_base_theme() -> None:
    with dpg.theme() as global_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
    dpg.bind_theme(global_theme)


def _series_theme(role: str, kind: str, weight: float, alpha: int) -> int:
    key = (role, kind, round(weight, 2), alpha)
    if key in _theme_cache:
        return _theme_cache[key]
    col = rgba(role, alpha)
    with dpg.theme() as th:
        with dpg.theme_component(_SERIES_KINDS[kind]):
            dpg.add_theme_color(dpg.mvPlotCol_Line, col, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_Fill, col, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_MarkerFill, col, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_MarkerOutline, col, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, weight, category=dpg.mvThemeCat_Plots)
            if kind == "scatter":
                dpg.add_theme_style(dpg.mvPlotStyleVar_Marker, dpg.mvPlotMarker_Circle, category=dpg.mvThemeCat_Plots)
                dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerSize, 2.5 * weight / 2.0, category=dpg.mvThemeCat_Plots)
    _theme_cache[key] = th
    return th


def bind_role(tag: str, role: str, *, kind: str = "line", weight: float = 2.0, alpha: int = 255) -> None:
    """Color series ``tag`` by semantic ``role``; re-applied on presenter toggle."""
    _bound[tag] = (role, kind, weight, alpha)
    scale = PRESENTER_LINE_SCALE if _presenter else 1.0
    if dpg.does_item_exist(tag):
        dpg.bind_item_theme(tag, _series_theme(role, kind, weight * scale, alpha))


def apply_presenter(enabled: bool) -> None:
    """Scale fonts and plot line weights for projection."""
    global _presenter
    _presenter = bool(enabled)
    dpg.set_global_font_scale(PRESENTER_FONT_SCALE if _presenter else 1.0)
    for tag, (role, kind, weight, alpha) in list(_bound.items()):
        bind_role(tag, role, kind=kind, weight=weight, alpha=alpha)


def reset_bindings() -> None:
    """Forget cached themes (call after ``dpg.destroy_context``)."""
    global _presenter
    _theme_cache.clear()
    _bound.clear()
    _presenter = False


# --- drawlist primitives ----------------------------------------------------------


def draw_vector(
    parent: str,
    start: tuple[float, float],
    vec: tuple[float, float],
    color,
    *,
    label: str = "",
    thickness: float = 3.0,
    head: float = 10.0,
    label_offset: tuple[float, float] = (6.0, -18.0),
    size: int = 14,
) -> None:
    """Arrow from ``start`` along screen vector ``vec`` (pixels, y down)."""
    x0, y0 = start
    x1, y1 = x0 + vec[0], y0 + vec[1]
    if math.hypot(vec[0], vec[1]) < 1.0:
        dpg.draw_circle((x0, y0), 3, color=color, fill=color, parent=parent)
    else:
        dpg.draw_arrow((x1, y1), (x0, y0), color=color, thickness=thickness, size=head, parent=parent)
    if label:
        dpg.draw_text((x1 + label_offset[0], y1 + label_offset[1]), label, color=color, size=size, parent=parent)


def heading_to_screen(heading_deg: float, radius: float) -> tuple[float, float]:
    """Compass heading (0 = up, clockwise positive) to a screen offset."""
    a = math.radians(heading_deg)
    return (radius * math.sin(a), -radius * math.cos(a))


def draw_dial(
    parent: str,
    center: tuple[float, float],
    radius: float,
    needles: list[tuple[float, tuple, str]],
    *,
    cardinal: bool = True,
    tick_step_deg: float = 30.0,
) -> None:
    """Compass / turntable dial. ``needles`` = [(heading_deg, rgba, label), ...]."""
    cx, cy = center
    dpg.draw_circle(center, radius, color=(120, 120, 130, 255), thickness=2, parent=parent)
    n_ticks = int(round(360.0 / tick_step_deg))
    for k in range(n_ticks):
        h = k * tick_step_deg
        ox, oy = heading_to_screen(h, radius)
        ix, iy = heading_to_screen(h, radius * 0.9)
        dpg.draw_line((cx + ix, cy + iy), (cx + ox, cy + oy), color=(120, 120, 130, 255), thickness=2, parent=parent)
    if cardinal:
        for h, txt in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            ox, oy = heading_to_screen(h, radius + 14)
            dpg.draw_text((cx + ox - 5, cy + oy - 8), txt, color=(200, 200, 210, 255), size=15, parent=parent)
    for i, (h, col, label) in enumerate(needles):
        tip = heading_to_screen(h, radius * (0.85 - 0.08 * i))
        draw_vector(parent, center, tip, col, label=label, thickness=4.0 - 0.5 * i, head=12, size=13)
    dpg.draw_circle(center, 4, color=(200, 200, 210, 255), fill=(200, 200, 210, 255), parent=parent)


class OrthoCamera:
    """Orthographic view of NED space: Up is up on screen, no mirroring.

    ``az_deg`` is the compass bearing *from the origin to the camera*;
    ``el_deg`` is its elevation. The default camera sits east-south-east and
    slightly above, so a north-heading vehicle is seen in profile (nose right).
    """

    def __init__(self, origin: tuple[float, float], scale: float, az_deg: float = 120.0, el_deg: float = 22.0) -> None:
        self.origin = origin
        self.scale = scale
        az, el = math.radians(az_deg), math.radians(el_deg)
        c = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), -math.sin(el)])
        f = -c
        right = np.cross(f, np.array([0.0, 0.0, -1.0]))
        right /= np.linalg.norm(right)
        self.right = right
        self.up = np.cross(right, f)
        self.toward = c

    def project(self, p_ned) -> tuple[float, float]:
        p = np.asarray(p_ned, dtype=float)
        return (
            self.origin[0] + self.scale * float(p @ self.right),
            self.origin[1] - self.scale * float(p @ self.up),
        )

    def depth(self, p_ned) -> float:
        """Larger = closer to the viewer."""
        return float(np.asarray(p_ned, dtype=float) @ self.toward)
