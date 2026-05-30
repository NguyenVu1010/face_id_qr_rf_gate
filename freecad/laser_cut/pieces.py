"""Per-piece composition. Each builder returns a Piece with outline + cuts + engraves."""

import math
from dataclasses import dataclass, field

from freecad.laser_cut.cutouts import (
    Shape, circle, rect,
    servo_cutout, hc_sr04_holes, hc_sr04_pcb_mount,
    arm_slot,
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
    # Ø10mm adapter cable entry — aligned with the J_PWR barrel axis when
    # PCB sits on LEFT-panel standoffs. Stack: 5mm LEFT panel + 5mm nylon
    # standoff + 1.6mm PCB + ~6mm to barrel center axis = X≈17.6 from the
    # LEFT face. Barrel exits toward +Y (BACK) at Y≈221.5, Z≈110.
    cuts.append(circle(17.0, 110.0, 5.0))
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
    outline = _rect_outline(150.0, 15.0)
    cuts = [
        circle(5.0, 7.5, 1.1),
        circle(13.0, 7.5, 1.1),
    ]
    # 4 engraved stripes (paint red after cutting for red/white barrier look).
    # Centers at X=30/60/90/120 with stripe width 20mm + 10mm gaps fit cleanly
    # in 150mm arm length; clear of the two M2 mount holes at X=5 and X=13.
    engraves = [rect(cx=x, cy=7.5, w=20.0, h=5.0, kind="engrave")
                for x in (30.0, 60.0, 90.0, 120.0)]
    return Piece(name="ARM", outline=outline, cuts=cuts, engraves=engraves)


def build_top() -> Piece:
    outline = _rect_outline(150.0, 168.0)
    cuts: list[Shape] = []
    cuts.append(rect(cx=75.0, cy=35.0, w=98.0, h=40.0))  # LCD window, square corners
    for x, y in [(28.5, 7.5), (121.5, 7.5), (28.5, 62.5), (121.5, 62.5)]:
        cuts.append(circle(x, y, 1.6))                    # LCD module mount holes
    # Camera tower: cable hole + 4 flange mounts. Shifted forward to Y=110 to
    # leave 50mm gap for a USB-plug pass-through behind it.
    cuts.append(circle(75.0, 110.0, 4.0))                 # camera cable Ø8mm
    for x, y in [(67.0, 102.0), (83.0, 102.0), (67.0, 118.0), (83.0, 118.0)]:
        cuts.append(circle(x, y, 1.6))                    # camera tower flange mounts
    # USB-plug pass-through. 20×12mm fits a full USB-A male plug WITH its
    # plastic housing/strain-relief (metal connector 12×4.5mm + typical
    # housing 15-18×8-10mm + 2-4mm clearance). Center 50mm behind camera
    # cable hole; 2mm margin to BACK edge of TOP.
    cuts.append(rect(cx=75.0, cy=160.0, w=20.0, h=12.0))
    return Piece(name="TOP", outline=outline, cuts=cuts)


def build_slope() -> Piece:
    # SLOPE facet has no cutouts or engravings: the RC522 RFID reader is
    # bonded to the inside surface and reads through the mica (RF passes
    # cleanly through 3-10mm acrylic — non-conductive, non-magnetic). No
    # visual marker on the outside — keeps the panel clean.
    slope_proj = 72.0
    hypotenuse = math.sqrt(slope_proj ** 2 + slope_proj ** 2)
    outline = _rect_outline(150.0, hypotenuse)
    return Piece(name="SLOPE", outline=outline)


def build_left() -> Piece:
    outline = pentagon_outline(depth=240.0, height=300.0, slope=72.0)
    cuts = [
        # 4 corner mount holes (panel → wooden corner posts)
        circle(5.0, 8.0, 1.75),
        circle(235.0, 8.0, 1.75),
        circle(235.0, 292.0, 1.75),
        circle(5.0, 213.0, 1.75),
        # 4 PCB standoff mount holes — motherboard PCB (200x120mm) sits flat
        # against inside of LEFT panel with long axis along trụ Y and short
        # axis along trụ Z. Mount holes at PCB corners (5mm inset from PCB
        # edges) at trụ (Y, Z) coords, Ø3.2mm clearance for M3 screws.
        circle(25.0, 95.0, 1.6),
        circle(215.0, 95.0, 1.6),
        circle(25.0, 205.0, 1.6),
        circle(215.0, 205.0, 1.6),
    ]
    return Piece(name="LEFT", outline=outline, cuts=cuts)


def build_right() -> Piece:
    outline = pentagon_outline(depth=240.0, height=300.0, slope=72.0)
    cuts: list[Shape] = []
    cuts.extend(hc_sr04_holes(cx=120.0, cy=40.0))            # 2 transducer Ø16, spacing 26 — lowered to Z=40
    cuts.extend(hc_sr04_pcb_mount(cx=120.0, cy=40.0))        # 4 M2 corner holes at PCB 45x20 corners
    cuts.append(arm_slot(cx=120.0, cy=190.0, h=200.0))       # arm retraction slot Z=90-290 (200mm tall, 10mm margin from top, 42mm from HC-SR04)
    return Piece(name="RIGHT", outline=outline, cuts=cuts)
