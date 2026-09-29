"""Semantic colors shared by the Dear PyGui apps and the slide figures.

Roles, not hues: every demo and slide draws "truth", "gyro", "accel", ...
in the same color. The light palette matches the SimplePlus Beamer theme;
the dark palette is tuned for the Dear PyGui default (dark) background.
"""

from __future__ import annotations

RGB = tuple[int, int, int]

ROLES = ("truth", "measured", "gyro", "accel", "mag", "fused", "kalman", "error", "reference", "cursor")

# Slides (white background) - SimplePlus colors where available.
LIGHT: dict[str, RGB] = {
    "truth": (56, 66, 89),  # MediumBlack
    "measured": (160, 165, 175),
    "gyro": (4, 80, 115),  # MediumBlue
    "accel": (94, 179, 168),  # MediumGreen
    "mag": (222, 140, 30),
    "fused": (160, 0, 80),  # maroon
    "kalman": (120, 60, 170),
    "error": (236, 88, 88),  # MediumRed
    "reference": (120, 120, 120),
    "cursor": (200, 160, 0),
}

# Apps (dark background) - same hue families, lifted for contrast.
DARK: dict[str, RGB] = {
    "truth": (235, 235, 242),
    "measured": (140, 145, 155),
    "gyro": (90, 165, 235),
    "accel": (100, 205, 175),
    "mag": (245, 170, 60),
    "fused": (240, 95, 155),
    "kalman": (185, 140, 245),
    "error": (240, 105, 105),
    "reference": (150, 150, 150),
    "cursor": (250, 220, 90),
}


def mpl(role: str) -> tuple[float, float, float]:
    """Light-palette color as a matplotlib RGB tuple in [0, 1]."""
    r, g, b = LIGHT[role]
    return (r / 255.0, g / 255.0, b / 255.0)
