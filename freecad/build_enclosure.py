"""Build smart_gate enclosure (box body + connector plate + lid).

Run via FreeCAD MCP (mcp__freecad__execute_code), not standalone Python.
Reads parameters from this module; produces freecad/smart_gate_enclosure.FCStd.

Spec: docs/superpowers/specs/2026-05-23-smart-gate-enclosure-design.md
Plan: docs/superpowers/plans/2026-05-23-smart-gate-enclosure.md
"""

import os
import FreeCAD as App
import Part

# === Box dimensions (mm) ===
INNER_W = 205.0
INNER_D = 130.0
INNER_H = 64.0   # from floor top to lid bottom
WALL = 2.5
FLOOR_T = 2.5
LID_T = 3.5
OUTER_W = INNER_W + 2 * WALL   # 210
OUTER_D = INNER_D + 2 * WALL   # 135
BOX_H = INNER_H + FLOOR_T      # 66.5 (top of side walls)
TOTAL_H = BOX_H + LID_T        # 70.0 (top of closed lid)

# === PCB (extracted from smart_gate_combined.kicad_pcb) ===
PCB_W = 201.74
PCB_D = 119.62
PCB_T = 1.6
PCB_OX = WALL + (INNER_W - PCB_W) / 2   # 4.13
PCB_OY = WALL + (INNER_D - PCB_D) / 2   # 7.69

# === PCB connector positions (board-local coords) ===
J_PWR_X, J_PWR_Y = 12.46, 19.68
J_PI_X, J_PI_Y = 108.06, 91.76   # rot=180°, socket along Y axis
J_LCD_X, J_LCD_Y = 186.80, 57.48

# === Pi 4B mechanical ===
# With J_PI rot=180°, Pi-LEFT (USB-C side) maps to mb SOUTH, Pi-RIGHT maps to mb NORTH
PI_GPIO_OFFSET = 3.5

# === Vertical (Z) stack ===
STANDOFF_H = 4.5
SOCKET_H = 11.0          # J_PI 2x20 socket pin + housing
PI_PCB_T = 1.4
PI_USB_H = 15.6

# Pi top of PCB / top of USB
PI_PCB_TOP_Z = FLOOR_T + STANDOFF_H + PCB_T + SOCKET_H + PI_PCB_T   # 21.0
PI_USB_TOP_Z = PI_PCB_TOP_Z + PI_USB_H                              # 36.6
PI_USB_BOT_Z = PI_PCB_TOP_Z                                         # 21.0

# === Fastener dimensions ===
STANDOFF_R = 3.0
STANDOFF_PILOT_R = 1.35
PILLAR_SIZE = 7.0          # 7×7mm — small enough to avoid PCB corner overlap
HEAT_SET_HOLE_R = 2.1
HEAT_SET_DEPTH = 5.5

# === Connector cutout positions (derived) ===
PI_BOX_X_MIN = PCB_OX + 104.56   # 108.69
PI_BOX_X_MAX = PCB_OX + 160.56   # 164.69
PI_BOX_Y_MIN = PCB_OY + 10.26    # 17.95 (Pi NORTH edge)
PI_BOX_Y_MAX = PCB_OY + 95.26    # 102.95 (Pi SOUTH edge)

ETH_X = PCB_OX + 115.56          # 119.69
USB3_X = PCB_OX + 129.56         # 133.69
USB2_X = PCB_OX + 146.56         # 150.69
USBC_X = PCB_OX + 115.56         # 119.69

# === Output ===
PROJECT_DIR = '/home/nguyenvd/workspace/smart_gate'
FCSTD_PATH = os.path.join(PROJECT_DIR, 'freecad', 'smart_gate_enclosure.FCStd')
PCB_STEP_PATH = os.path.join(PROJECT_DIR, '3d', 'smart_gate_combined.step')

# === Fillet radii ===
CORNER_FILLET_R = 2.0      # outer vertical corner edges (small to avoid fillet failure)
LID_FILLET_R = 2.0         # lid top/bottom corner edges
PLATE_FILLET_R = 1.5       # connector plate corners


def fillet_vertical_edges_at(shape, corners_xy, radius, tol=0.01):
    """Fillet all Z-parallel edges whose XY position matches any of the given corners."""
    edges_to_fillet = []
    for edge in shape.Edges:
        if not isinstance(edge.Curve, Part.Line):
            continue
        v1 = edge.Vertexes[0].Point
        v2 = edge.Vertexes[1].Point
        d = v2 - v1
        if abs(d.x) >= tol or abs(d.y) >= tol:
            continue   # not Z-parallel
        for (cx, cy) in corners_xy:
            if abs(v1.x - cx) < tol and abs(v1.y - cy) < tol:
                edges_to_fillet.append(edge)
                break
    if edges_to_fillet:
        try:
            return shape.makeFillet(radius, edges_to_fillet)
        except Exception as e:
            print(f'  WARN: fillet failed ({e}); returning unfilleted shape')
    return shape


def fillet_horizontal_edges_at(shape, corner_z_pairs, radius, tol=0.01):
    """Fillet outer-rectangle edges in XY plane at given Z values.
    corner_z_pairs: list of Z values where the rectangle perimeter sits."""
    edges_to_fillet = []
    for edge in shape.Edges:
        if not isinstance(edge.Curve, Part.Line):
            continue
        v1 = edge.Vertexes[0].Point
        v2 = edge.Vertexes[1].Point
        d = v2 - v1
        if abs(d.z) >= tol:
            continue   # not horizontal
        if abs(v1.z - v2.z) >= tol:
            continue
        for cz in corner_z_pairs:
            if abs(v1.z - cz) < tol:
                edges_to_fillet.append(edge)
                break
    if edges_to_fillet:
        try:
            return shape.makeFillet(radius, edges_to_fillet)
        except Exception as e:
            print(f'  WARN: fillet failed ({e}); returning unfilleted shape')
    return shape


def build_box_body(doc):
    """Floor + 3 walls (S/E/W) + 5mm north frame + 4 pillars + 4 standoffs + cutouts."""
    outer = Part.makeBox(OUTER_W, OUTER_D, BOX_H)
    inner = Part.makeBox(INNER_W, INNER_D, INNER_H,
                         App.Vector(WALL, WALL, FLOOR_T))
    box = outer.cut(inner)

    # Remove north wall above 5mm frame height
    FRAME_H = 5.0
    north_cut = Part.makeBox(OUTER_W, WALL, BOX_H - FLOOR_T - FRAME_H,
                              App.Vector(0, 0, FLOOR_T + FRAME_H))
    box = box.cut(north_cut)

    # 4 corner pillars
    pillar_corners = [(0, 0), (OUTER_W - PILLAR_SIZE, 0),
                      (0, OUTER_D - PILLAR_SIZE),
                      (OUTER_W - PILLAR_SIZE, OUTER_D - PILLAR_SIZE)]
    for (px, py) in pillar_corners:
        pillar = Part.makeBox(PILLAR_SIZE, PILLAR_SIZE, BOX_H,
                              App.Vector(px, py, 0))
        box = box.fuse(pillar)
        # Heat-set insert hole (top-down)
        hole_x = px + PILLAR_SIZE / 2
        hole_y = py + PILLAR_SIZE / 2
        insert = Part.makeCylinder(HEAT_SET_HOLE_R, HEAT_SET_DEPTH,
                                    App.Vector(hole_x, hole_y,
                                               BOX_H - HEAT_SET_DEPTH))
        box = box.cut(insert)

    # North-frame heat-set inserts for plate mount (4 along the 5mm frame, top-down on frame)
    plate_mount_xs = [10, OUTER_W / 3, OUTER_W * 2 / 3, OUTER_W - 10]
    for px in plate_mount_xs:
        insert = Part.makeCylinder(HEAT_SET_HOLE_R, HEAT_SET_DEPTH,
                                    App.Vector(px, WALL / 2,
                                               FLOOR_T + FRAME_H - HEAT_SET_DEPTH))
        box = box.cut(insert)

    # 4 PCB mount standoffs
    standoff_positions = [
        (PCB_OX + 5, PCB_OY + 5),
        (PCB_OX + PCB_W - 5, PCB_OY + 5),
        (PCB_OX + 5, PCB_OY + PCB_D - 5),
        (PCB_OX + PCB_W - 5, PCB_OY + PCB_D - 5),
    ]
    for (sx, sy) in standoff_positions:
        post = Part.makeCylinder(STANDOFF_R, STANDOFF_H,
                                  App.Vector(sx, sy, FLOOR_T))
        pilot = Part.makeCylinder(STANDOFF_PILOT_R, STANDOFF_H + 0.1,
                                   App.Vector(sx, sy, FLOOR_T - 0.05))
        box = box.fuse(post.cut(pilot))

    # === Cutouts (swapped per user request: DC on EAST, peripherals on WEST) ===
    # 1. DC jack on EAST wall (X=OUTER_W) — round Ø11mm
    # Cable runs internally from J_PWR (near PCB west edge) east to wall
    dc_z = FLOOR_T + STANDOFF_H + PCB_T + 6.0   # 2.5+4.5+1.6+6 = 14.6mm
    dc_y = PCB_OY + J_PWR_Y        # same Y as PCB header
    dc = Part.makeCylinder(11.0 / 2 + 0.25, WALL + 2)
    dc.Placement = App.Placement(
        App.Vector(OUTER_W - WALL - 1, dc_y, dc_z),
        App.Rotation(App.Vector(0, 1, 0), 90))
    box = box.cut(dc)

    # 2. USB-C cable hole on SOUTH wall — oval 12x6
    usbc_w, usbc_h = 12.0, 6.0
    usbc_z = PI_PCB_TOP_Z + 7   # ~28mm
    usbc = Part.makeBox(usbc_w, WALL + 2, usbc_h,
                        App.Vector(USBC_X - usbc_w / 2,
                                   OUTER_D - WALL - 1,
                                   usbc_z - usbc_h / 2))
    box = box.cut(usbc)

    # 3. Peripheral wire exit slots on WEST wall (X=0) — 4 slots, 15x10mm each
    slot_w, slot_h = 15.0, 10.0    # Y (along wall) x Z (vertical, reduced per user)
    slot_z = PI_PCB_TOP_Z + 18     # 39mm above floor
    for slot_y in [25, 55, 80, 105]:
        slot = Part.makeBox(WALL + 2, slot_w, slot_h,
                            App.Vector(-1,
                                       slot_y - slot_w / 2,
                                       slot_z - slot_h / 2))
        box = box.cut(slot)

    # (Pillar 7×7 now small enough — no notch needed at PCB level)

    # === Chamfer outer vertical corner edges (chamfer more reliable than fillet
    # for complex geometry with pillars and cuts) ===
    outer_corners_xy = [(0, 0), (OUTER_W, 0), (0, OUTER_D), (OUTER_W, OUTER_D)]
    chamfer_edges = []
    for edge in box.Edges:
        if not isinstance(edge.Curve, Part.Line):
            continue
        v1 = edge.Vertexes[0].Point
        v2 = edge.Vertexes[1].Point
        if abs(v1.x - v2.x) > 0.01 or abs(v1.y - v2.y) > 0.01:
            continue   # not Z-parallel
        for (cx, cy) in outer_corners_xy:
            if abs(v1.x - cx) < 0.01 and abs(v1.y - cy) < 0.01:
                chamfer_edges.append(edge)
                break
    if chamfer_edges:
        try:
            box = box.makeChamfer(CORNER_FILLET_R, chamfer_edges)
            print(f'  Chamfered {len(chamfer_edges)} box corner edges (size {CORNER_FILLET_R}mm)')
        except Exception as e:
            print(f'  WARN: box chamfer failed ({e}); leaving sharp corners')

    feat = doc.addObject('Part::Feature', 'EnclosureBox')
    feat.Shape = box
    feat.ViewObject.ShapeColor = (0.85, 0.85, 0.85, 1.0)
    return feat


def build_connector_plate(doc):
    """North-wall removable plate 210 x 2.5 x ~60mm with Pi USB cluster cutout.

    Positioned offset 25mm above box for visualization (so both parts visible).
    """
    PLATE_W = OUTER_W
    FRAME_H = 5.0
    PLATE_H = BOX_H - FLOOR_T - FRAME_H   # 59
    PLATE_T = WALL
    LIFTED_Y = -PLATE_T - 25.0

    plate = Part.makeBox(PLATE_W, PLATE_T, PLATE_H,
                         App.Vector(0, LIFTED_Y, FLOOR_T + FRAME_H))

    # Pi USB cluster opening: 50×18 centered at (cluster_x, cluster_z)
    cluster_w = 50.0
    cluster_h = 18.0
    cluster_x = ETH_X - 11    # ~108.7
    cluster_z = PI_USB_BOT_Z  # 21.0
    cluster = Part.makeBox(cluster_w, PLATE_T + 2, cluster_h,
                           App.Vector(cluster_x,
                                      LIFTED_Y - 1,
                                      cluster_z))
    plate = plate.cut(cluster)

    # 4× M3 clearance holes Ø3.2
    plate_mount_xs = [10, OUTER_W / 3, OUTER_W * 2 / 3, OUTER_W - 10]
    for px in plate_mount_xs:
        # Hole at top of plate (mating with north-frame heat-set inserts)
        hole = Part.makeCylinder(1.6, PLATE_T + 2)
        hole.Placement = App.Placement(
            App.Vector(px, LIFTED_Y - 1, FLOOR_T + FRAME_H - 0.5),
            App.Rotation(App.Vector(1, 0, 0), -90))
        # Actually for vertical screw into frame top, hole axis is +Z
        # Redo: axis along Z, hole through plate at bottom 4mm height
        hole_v = Part.makeCylinder(1.6, FRAME_H,
                                    App.Vector(px, LIFTED_Y + PLATE_T / 2,
                                               FLOOR_T))
        # Skip horizontal hole — use vertical hole through plate-frame overlap area
        # Actually plate sits IN FRONT of the frame, screws go horizontally
        # Reconsider: screws should go HORIZONTALLY (+Y direction) through plate into frame
        hole_h = Part.makeCylinder(1.6, PLATE_T + 2)
        hole_h.Placement = App.Placement(
            App.Vector(px, LIFTED_Y - 1, FLOOR_T + FRAME_H / 2),
            App.Rotation(App.Vector(1, 0, 0), -90))
        plate = plate.cut(hole_h)

    feat = doc.addObject('Part::Feature', 'ConnectorPlate')
    feat.Shape = plate
    feat.ViewObject.ShapeColor = (0.6, 0.8, 0.9, 1.0)
    return feat


def build_lid(doc):
    """Lid 210×135×3.5 with LCD viewing window + 4 LCD mounts + 4 corner screws.

    Positioned 25mm above closed position for visualization.
    """
    LIFTED_Z = 25.0
    LID_BASE_Z = BOX_H + LIFTED_Z
    lid = Part.makeBox(OUTER_W, OUTER_D, LID_T,
                       App.Vector(0, 0, LID_BASE_Z))

    # LCD viewing cutout 98×40mm centered at (105, 67.5), corners filleted
    lcd_w, lcd_h = 98.0, 40.0
    lcd_cx, lcd_cy = 105.0, 67.5
    lcd_cut = Part.makeBox(lcd_w, lcd_h, LID_T + 0.2,
                           App.Vector(lcd_cx - lcd_w / 2,
                                      lcd_cy - lcd_h / 2,
                                      LID_BASE_Z - 0.1))
    # Round the 4 corner edges (Z-parallel) of the LCD cutout
    lcd_corners = [
        (lcd_cx - lcd_w / 2, lcd_cy - lcd_h / 2),
        (lcd_cx + lcd_w / 2, lcd_cy - lcd_h / 2),
        (lcd_cx - lcd_w / 2, lcd_cy + lcd_h / 2),
        (lcd_cx + lcd_w / 2, lcd_cy + lcd_h / 2),
    ]
    lcd_cut = fillet_vertical_edges_at(lcd_cut, lcd_corners, 4.0)
    lid = lid.cut(lcd_cut)

    # 4 LCD mount holes (Ø2.7 self-tap pilot)
    LCD_MOUNT_DX = 93.0
    LCD_MOUNT_DY = 55.0
    for (mx, my) in [
        (lcd_cx - LCD_MOUNT_DX / 2, lcd_cy - LCD_MOUNT_DY / 2),
        (lcd_cx + LCD_MOUNT_DX / 2, lcd_cy - LCD_MOUNT_DY / 2),
        (lcd_cx - LCD_MOUNT_DX / 2, lcd_cy + LCD_MOUNT_DY / 2),
        (lcd_cx + LCD_MOUNT_DX / 2, lcd_cy + LCD_MOUNT_DY / 2),
    ]:
        pilot = Part.makeCylinder(1.35, LID_T + 0.2,
                                   App.Vector(mx, my, LID_BASE_Z - 0.1))
        lid = lid.cut(pilot)

    # 4 corner screw holes Ø3.2
    for (cx, cy) in [
        (PILLAR_SIZE / 2, PILLAR_SIZE / 2),
        (OUTER_W - PILLAR_SIZE / 2, PILLAR_SIZE / 2),
        (PILLAR_SIZE / 2, OUTER_D - PILLAR_SIZE / 2),
        (OUTER_W - PILLAR_SIZE / 2, OUTER_D - PILLAR_SIZE / 2),
    ]:
        clear = Part.makeCylinder(1.6, LID_T + 0.2,
                                   App.Vector(cx, cy, LID_BASE_Z - 0.1))
        lid = lid.cut(clear)

    # === Fillet lid corner edges (vertical at corners) ===
    lid_corners_xy = [(0, 0), (OUTER_W, 0), (0, OUTER_D), (OUTER_W, OUTER_D)]
    lid = fillet_vertical_edges_at(lid, lid_corners_xy, LID_FILLET_R)

    feat = doc.addObject('Part::Feature', 'EnclosureLid')
    feat.Shape = lid
    feat.ViewObject.ShapeColor = (0.7, 0.85, 0.95, 1.0)
    return feat


def import_pcb(doc):
    """Import the motherboard PCB STEP file and position it on top of standoffs.

    KiCad-exported STEP uses the kicad-canvas origin; translate so the PCB
    board-bottom-left aligns with (PCB_OX, PCB_OY, FLOOR_T+STANDOFF_H) in box.
    """
    if not os.path.exists(PCB_STEP_PATH):
        print(f'  PCB STEP not found at {PCB_STEP_PATH}; skipping')
        return None
    shape = Part.read(PCB_STEP_PATH)
    bb = shape.BoundBox
    print(f'  PCB STEP raw bbox: X=[{bb.XMin:.1f}, {bb.XMax:.1f}], '
          f'Y=[{bb.YMin:.1f}, {bb.YMax:.1f}], Z=[{bb.ZMin:.1f}, {bb.ZMax:.1f}]')

    # KiCad-exported STEP has Y axis flipped AND X orientation that doesn't
    # match my cutout convention. Rotate 180° around Z axis (mirror both X+Y)
    # so J_PWR ends up near east wall (matching its DC jack cutout at box-X=210).
    shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 180)
    bb = shape.BoundBox

    # Translate so rotated PCB bbox bottom-left → (PCB_OX, PCB_OY, FLOOR_T+STANDOFF_H)
    dx = PCB_OX - bb.XMin
    dy = PCB_OY - bb.YMin
    dz = (FLOOR_T + STANDOFF_H) - bb.ZMin
    shape.translate(App.Vector(dx, dy, dz))

    feat = doc.addObject('Part::Feature', 'MotherboardPCB')
    feat.Shape = shape
    feat.ViewObject.ShapeColor = (0.05, 0.4, 0.1, 1.0)   # PCB green
    feat.ViewObject.Transparency = 0
    return feat


def main():
    if 'smart_gate_enclosure' in [d.Name for d in App.listDocuments().values()]:
        App.closeDocument('smart_gate_enclosure')
    doc = App.newDocument('smart_gate_enclosure')

    box = build_box_body(doc)
    plate = build_connector_plate(doc)
    lid = build_lid(doc)
    pcb = import_pcb(doc)

    print(f'Box bbox: X=[{box.Shape.BoundBox.XMin:.1f}, {box.Shape.BoundBox.XMax:.1f}], '
          f'Y=[{box.Shape.BoundBox.YMin:.1f}, {box.Shape.BoundBox.YMax:.1f}], '
          f'Z=[{box.Shape.BoundBox.ZMin:.1f}, {box.Shape.BoundBox.ZMax:.1f}]')
    print(f'  Box volume:   {box.Shape.Volume:.0f} mm^3')
    print(f'  Plate volume: {plate.Shape.Volume:.0f} mm^3')
    print(f'  Lid volume:   {lid.Shape.Volume:.0f} mm^3')

    doc.recompute()
    doc.saveAs(FCSTD_PATH)
    print(f'Saved {FCSTD_PATH}')

    # STL export (only the 3 printed parts, not the imported PCB)
    import Mesh
    EXPORT_DIR = os.path.join(PROJECT_DIR, 'freecad', 'exports')
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for feat, fname in [(box, 'box_body.stl'),
                        (plate, 'connector_plate.stl'),
                        (lid, 'lid.stl')]:
        if feat is None:
            continue
        out = os.path.join(EXPORT_DIR, fname)
        Mesh.export([feat], out)
        size_kb = os.path.getsize(out) / 1024
        print(f'  Exported {fname} ({size_kb:.0f} KB)')

    return doc


main()
