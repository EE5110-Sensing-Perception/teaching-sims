"""Reusable time playback (play / pause / scrub / speed / plot cursors)."""

from __future__ import annotations

import time
from typing import Callable

import dearpygui.dearpygui as dpg
import numpy as np


class Playback:
    """Drive a view time over a simulated time vector.

    Call ``build_controls()`` inside a container, ``set_times(t)`` after each
    simulation, and ``tick()`` once per rendered frame. ``on_time(i, t)`` is
    invoked whenever the view index changes (scrub, seek, or animation).
    """

    def __init__(
        self,
        prefix: str,
        on_time: Callable[[int, float], None] | None = None,
        *,
        speed: float = 1.0,
        speed_range: tuple[float, float] | None = (0.1, 4.0),
        speed_label: str = "Speed (x realtime)",
    ) -> None:
        self.prefix = prefix
        self.on_time = on_time
        self.speed = speed
        self.speed_range = speed_range
        self.speed_label = speed_label
        self.playing = False
        self._t0: float | None = None
        self._t: np.ndarray = np.zeros(1)
        self._suppress = False
        self._cursors: dict[str, tuple[float, float]] = {}
        self.index = 0

    # --- tags -------------------------------------------------------------------
    @property
    def slider_tag(self) -> str:
        return f"{self.prefix}_view_t"

    @property
    def speed_tag(self) -> str:
        return f"{self.prefix}_speed"

    @property
    def t_view(self) -> float:
        return float(self._t[self.index])

    @property
    def t_end(self) -> float:
        return float(self._t[-1])

    # --- UI ---------------------------------------------------------------------
    def build_controls(self, heading: str = "Playback") -> None:
        if heading:
            dpg.add_text(heading)
        dpg.add_slider_float(
            tag=self.slider_tag,
            label="View time (s)",
            default_value=0.0,
            min_value=0.0,
            max_value=1.0,
            callback=self._on_scrub,
        )
        if self.speed_range is not None:
            dpg.add_slider_float(
                tag=self.speed_tag,
                label=self.speed_label,
                default_value=self.speed,
                min_value=self.speed_range[0],
                max_value=self.speed_range[1],
                callback=self._on_speed,
            )
        with dpg.group(horizontal=True):
            dpg.add_button(label="Play", width=100, callback=lambda: self.play())
            dpg.add_button(label="Pause", width=100, callback=lambda: self.pause())

    def _on_scrub(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self.playing = False
        self.seek(float(dpg.get_value(self.slider_tag)))

    def _on_speed(self, *_a, **_k) -> None:
        if self._suppress:
            return
        self.speed = max(1e-3, float(dpg.get_value(self.speed_tag)))
        if self.playing:
            # keep view time continuous across a speed change
            self._t0 = time.monotonic() - self.t_view / self.speed

    # --- data -------------------------------------------------------------------
    def set_times(self, t: np.ndarray, *, keep: bool = True) -> None:
        """Bind a new time vector; keep the current view time if possible."""
        t_prev = self.t_view
        self._t = np.asarray(t, dtype=float)
        if dpg.does_item_exist(self.slider_tag):
            dpg.configure_item(self.slider_tag, min_value=float(self._t[0]), max_value=float(self._t[-1]))
        if self.playing:
            return
        self.seek(t_prev if keep else self.t_end)

    def set_cursor_span(self, tag: str, *arrays) -> None:
        """Register a vertical cursor line series spanning the given data."""
        y = np.concatenate([np.ravel(np.asarray(a, dtype=float)) for a in arrays])
        lo, hi = float(np.nanmin(y)), float(np.nanmax(y))
        pad = 0.05 * (hi - lo + 1e-9)
        self._cursors[tag] = (lo - pad, hi + pad)
        self._draw_cursor(tag)

    def _draw_cursor(self, tag: str) -> None:
        if dpg.does_item_exist(tag):
            lo, hi = self._cursors[tag]
            ti = self.t_view
            dpg.set_value(tag, [[ti, ti], [lo, hi]])

    # --- transport ----------------------------------------------------------------
    def index_at(self, t_query: float) -> int:
        t = self._t
        tq = float(np.clip(t_query, float(t[0]), float(t[-1])))
        i = int(np.searchsorted(t, tq, side="right") - 1)
        return int(np.clip(i, 0, len(t) - 1))

    def seek(self, t_query: float) -> None:
        self.index = self.index_at(t_query)
        if dpg.does_item_exist(self.slider_tag):
            self._suppress = True
            try:
                dpg.set_value(self.slider_tag, self.t_view)
            finally:
                self._suppress = False
        for tag in self._cursors:
            self._draw_cursor(tag)
        if self.on_time is not None:
            self.on_time(self.index, self.t_view)

    def play(self, from_start: bool = True) -> None:
        if self.speed_range is not None and dpg.does_item_exist(self.speed_tag):
            self.speed = max(1e-3, float(dpg.get_value(self.speed_tag)))
        start = float(self._t[0]) if from_start else self.t_view
        self.playing = True
        self._t0 = time.monotonic() - (start - float(self._t[0])) / self.speed
        self.seek(start)

    def pause(self) -> None:
        self.playing = False

    def tick(self) -> None:
        if not self.playing:
            return
        if self._t0 is None:
            self._t0 = time.monotonic()
        t_now = float(self._t[0]) + (time.monotonic() - self._t0) * self.speed
        if t_now >= self.t_end:
            self.playing = False
            self.seek(self.t_end)
            return
        i = self.index_at(t_now)
        if i != self.index:
            self.seek(t_now)
