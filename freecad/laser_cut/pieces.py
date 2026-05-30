"""Per-piece composition. Each builder returns a Piece with outline + cuts + engraves."""

import math
from dataclasses import dataclass, field

from freecad.laser_cut.cutouts import (
    Shape, circle, rect,
    servo_cutout, hc_sr04_holes, hc_sr04_pcb_mount,
    rfid_engrave_marker, arm_slot,
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
    return Piece(name="FRONT", outline=_rect_outline(150.0, 228.0))


def build_back() -> Piece:
    outline = _rect_outline(150.0, 300.0)
    cuts: list[Shape] = []
    cuts.append(circle(15.0, 15.0, 5.0))  # Ø10mm adapter at (15, 15)
    for x, y in [
        (8.0, 8.0), (142.0, 8.0),
        (8.0, 292.0), (142.0, 292.0),
        (8.0, 150.0), (142.0, 150.0),
    ]:
        cuts.append(circle(x, y, 1.75))  # M3 mount Ø3.5
    return Piece(name="BACK", outline=outline, cuts=cuts)


def build_bottom() -> Piece:
    outline = _rect_outline(150.0, 240.0)
    cuts = [rect(cx=75.0, cy=y, w=30.0, h=3.0) for y in (40.0, 80.0, 120.0, 160.0, 200.0)]
    return Piece(name="BOTTOM", outline=outline, cuts=cuts)


def build_arm() -> Piece:
    outline = _rect_outline(200.0, 15.0)
    cuts = [
        circle(5.0, 7.5, 1.1),
        circle(13.0, 7.5, 1.1),
    ]
    # 5 engraved stripes (paint red after cutting for red/white barrier look).
    # Centers at X=35..185 with stripe width 20mm leave 5mm margins inside the
    # arm (avoids extending past arm length 200mm) and clear the two mount
    # holes at X=5/X=13.
    engraves = [rect(cx=x, cy=7.5, w=20.0, h=10.0, kind="engrave")
                for x in (35.0, 75.0, 115.0, 155.0, 185.0)]
    return Piece(name="ARM", outline=outline, cuts=cuts, engraves=engraves)


def build_top() -> Piece:
    outline = _rect_outline(150.0, 168.0)
    cuts: list[Shape] = []
    cuts.append(rect(cx=75.0, cy=35.0, w=98.0, h=40.0))  # LCD window, square corners
    for x, y in [(28.5, 7.5), (121.5, 7.5), (28.5, 62.5), (121.5, 62.5)]:
        cuts.append(circle(x, y, 1.6))
    cuts.append(circle(75.0, 120.0, 4.0))  # camera cable Ø8
    for x, y in [(67.0, 112.0), (83.0, 112.0), (67.0, 128.0), (83.0, 128.0)]:
        cuts.append(circle(x, y, 1.6))
    return Piece(name="TOP", outline=outline, cuts=cuts)


def build_slope() -> Piece:
    slope_proj = 72.0
    hypotenuse = math.sqrt(slope_proj ** 2 + slope_proj ** 2)
    outline = _rect_outline(150.0, hypotenuse)
    engraves = [rfid_engrave_marker(cx=75.0, cy=hypotenuse / 2, w=60.0, h=35.0)]
    return Piece(name="SLOPE", outline=outline, engraves=engraves)


def build_left() -> Piece:
    outline = pentagon_outline(depth=240.0, height=300.0, slope=72.0)
    cuts = [
        circle(5.0, 8.0, 1.75),
        circle(235.0, 8.0, 1.75),
        circle(235.0, 292.0, 1.75),
        circle(5.0, 213.0, 1.75),
    ]
    return Piece(name="LEFT", outline=outline, cuts=cuts)


def build_right() -> Piece:
    outline = pentagon_outline(depth=240.0, height=300.0, slope=72.0)
    cuts: list[Shape] = []
    cuts.extend(hc_sr04_holes(cx=120.0, cy=80.0))            # 2 transducer Ø16, spacing 26
    cuts.extend(hc_sr04_pcb_mount(cx=120.0, cy=80.0))        # 4 M2 corner holes at PCB 45x20 corners
    cuts.append(arm_slot(cx=120.0, cy=215.0))                # arm retraction slot
    return Piece(name="RIGHT", outline=outline, cuts=cuts)
