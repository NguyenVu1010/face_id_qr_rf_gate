"""Render pieces to SVG + convert to PDF."""

from pathlib import Path

import svgwrite
import cairosvg

from freecad.laser_cut.pieces import Piece
from freecad.laser_cut.cutouts import Shape
from freecad.laser_cut.layout import SHEET_W, SHEET_H


CUT_COLOR = "#ff0000"
ENGRAVE_COLOR = "#000000"
CUT_STROKE = "0.3"
ENGRAVE_STROKE = "0.5"


def _polyline_d(points: list[tuple[float, float]], close: bool = True) -> str:
    if not points:
        return ""
    cmds = [f"M {points[0][0]:.3f},{points[0][1]:.3f}"]
    for x, y in points[1:]:
        cmds.append(f"L {x:.3f},{y:.3f}")
    if close:
        cmds.append("Z")
    return " ".join(cmds)


def _to_svg_y(y: float) -> float:
    """Flip Y so math-convention bottom-left origin renders with bottom at sheet bottom."""
    return SHEET_H - y


def _draw_shape(dwg: svgwrite.Drawing, shape: Shape, offset: tuple[float, float]):
    ox, oy = offset
    shifted = [(p[0] + ox, _to_svg_y(p[1] + oy)) for p in shape.points]
    color = CUT_COLOR if shape.kind == "cut" else ENGRAVE_COLOR
    stroke = CUT_STROKE if shape.kind == "cut" else ENGRAVE_STROKE
    dwg.add(dwg.path(d=_polyline_d(shifted), stroke=color, stroke_width=stroke,
                     fill="none", fill_rule="evenodd"))


def _draw_label(dwg: svgwrite.Drawing, name: str, offset: tuple[float, float],
                outline: list[tuple[float, float]]):
    ox, oy = offset
    xs = [p[0] + ox for p in outline]
    ys = [p[1] + oy for p in outline]
    cx = min(xs) + 5.0
    cy = _to_svg_y(max(ys) - 5.0)
    dwg.add(dwg.text(name, insert=(cx, cy), fill=ENGRAVE_COLOR,
                     font_size="6px", font_family="sans-serif"))


def render_svg(pieces: list[Piece], positions: dict[str, tuple[float, float]],
               output_path: Path, include_labels: bool = False):
    """Render all pieces to an SVG file.

    `include_labels=False` (default) omits the piece-name text labels so the
    laser cutter sees only geometry (some laser CAM tools interpret <text> as
    extra engrave paths and can mis-process them). Set True only when
    generating a human-readable proof; pass that proof file to the user, not
    to the shop.
    """
    dwg = svgwrite.Drawing(
        str(output_path),
        size=(f"{SHEET_W}mm", f"{SHEET_H}mm"),
        viewBox=f"0 0 {SHEET_W} {SHEET_H}",
    )
    for piece in pieces:
        offset = positions[piece.name]
        outline_shape = Shape(kind="cut", points=piece.outline)
        _draw_shape(dwg, outline_shape, offset)
        for cut in piece.cuts:
            _draw_shape(dwg, cut, offset)
        for eng in piece.engraves:
            _draw_shape(dwg, eng, offset)
        if include_labels:
            _draw_label(dwg, piece.name, offset, piece.outline)
    dwg.save()


def svg_to_pdf(svg_path: Path, pdf_path: Path):
    cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
