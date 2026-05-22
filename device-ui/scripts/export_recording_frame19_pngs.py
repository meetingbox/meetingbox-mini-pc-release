"""Export Frame 19 recording assets as PNG for Kivy (SVG is not reliable on device).

When Figma MCP / Framelink returns SVG, run this script to produce PNGs under
``assets/recording/figma/``. Requires ``npx`` (resvg-js-cli).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "recording" / "figma"

_EXPORTS: tuple[tuple[str, int], ...] = (
    ("frame19_vector_left.svg", 74),
    ("frame19_vector_right.svg", 74),
    ("frame19_group48.svg", 846),
    ("ellipse_17_group48.svg", 846),
    ("ellipse_17.svg", 286),
)


def _resvg(svg: Path, png: Path, fit_width: int) -> None:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise RuntimeError("npx not found — install Node.js to export PNGs")
    cmd = [
        npx,
        "--yes",
        "@resvg/resvg-js-cli",
        "--fit-width",
        str(fit_width),
        str(svg),
        str(png),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    _ASSETS.mkdir(parents=True, exist_ok=True)
    for svg_name, width in _EXPORTS:
        svg = _ASSETS / svg_name
        if not svg.is_file():
            # wave_circle export lives at recording/ until copied to figma/
            alt = _ASSETS.parent / svg_name.replace("frame19_group48", "wave_circle_bg")
            if svg_name == "frame19_group48.svg" and alt.is_file():
                svg = alt
            else:
                print(f"SKIP missing {svg}")
                continue
        png = _ASSETS / svg_name.replace(".svg", ".png")
        try:
            _resvg(svg, png, width)
            print(f"OK {png.name} ({png.stat().st_size} bytes)")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {svg_name}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
