"""Build the camera tower (3D-printed) for the mica gate pillar.

Run via FreeCAD MCP (mcp__freecad__execute_code), not standalone Python.

Spec: docs/superpowers/specs/2026-05-31-mica-gate-pillar-design.md §6, §13.4

Geometry:
- Cylinder Ø20mm × 120mm tall (hollow, Ø14mm inner for USB cable + webcam routing)
- Base flange Ø50mm × 3mm with Ø8mm central cable bore
- 4× M3 clearance Ø3.2mm holes on flange at 22mm-side inscribed square corners
"""

import os
import FreeCAD as App
import Part

DOC_NAME = "smart_gate_camera_tower"
OUT_DIR = os.path.join(os.path.dirname(__file__), "exports")

CYL_OD = 20.0
CYL_ID = 14.0
CYL_H = 120.0
FLANGE_OD = 50.0
FLANGE_T = 3.0
CABLE_BORE = 8.0
MOUNT_HOLE_D = 3.2
MOUNT_SQUARE = 22.0


def build():
    doc = App.newDocument(DOC_NAME)
    outer = Part.makeCylinder(CYL_OD / 2, CYL_H + FLANGE_T)
    inner = Part.makeCylinder(CYL_ID / 2, CYL_H + FLANGE_T + 0.1, App.Vector(0, 0, -0.05))
    tower = outer.cut(inner)
    flange_disc = Part.makeCylinder(FLANGE_OD / 2, FLANGE_T)
    flange_bore = Part.makeCylinder(CABLE_BORE / 2, FLANGE_T + 0.2, App.Vector(0, 0, -0.1))
    flange = flange_disc.cut(flange_bore)
    half = MOUNT_SQUARE / 2
    for x, y in [(-half, -half), (half, -half), (half, half), (-half, half)]:
        hole = Part.makeCylinder(MOUNT_HOLE_D / 2, FLANGE_T + 0.2,
                                  App.Vector(x, y, -0.1))
        flange = flange.cut(hole)
    final = flange.fuse(tower)
    Part.show(final, "camera_tower")
    doc.recompute()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "camera_tower.stl")
    final.exportStl(out_path)
    print(f"Wrote {out_path}")


build()
