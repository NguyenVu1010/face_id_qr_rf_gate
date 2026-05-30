"""3D-printed servo bracket for the mica gate pillar.

Holds SG90 with shaft axis along Y, tip at (X=120, Y=120, Z=150) when the
bracket sits on the BOTTOM face (Z=0) inside the trụ.

Run via FreeCAD MCP. If FreeCAD unavailable, can be regenerated later.

Spec: docs/superpowers/specs/2026-05-31-mica-gate-pillar-design.md §6
"""

import os
import FreeCAD as App
import Part

DOC_NAME = "smart_gate_servo_bracket"
OUT_DIR = os.path.join(os.path.dirname(__file__), "exports")

# SG90 envelope
SERVO_BODY_L = 22.8
SERVO_BODY_W = 12.4
SERVO_BODY_H = 22.5
SHAFT_OFFSET = 5.0  # shaft offset from one end of body

# Bracket
BASE_W = 50.0    # X direction footprint
BASE_D = 40.0    # Y direction footprint
BASE_T = 3.0     # thickness of bracket base
WALL_T = 3.0     # vertical wall thickness
TARGET_Z = 100.0  # desired shaft Z height (pivot for the 150mm drop-arm)
WALL_H = TARGET_Z - BASE_T  # vertical wall height to position servo at correct Z


def build():
    doc = App.newDocument(DOC_NAME)
    # Base plate (sits flat on BOTTOM)
    base = Part.makeBox(BASE_W, BASE_D, BASE_T,
                        App.Vector(-BASE_W / 2, -BASE_D / 2, 0))
    # Vertical wall — holds servo at correct height
    # Servo flange is fastened to the wall; servo body extends in +Y direction.
    # Wall is in X-Z plane at Y=0.
    wall = Part.makeBox(BASE_W, WALL_T, WALL_H,
                        App.Vector(-BASE_W / 2, -WALL_T / 2, BASE_T))
    bracket = base.fuse(wall)
    # Cut shaft hole in wall (Ø8mm at correct Z)
    shaft_hole = Part.makeCylinder(4.0, WALL_T + 0.2,
                                    App.Vector(0, -WALL_T / 2 - 0.1, TARGET_Z),
                                    App.Vector(0, 1, 0))
    bracket = bracket.cut(shaft_hole)
    # Cut 2 servo flange screw holes (M2.5 clearance Ø2.7)
    for offset in [-14.0, 14.0]:
        hole = Part.makeCylinder(1.35, WALL_T + 0.2,
                                  App.Vector(offset, -WALL_T / 2 - 0.1, TARGET_Z),
                                  App.Vector(0, 1, 0))
        bracket = bracket.cut(hole)
    # Cut 4 base mount holes for bonding/zip-tie attachment
    for x, y in [(-20, -15), (20, -15), (-20, 15), (20, 15)]:
        hole = Part.makeCylinder(1.6, BASE_T + 0.2, App.Vector(x, y, -0.1))
        bracket = bracket.cut(hole)
    Part.show(bracket, "servo_bracket")
    doc.recompute()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "servo_bracket.stl")
    bracket.exportStl(out_path)
    print(f"Wrote {out_path}")


build()
