"""Smoke test: every registered slide figure renders to PDF."""

from __future__ import annotations

import pytest

from teaching_sims.slides.imu_figures import REGISTRY, generate


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_figure_renders(tmp_path, name):
    (path,) = generate(tmp_path, [name])
    assert path.exists() and path.stat().st_size > 1000
