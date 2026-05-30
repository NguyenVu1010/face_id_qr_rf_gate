"""Cutout shape builders. Each returns a Shape (or list of Shapes) at given center."""

from dataclasses import dataclass
import math


@dataclass
class Shape:
    kind: str  # "cut" or "engrave"
    points: list[tuple[float, float]]


def circle(cx: float, cy: float, radius: float, segments: int = 16) -> Shape:
    pts = [
        (cx + radius * math.cos(2 * math.pi * i / segments),
         cy + radius * math.sin(2 * math.pi * i / segments))
        for i in range(segments)
    ]
    return Shape(kind="cut", points=pts)


def rect(cx: float, cy: float, w: float, h: float, kind: str = "cut") -> Shape:
    return Shape(kind=kind, points=[
        (cx - w / 2, cy - h / 2),
        (cx + w / 2, cy - h / 2),
        (cx + w / 2, cy + h / 2),
        (cx - w / 2, cy + h / 2),
    ])


def servo_cutout(cx: float, cy: float, shaft_d: float = 8.0,
                 flange_spacing: float = 28.0, flange_hole_d: float = 2.7) -> list[Shape]:
    return [
        circle(cx, cy, shaft_d / 2),
        circle(cx - flange_spacing / 2, cy, flange_hole_d / 2),
        circle(cx + flange_spacing / 2, cy, flange_hole_d / 2),
    ]


def hc_sr04_holes(cx: float, cy: float, spacing: float = 26.0,
                   radius: float = 8.0) -> list[Shape]:
    """HC-SR04 transducer through-holes. Datasheet PCB is 45x20mm with two
    Ø16mm transducer cylinders, center-to-center spacing 26mm.
    """
    return [
        circle(cx - spacing / 2, cy, radius),
        circle(cx + spacing / 2, cy, radius),
    ]


def hc_sr04_pcb_mount(cx: float, cy: float) -> list[Shape]:
    """4× Ø2.2mm M2-clearance holes at the corners of a 45x20mm HC-SR04 PCB.
    cx/cy = center of the PCB on the panel (matches `hc_sr04_holes` cx/cy).
    Hole positions follow board-local corners (2,2), (43,2), (2,18), (43,18),
    i.e. 41mm × 16mm spacing.
    """
    return [
        circle(cx - 20.5, cy - 8.0, 1.1),
        circle(cx + 20.5, cy - 8.0, 1.1),
        circle(cx - 20.5, cy + 8.0, 1.1),
        circle(cx + 20.5, cy + 8.0, 1.1),
    ]


def arm_slot(cx: float, cy: float, w: float = 20.0, h: float = 130.0) -> Shape:
    """Vertical slot for the drop-arm to retract through.
    cx/cy = center of slot. w (Y direction on the face) × h (Z direction on the face).
    """
    return rect(cx, cy, w, h, kind="cut")


def rfid_engrave_marker(cx: float, cy: float, w: float = 50.0, h: float = 30.0) -> Shape:
    return rect(cx, cy, w, h, kind="engrave")
