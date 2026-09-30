"""Build the IMU study guides into Canvas-ready HTML.

Usage (from the repo root)::

    python -m teaching_sims.guides.build
    python -m teaching_sims.guides.build --image-base /courses/12345/file_contents/course%20files/imu-guides/

Sources live in ``guides/imu/src/*.html``: body fragments with a
``<!-- title: ... -->`` first line and a small set of classes (see ``CLASS_STYLES``).
Two outputs:

* ``guides/imu/canvas/*.html``: fragments for the Canvas HTML editor. Canvas strips
  ``<style>`` and ``<script>``, so every class becomes an inline style, and
  ``<figure>``/``<figcaption>`` become ``<div>``/``<p>``. Math stays as LaTeX in
  ``\\( \\)`` (inline) and ``$$ $$`` (display), which Canvas renders with MathJax.
  Image paths become ``--image-base`` + file name.
* ``guides/imu/preview/*.html``: standalone pages with MathJax for checking locally.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

GUIDE_DIR = Path("guides/imu")

INK, BLUE, MAROON, TEAL, ORANGE = "#384259", "#045073", "#A00050", "#3f8f85", "#b8700f"
TAG_STYLES = {
    "h2": f"color:{INK};border-bottom:2px solid {MAROON};padding-bottom:4px;margin-top:1.8em",
    "h3": f"color:{BLUE};margin-top:1.4em",
    "h4": f"color:{INK};margin-top:1.1em",
    "table": "border-collapse:collapse;width:100%;margin:0.8em 0 1.2em 0",
    "th": "border:1px solid #cfd4dc;background:#f1f3f6;padding:6px 8px;text-align:left;vertical-align:top",
    "td": "border:1px solid #cfd4dc;padding:6px 8px;vertical-align:top",
    "figure": "margin:1.2em auto;text-align:center",
    "figcaption": "font-size:0.9em;color:#555;margin:0.4em 0 0 0;text-align:left",
    "img": "max-width:100%;height:auto",
    "code": "background:#f1f3f6;padding:1px 4px;border-radius:3px;font-family:Consolas,Menlo,monospace;font-size:0.92em",
}
_BOX = "padding:10px 14px;margin:1em 0;border-radius:4px"
CLASS_STYLES = {
    "def": f"background:#eef4fa;border-left:4px solid {BLUE};{_BOX}",
    "key": f"background:#fbf0f5;border-left:4px solid {MAROON};{_BOX}",
    "warn": f"background:#fff5e6;border-left:4px solid {ORANGE};{_BOX}",
    "demo": f"background:#eef7f5;border-left:4px solid {TEAL};{_BOX}",
    "example": f"border:1px solid #b9d9d4;background:#fafdfc;padding:12px 16px;margin:1.2em 0;border-radius:6px",
    "answer": f"border-left:3px solid #cfd4dc;padding:4px 12px;margin:0.6em 0 1em 0",
    "overview": f"background:#f6f7f9;border:1px solid #dfe3e8;{_BOX}",
    "wide": "width:100%",
    "narrow": "max-width:560px;width:100%",
    "muted": "color:#666;font-size:0.9em",
    "center": "text-align:center",
    "eq": "overflow-x:auto",
}
RENAME = {"figure": "div", "figcaption": "p"}

_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)(\s[^<>]*?)?(/?)>")
_ATTR = re.compile(r'\s(class|style|src)="([^"]*)"')
_TITLE = re.compile(r"^\s*<!--\s*title:\s*(.*?)\s*-->\s*\n?")


def _rewrite_tag(m: re.Match, image_base: str, errors: list[str]) -> str:
    closing, tag, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3) or "", m.group(4)
    out_tag = RENAME.get(tag, tag)
    if closing:
        return f"</{out_tag}>"
    found = dict(_ATTR.findall(attrs))
    rest = _ATTR.sub("", attrs)
    styles = [TAG_STYLES.get(tag, "")]
    for c in found.get("class", "").split():
        if c not in CLASS_STYLES:
            errors.append(f"unknown class {c!r}")
        styles.append(CLASS_STYLES.get(c, ""))
    styles.append(found.get("style", ""))
    style = ";".join(s.strip(";") for s in styles if s)
    parts = [out_tag]
    if "src" in found:
        src = found["src"]
        if src.startswith("img/"):
            src = image_base + src[len("img/"):]
        parts.append(f'src="{src}"')
    if rest.strip():
        parts.append(rest.strip())
    if style:
        parts.append(f'style="{style}"')
    return "<" + " ".join(parts) + (" /" if selfclose else "") + ">"


def to_canvas(body: str, image_base: str) -> str:
    errors: list[str] = []
    out = _TAG.sub(lambda m: _rewrite_tag(m, image_base, errors), body)
    if errors:
        raise ValueError("; ".join(sorted(set(errors))))
    return out


def preview_page(title: str, fragment: str, nav: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script>window.MathJax = {{ tex: {{ inlineMath: [['\\\\(', '\\\\)']], displayMath: [['$$', '$$']] }} }};</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
</head>
<body style="background:#fff;color:#2d3b45;font-family:'Lato','Helvetica Neue',Arial,sans-serif;line-height:1.55;max-width:900px;margin:0 auto;padding:16px">
<p style="font-size:0.9em">{nav}</p>
<h1 style="color:#384259">{html.escape(title)}</h1>
{fragment}
</body></html>
"""


def build(guide_dir: Path = GUIDE_DIR, image_base: str = "") -> list[Path]:
    src_dir = guide_dir / "src"
    img_dir = guide_dir / "img"
    canvas_dir, preview_dir = guide_dir / "canvas", guide_dir / "preview"
    canvas_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(src_dir.glob("*.html"))
    titles = {}
    for s in sources:
        m = _TITLE.match(s.read_text(encoding="utf-8"))
        if not m:
            raise ValueError(f"{s}: first line must be <!-- title: ... -->")
        titles[s] = m.group(1)
    written: list[Path] = []
    for s in sources:
        body = _TITLE.sub("", s.read_text(encoding="utf-8"), count=1)
        for name in re.findall(r'src="img/([^"]+)"', body):
            if not (img_dir / name).exists():
                raise FileNotFoundError(f"{s.name}: missing figure img/{name} (run the figures module)")
        canvas_path = canvas_dir / s.name
        canvas_path.write_text(to_canvas(body, image_base), encoding="utf-8")
        nav = '<a href="index.html">All guides</a>'
        preview_path = preview_dir / s.name
        preview_path.write_text(preview_page(titles[s], to_canvas(body, "../img/"), nav), encoding="utf-8")
        written += [canvas_path, preview_path]
    items = "\n".join(f'<li><a href="{s.name}">{html.escape(titles[s])}</a></li>' for s in sources)
    index = preview_dir / "index.html"
    index.write_text(preview_page("IMU study guides", f"<ol>{items}</ol>", ""), encoding="utf-8")
    written.append(index)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=Path, default=GUIDE_DIR)
    ap.add_argument("--image-base", default="",
                    help="prefix for image URLs in the Canvas output (default: bare file names)")
    args = ap.parse_args(argv)
    for p in build(args.dir, args.image_base):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
