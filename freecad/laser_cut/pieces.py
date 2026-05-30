"""Per-piece composition. Each builder returns a Piece with outline + cuts + engraves."""

from dataclasses import dataclass, field

from freecad.laser_cut.cutouts import (
    Shape, circle, rect, lcd_window,
    servo_cutout, hc_sr04_holes, rfid_engrave_marker,
)
from freecad.laser_cut.geometry import pentagon_outline


@dataclass
class Piece:
    name: str
    outline: list[tuple[float, float]]
    cuts: list[Shape] = field(default_factory=list)
    engraves: list[Shape] = field(default_factory=list)


def _rect_outline(w: float, h: float) -> list[tuple[float, float]]:
    return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]


def build_front() -> Piece:
    return Piece(name="FRONT", outline=_rect_outline(150.0, 370.0))


def build_back() -> Piece:
    outline = _rect_outline(150.0, 400.0)
    cuts: list[Shape] = []
    cuts.append(circle(15.0, 15.0, 5.0))  # Ø10mm adapter at (15, 15)
    for x, y in [
        (8.0, 8.0), (142.0, 8.0),
        (8.0, 392.0), (142.0, 392.0),
        (8.0, 200.0), (142.0, 200.0),
    ]:
        cuts.append(circle(x, y, 1.75))  # M3 mount Ø3.5
    return Piece(name="BACK", outline=outline, cuts=cuts)


def build_bottom() -> Piece:
    outline = _rect_outline(150.0, 120.0)
    cuts = [rect(cx=75.0, cy=y, w=30.0, h=3.0) for y in (30.0, 60.0, 90.0)]
    return Piece(name="BOTTOM", outline=outline, cuts=cuts)


def build_arm() -> Piece:
    outline = _rect_outline(150.0, 15.0)
    cuts = [
        circle(5.0, 7.5, 1.1),
        circle(13.0, 7.5, 1.1),
    ]
    return Piece(name="ARM", outline=outline, cuts=cuts)
