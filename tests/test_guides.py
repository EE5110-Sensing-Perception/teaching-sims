"""Study guides: new figures render, and the Canvas build is inline-styled and self-consistent."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from teaching_sims.guides import build, figures

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", sorted(figures.REGISTRY))
def test_guide_figure_renders(tmp_path, name):
    (path,) = figures.generate(tmp_path, [name])
    assert path.exists() and path.stat().st_size > 1000


def test_guide_figure_pdf_for_lecture_decks(tmp_path):
    (path,) = figures.generate(tmp_path, ["g_random_walk"], fmt="pdf")
    assert path.suffix == ".pdf" and path.read_bytes().startswith(b"%PDF")


def test_to_canvas_inlines_classes_and_rewrites_images():
    out = build.to_canvas('<div class="key"><figure><img src="img/a.png" alt="x"></figure></div>', "/files/")
    assert "class=" not in out
    assert 'style="background:#fbf0f5' in out
    assert 'src="/files/a.png"' in out
    assert "<figure" not in out and "</div></div>" in out


def test_unknown_class_is_rejected():
    with pytest.raises(ValueError, match="unknown class"):
        build.to_canvas('<p class="nope">x</p>', "")


def test_all_guides_build(tmp_path):
    src = REPO / "guides" / "imu" / "src"
    shutil.copytree(src, tmp_path / "src")
    (tmp_path / "img").mkdir()
    names = {n for f in src.glob("*.html") for n in re.findall(r'src="img/([^"]+)"', f.read_text())}
    assert names <= set(f"{n}.png" for n in figures.all_names()), "guide references an unknown figure"
    for n in names:
        (tmp_path / "img" / n).write_bytes(b"png")
    written = build.build(tmp_path, "/base/")
    canvas = sorted((tmp_path / "canvas").glob("*.html"))
    assert len(canvas) == len(list(src.glob("*.html"))) == 8
    for f in canvas:
        text = f.read_text()
        assert "class=" not in text and "<script" not in text and "<style" not in text
        assert 'src="img/' not in text
    assert (tmp_path / "preview" / "index.html") in written
