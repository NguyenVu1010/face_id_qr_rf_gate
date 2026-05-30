"""CLI: build all pieces, render SVG + PDF, write to exports/."""

from pathlib import Path

from freecad.laser_cut.pieces import (
    build_front, build_back, build_left, build_right,
    build_top, build_slope, build_bottom, build_arm,
)
from freecad.laser_cut.layout import compute_layout
from freecad.laser_cut.render import render_svg, svg_to_pdf


def main():
    pieces = [
        build_front(), build_back(), build_left(), build_right(),
        build_top(), build_slope(), build_bottom(), build_arm(),
    ]
    positions = compute_layout()
    out_dir = Path(__file__).parent / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / "mica_gate_pillar.svg"
    pdf_path = out_dir / "mica_gate_pillar.pdf"
    render_svg(pieces, positions, svg_path)
    svg_to_pdf(svg_path, pdf_path)
    print(f"Wrote {svg_path}")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
