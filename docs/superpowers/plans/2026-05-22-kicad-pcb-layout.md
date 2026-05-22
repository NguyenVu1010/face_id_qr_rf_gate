# KiCad PCB Layout Implementation Plan — ESP32 Carrier Board

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Mixed workflow:** placement is scripted via pcbnew Python API (autonomous); routing is GUI (FreeRouting auto-router preferred); validation via KiCad MCP.

**Goal:** Produce a fabricated-ready 2-layer KiCad PCB layout for the ESP32 carrier board. Output: `smart_gate_carrier.kicad_pcb` (routed, DRC-clean) + gerbers + drill files + STEP 3D model for FreeCAD verification.

**Architecture:** 2-layer FR4, 1.6 mm thickness. Board outline ≈ 150×80 mm (fits comfortably in the 200×100 mm internal base box per spec §6, leaving ~25 mm cable clearance each side). DC barrel jack on left edge; peripheral pin headers on right edge oriented for cables exiting to the outside of the base box; ESP32 DevKit socket centered with USB connector facing the back panel cutout. 4× M3 mounting holes at corners for board-to-base-box standoffs.

**Tech Stack:** KiCad 6.0.2 (Pcbnew), pcbnew Python API for scripted placement, FreeRouting (Java jar) for auto-routing, kicad MCP for validation.

**Spec source:** `docs/superpowers/specs/2026-05-21-smart-gate-architecture-design.md` — §5 pins, §6 mechanical.
**Netlist source:** `kicad/smart_gate_carrier/smart_gate_carrier.net` (already imported per previous plan).

**Project location:** `/home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier/`

---

## Board layout zones (top view)

```
   ┌──────────────────────────────────────────────────────────────────┐
   │ ⊕                                                              ⊕ │  ← top edge
   │                                                                  │
   │  ┌─────────┐  ┌──────┐    ┌────────────────┐    ┌─────┐  ┌────┐ │
   │  │  J_PWR  │  │D_REV │    │   J_ESP_L      │    │J_RFID│ │J_LCD│ │
   │  │ DC jack │  │      │    │  (DevKit L)    │    │RC522 │ │  ↑  │ │
   │  └─────────┘  └──────┘    │   1×15 socket  │    │ 1×8  │ │ 1×4 │ │
   │   ┌─────┐                 │                │    └─────┘  └────┘ │
   │   │CBULK│   ┌─────┐       │                │    ┌─────┐  ┌────┐ │
   │   └─────┘   │J_BUCK│      │   J_ESP_R      │    │J_USR │ │J_SVO│ │
   │             │buck  │      │  (DevKit R)    │    │HC-SR04│ │servo│ │
   │             │4 pin │      │   1×15 socket  │    │ 1×4  │ │ 1×3 │ │
   │             └─────┘       └────────────────┘    └─────┘  └────┘ │
   │   ┌─────┐                                                       │
   │   │U_LDO│   ┌─────┐    ┌────────┐  ┌───────┐    ┌─────┐  ┌────┐ │
   │   │ +caps   │J_EXP │   │ I2C    │  │ R_USR1│    │ Q_BUZ│ │J_BUZ│ │
   │   └─────┘   │ 1×6 │    │ pull-up│  │ R_USR2│    │R_BUZ │ │buzz │ │
   │             └─────┘    └────────┘  └───────┘    └─────┘  └────┘ │
   │                                                                  │
   │ ⊕                                                              ⊕ │  ← bottom edge
   └──────────────────────────────────────────────────────────────────┘
                 ↑                                            ↑
            DC jack edge                                Header edge
            (cables out left)                          (cables out right)
   ⊕ = M3 mounting hole (4 corners)
   150 × 80 mm board outline
```

---

## File Structure

```
kicad/smart_gate_carrier/
├── smart_gate_carrier.kicad_pro          (existing)
├── smart_gate_carrier.kicad_pcb          (modified by scripts + GUI)
├── smart_gate_carrier.net                (existing)
├── build_scripts/
│   ├── build_carrier.py                  (existing - schematic netlist)
│   ├── place_components.py               (NEW - scripted placement)
│   ├── add_outline_and_mounts.py         (NEW - board outline + M3 holes)
│   └── export_artifacts.py               (NEW - gerber/drill/STEP export)
├── gerber/                               (output, gitignored)
└── 3d/
    └── smart_gate_carrier.step           (output for FreeCAD)
```

---

## Tasks

### Task 1: Define placement coordinates and pcbnew helper module

**Files:**
- Create: `kicad/smart_gate_carrier/build_scripts/pcb_common.py`

- [ ] **Step 1: Write the helper module with placement coordinates**

```python
# build_scripts/pcb_common.py
"""Shared constants and helpers for PCB layout scripts."""

import pcbnew
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB_FILE = os.path.join(PROJECT_DIR, 'smart_gate_carrier.kicad_pcb')

# Board outline (mm)
BOARD_W = 150.0
BOARD_H = 80.0
BOARD_ORIGIN_X = 100.0   # pcbnew uses page coords; offset board into A4 sheet
BOARD_ORIGIN_Y = 100.0

# Mounting holes (M3, 3.2 mm hole, 6 mm pad/keepout)
MOUNT_OFFSET = 4.0     # from board edge
MOUNT_HOLES = [
    (BOARD_ORIGIN_X + MOUNT_OFFSET,             BOARD_ORIGIN_Y + MOUNT_OFFSET),
    (BOARD_ORIGIN_X + BOARD_W - MOUNT_OFFSET,   BOARD_ORIGIN_Y + MOUNT_OFFSET),
    (BOARD_ORIGIN_X + MOUNT_OFFSET,             BOARD_ORIGIN_Y + BOARD_H - MOUNT_OFFSET),
    (BOARD_ORIGIN_X + BOARD_W - MOUNT_OFFSET,   BOARD_ORIGIN_Y + BOARD_H - MOUNT_OFFSET),
]

# Component placement: {ref: (x_mm, y_mm, rotation_deg)} in absolute pcbnew coords.
# Coordinates picked so power section is on left, DevKit centered, headers on right.
PLACEMENT = {
    # Power input column (left, top → bottom)
    'J_PWR':       (BOARD_ORIGIN_X +  10, BOARD_ORIGIN_Y + 15,  0),
    'D_REV':       (BOARD_ORIGIN_X +  25, BOARD_ORIGIN_Y + 15,  0),
    'C_BULK':      (BOARD_ORIGIN_X +  10, BOARD_ORIGIN_Y + 30,  0),
    'J_BUCK':      (BOARD_ORIGIN_X +  25, BOARD_ORIGIN_Y + 35,  0),
    'U_LDO':       (BOARD_ORIGIN_X +  10, BOARD_ORIGIN_Y + 55,  0),
    'C_LDOIN':     (BOARD_ORIGIN_X +  18, BOARD_ORIGIN_Y + 55,  0),
    'C_LDOOUT':    (BOARD_ORIGIN_X +  24, BOARD_ORIGIN_Y + 55,  0),

    # ESP32 DevKit socket (center, 23 mm pitch between rails matches DevKit width)
    'J_ESP_L':     (BOARD_ORIGIN_X +  55, BOARD_ORIGIN_Y + 40, 90),   # left rail, vertical
    'J_ESP_R':     (BOARD_ORIGIN_X +  78, BOARD_ORIGIN_Y + 40, 90),
    'C_ESP_3V3_1': (BOARD_ORIGIN_X +  45, BOARD_ORIGIN_Y + 25,  0),
    'C_ESP_3V3_2': (BOARD_ORIGIN_X +  45, BOARD_ORIGIN_Y + 30,  0),

    # Peripheral headers (right column, top → bottom)
    'J_RFID':      (BOARD_ORIGIN_X + 105, BOARD_ORIGIN_Y + 15, 90),  # 1x8 vertical
    'J_LCD':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 15, 90),  # 1x4
    'R_SDA':       (BOARD_ORIGIN_X + 122, BOARD_ORIGIN_Y + 28,  0),
    'R_SCL':       (BOARD_ORIGIN_X + 122, BOARD_ORIGIN_Y + 32,  0),
    'J_USR':       (BOARD_ORIGIN_X + 105, BOARD_ORIGIN_Y + 45, 90),
    'R_USR1':      (BOARD_ORIGIN_X + 112, BOARD_ORIGIN_Y + 55,  0),
    'R_USR2':      (BOARD_ORIGIN_X + 112, BOARD_ORIGIN_Y + 60,  0),
    'J_SVO':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 40, 90),
    'C_SVO':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 55,  0),

    # Buzzer block (bottom right)
    'Q_BUZ':       (BOARD_ORIGIN_X + 105, BOARD_ORIGIN_Y + 67,  0),
    'R_BUZ':       (BOARD_ORIGIN_X + 113, BOARD_ORIGIN_Y + 67,  0),
    'J_BUZ':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 67, 90),

    # Expansion header (bottom left)
    'J_EXP':       (BOARD_ORIGIN_X +  35, BOARD_ORIGIN_Y + 70, 90),  # 1x6
}

def mm_to_iu(v):
    """Convert mm to pcbnew internal units (nanometers)."""
    return int(v * 1e6)

def iu_to_mm(v):
    return v / 1e6

def open_board(path=PCB_FILE):
    return pcbnew.LoadBoard(path)

def save_board(board, path=PCB_FILE):
    board.Save(path)
```

- [ ] **Step 2: Commit the helper module**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add kicad/smart_gate_carrier/build_scripts/pcb_common.py
git commit -m "feat(kicad): pcb placement coords and helper module"
```

---

### Task 2: Script the board outline and mounting holes

**Files:**
- Create: `kicad/smart_gate_carrier/build_scripts/add_outline_and_mounts.py`

- [ ] **Step 1: Write the outline + mounts script**

```python
#!/usr/bin/env python3
"""Add 150×80 mm board outline (Edge.Cuts layer) and four M3 mounting holes."""

import pcbnew
from pcb_common import (
    BOARD_W, BOARD_H, BOARD_ORIGIN_X, BOARD_ORIGIN_Y,
    MOUNT_HOLES, mm_to_iu, open_board, save_board, PCB_FILE,
)

def add_edge_cuts_rectangle(board):
    edge_layer = board.GetLayerID('Edge.Cuts')
    pts = [
        (BOARD_ORIGIN_X,           BOARD_ORIGIN_Y),
        (BOARD_ORIGIN_X + BOARD_W, BOARD_ORIGIN_Y),
        (BOARD_ORIGIN_X + BOARD_W, BOARD_ORIGIN_Y + BOARD_H),
        (BOARD_ORIGIN_X,           BOARD_ORIGIN_Y + BOARD_H),
        (BOARD_ORIGIN_X,           BOARD_ORIGIN_Y),
    ]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(edge_layer)
        seg.SetWidth(mm_to_iu(0.15))
        seg.SetStart(pcbnew.VECTOR2I(mm_to_iu(pts[i][0]), mm_to_iu(pts[i][1])))
        seg.SetEnd(pcbnew.VECTOR2I(mm_to_iu(pts[i+1][0]), mm_to_iu(pts[i+1][1])))
        board.Add(seg)

def add_mounting_hole(board, x_mm, y_mm):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(f'H{len(board.GetFootprints())+1}')
    fp.SetPosition(pcbnew.VECTOR2I(mm_to_iu(x_mm), mm_to_iu(y_mm)))
    pad = pcbnew.PAD(fp)
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.VECTOR2I(mm_to_iu(6.0), mm_to_iu(6.0)))
    pad.SetDrillSize(pcbnew.VECTOR2I(mm_to_iu(3.2), mm_to_iu(3.2)))
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)   # non-plated through hole
    pad.SetLayerSet(pcbnew.LSET.AllCuMask())
    fp.Add(pad)
    board.Add(fp)

def main():
    board = open_board()
    add_edge_cuts_rectangle(board)
    for x, y in MOUNT_HOLES:
        add_mounting_hole(board, x, y)
    save_board(board)
    print(f'Wrote outline + 4 mounting holes to {PCB_FILE}')

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run it**

```bash
cd /home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier
python3 build_scripts/add_outline_and_mounts.py
```

Expected: prints `Wrote outline + 4 mounting holes to ...kicad_pcb`.

- [ ] **Step 3: Verify via MCP**

```
mcp__kicad__validate_project  project_path="/home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier/smart_gate_carrier.kicad_pro"
```

Expected: `{"valid": true}`.

- [ ] **Step 4: Commit**

```bash
git add build_scripts/add_outline_and_mounts.py smart_gate_carrier.kicad_pcb
git commit -m "feat(kicad): script 150x80 board outline + 4 M3 mounting holes"
```

---

### Task 3: Script component placement

**Files:**
- Create: `kicad/smart_gate_carrier/build_scripts/place_components.py`

- [ ] **Step 1: Write the placement script**

```python
#!/usr/bin/env python3
"""Place all imported footprints at planned coordinates from pcb_common.PLACEMENT."""

import pcbnew
from pcb_common import PLACEMENT, mm_to_iu, open_board, save_board, PCB_FILE

def main():
    board = open_board()
    missing = []
    placed = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in PLACEMENT:
            if not ref.startswith('H'):   # skip mounting hole footprints
                missing.append(ref)
            continue
        x, y, rot = PLACEMENT[ref]
        fp.SetPosition(pcbnew.VECTOR2I(mm_to_iu(x), mm_to_iu(y)))
        fp.SetOrientationDegrees(rot)
        placed += 1
    save_board(board)
    print(f'Placed {placed} footprints.')
    if missing:
        print(f'Footprints with no placement (left at origin): {missing}')

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run it**

```bash
python3 build_scripts/place_components.py
```

Expected: `Placed 24 footprints.` and the `missing` list should be empty (or contain only PWR_FLAGs / mounting hole helpers — none expected since we omitted PWR_FLAGs).

- [ ] **Step 3: Open in PCB editor to inspect**

```bash
pcbnew kicad/smart_gate_carrier/smart_gate_carrier.kicad_pcb &
```

Visually verify: board outline visible, 24 footprints placed in expected zones (power left, DevKit center, headers right), ratsnest (white airwires) connecting them per netlist. No overlapping pads.

- [ ] **Step 4: Validate via MCP**

```
mcp__kicad__analyze_schematic_connections  project_path="...smart_gate_carrier.kicad_pro"
mcp__kicad__get_project_structure  project_path="..."
```

- [ ] **Step 5: Commit**

```bash
git add build_scripts/place_components.py smart_gate_carrier.kicad_pcb
git commit -m "feat(kicad): script footprint placement per board zone layout"
```

---

### Task 4: Manual placement tweaks (GUI)

**Files:** modify `smart_gate_carrier.kicad_pcb` interactively.

The scripted placement is approximate. Open the PCB editor and adjust visually for:

- [ ] **Step 1: No pad overlap** — drag any footprints whose pads physically overlap.
- [ ] **Step 2: Ratsnest minimization** — drag related footprints closer together if airwires cross excessively (rotate via `R` key, move via `M`).
- [ ] **Step 3: Connector orientation** — ensure connector pin 1 is on the outer edge (signals exit board cleanly). Use `R` to rotate 90°.
- [ ] **Step 4: Snap to 0.5 mm grid** — Edit → Preferences → set grid to 0.5 mm; use `Q` to nudge.
- [ ] **Step 5: Commit any changes**

```bash
git add smart_gate_carrier.kicad_pcb
git commit -m "tune(kicad): manual placement tweaks for connector orientation and ratsnest"
```

---

### Task 5: Set up design rules and route power rails

**Files:** PCB Editor menus.

- [ ] **Step 1: Set net classes**

PCB Editor → File → Board Setup → Design Rules → Net Classes. Create classes:

| Class | Track width | Clearance | Via diameter | Via drill |
| --- | --- | --- | --- | --- |
| Default | 0.25 mm | 0.2 mm | 0.6 mm | 0.3 mm |
| Power | 0.5 mm | 0.25 mm | 0.8 mm | 0.4 mm |

Assign to "Power" class: `+12V`, `+5V`, `+3V3`, `GND`. Assign all other nets to Default. Click OK.

- [ ] **Step 2: Route +12V manually**

Press `X` to start a track. Click each pin in the `+12V` net (J_PWR → D_REV → +12V net → J_BUCK pin 1). Use a top layer trace. Press `Esc` when done. Watch the ratsnest dim as you route.

- [ ] **Step 3: Route +5V**

Similar: J_BUCK pin 4 → U_LDO pin 3 → C_LDOIN pin 1 → all `+5V` consumers (J_ESP_R pin 1, LCD pin 2, HC-SR04 pin 1, servo pin 2, buzzer pin 1, C_SVO).

- [ ] **Step 4: Route +3V3**

U_LDO pin 2 → C_LDOOUT pin 1 → C_ESP_3V3_1/2 → J_ESP_L pin 1, J_RFID pin 8, R_SDA pin 2, R_SCL pin 2, J_EXP pin 1.

- [ ] **Step 5: Commit**

```bash
git add smart_gate_carrier.kicad_pcb
git commit -m "route(kicad): power rails (+12V, +5V, +3V3) at 0.5mm width"
```

---

### Task 6: Route signal nets (auto-router preferred)

The fastest path is FreeRouting. KiCad 6 has built-in FreeRouting integration via the Specctra DSN export.

- [ ] **Step 1: Install FreeRouting**

```bash
mkdir -p ~/tools/freerouting && cd ~/tools/freerouting
wget https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar -O freerouting.jar
which java || sudo apt install -y default-jre   # if Java not installed
```

- [ ] **Step 2: Export Specctra DSN from KiCad**

In PCB Editor: File → Export → Specctra DSN. Save as `smart_gate_carrier.dsn`.

- [ ] **Step 3: Run FreeRouting**

```bash
cd /home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier
java -jar ~/tools/freerouting/freerouting.jar -de smart_gate_carrier.dsn -do smart_gate_carrier.ses
```

Expected: GUI opens, auto-routes ~30-60 seconds for this design, exits with `.ses` written.

- [ ] **Step 4: Import .ses back to KiCad**

PCB Editor: File → Import → Specctra Session. Select `smart_gate_carrier.ses`. KiCad applies the routes.

- [ ] **Step 5: Inspect routing**

Verify all airwires are now solid traces. If any nets are unrouted, route manually with `X` key.

- [ ] **Step 6: Commit**

```bash
git add smart_gate_carrier.kicad_pcb smart_gate_carrier.dsn smart_gate_carrier.ses
git commit -m "route(kicad): auto-route signals via FreeRouting 1.9.0"
```

---

### Task 7: Add ground pour on bottom layer

**Files:** PCB Editor.

- [ ] **Step 1: Draw GND zone on bottom**

PCB Editor → switch to `B.Cu` layer (bottom copper) — click `B.Cu` in Layers panel. Toolbar → "Add a filled zone" (or press `Ctrl+Shift+Z`). Click 4 corners just outside the board outline (clip to Edge.Cuts).

In the zone properties dialog:
- Net: `GND`
- Layer: `B.Cu`
- Clearance: 0.25 mm
- Min thickness: 0.25 mm
- Thermal relief: enabled (default)
Click OK.

- [ ] **Step 2: Optionally add GND pour on top too**

Repeat for `F.Cu` layer. Helps EMI, fills gaps between traces.

- [ ] **Step 3: Refill zones**

Press `B` to recalculate zone fills.

- [ ] **Step 4: Commit**

```bash
git add smart_gate_carrier.kicad_pcb
git commit -m "feat(kicad): add GND copper pour on bottom (and optional top) layer"
```

---

### Task 8: DRC check

**Files:** PCB Editor.

- [ ] **Step 1: Run DRC**

PCB Editor → Inspect → Design Rules Checker. Click "Run DRC".

Expected: **0 errors, 0 unconnected items**. Common warnings:
- "Silkscreen overlap" — cosmetic, can ignore or tweak refdes positions.
- "Hole near hole" on mounting holes — keepout 6 mm pad on 3.2 mm drill is generous, should be fine.

If errors found, fix them (move tracks, adjust clearances). Iterate until clean.

- [ ] **Step 2: Re-validate via MCP**

```
mcp__kicad__validate_project  project_path="..."
```

- [ ] **Step 3: Commit**

```bash
git add smart_gate_carrier.kicad_pcb
git commit -m "fix(kicad): resolve DRC errors; board now DRC-clean"
```

---

### Task 9: Add silkscreen labels and version

**Files:** PCB Editor.

- [ ] **Step 1: Add board title**

PCB Editor → toolbar "Add a text item" → place on `F.SilkS` (top silkscreen).
- Text: `SMART GATE CARRIER v1.0`
- Size: 1.5 mm
- Position: top center (BOARD_ORIGIN_X + 75, BOARD_ORIGIN_Y + 5)

- [ ] **Step 2: Add date and assembly notes**

Bottom edge silkscreen:
- `2026-05-22 KiCad 6.0.2`
- Near J_LCD: `Cut LCD 5V pull-ups, use 3V3 onboard`
- Near J_USR: `R_USR1=1k R_USR2=2k divider`

- [ ] **Step 3: Verify reference designators are visible and not overlapping pads**

Drag any RefDes text that overlaps pads. Resize to 0.8-1.0 mm height.

- [ ] **Step 4: Commit**

```bash
git add smart_gate_carrier.kicad_pcb
git commit -m "docs(kicad): add silkscreen title, date, and assembly notes"
```

---

### Task 10: Export gerbers, drill, and 3D STEP

**Files:** new files in `gerber/` and `3d/` directories.

- [ ] **Step 1: Generate gerbers**

PCB Editor → File → Plot.
- Plot directory: `gerber/`
- Plot format: Gerber
- Layers: F.Cu, B.Cu, F.SilkS, B.SilkS, F.Mask, B.Mask, F.Paste, B.Paste, Edge.Cuts
- Options: Plot reference, plot footprint values, use Protel filename extensions
- Click "Plot"

- [ ] **Step 2: Generate drill file**

Same dialog → "Generate Drill Files".
- Format: Excellon
- Drill units: millimeters
- Zeros format: suppress leading zeros
- Click "Generate Drill File"

Output: `smart_gate_carrier.drl` (PTH) + `smart_gate_carrier-NPTH.drl` (mounting holes).

- [ ] **Step 3: Export 3D STEP for FreeCAD**

PCB Editor → File → Export → STEP. Save to `3d/smart_gate_carrier.step`. Use default settings (drill origin, components included).

- [ ] **Step 4: Verify via MCP**

```
mcp__kicad__get_project_structure  project_path="..."
mcp__kicad__analyze_bom  project_path="..."
```

- [ ] **Step 5: Generate PDF print of layout**

PCB Editor → File → Plot → PDF format → All visible layers → save as `smart_gate_carrier_pcb.pdf` for review.

- [ ] **Step 6: Commit**

```bash
# gerber/ is in .gitignore; force-add for archive
git add -f gerber/ 3d/smart_gate_carrier.step smart_gate_carrier_pcb.pdf
git add smart_gate_carrier.kicad_pcb
git commit -m "chore(kicad): export gerbers, drill files, and STEP 3D model"
```

---

### Task 11: Cross-check with mechanical envelope

**Files:** none modified.

- [ ] **Step 1: Load STEP into FreeCAD** (if available) and place inside the base box model from §6 spec. Verify:
  - PCB fits within 200×100 mm internal box footprint with ≥20 mm clearance each side.
  - Connectors (especially J_PWR, J_RFID, J_LCD, J_USR) align with the cutouts on the front/back panels.
  - DC jack J_PWR exits toward the back panel.
  - Headers J_RFID, J_LCD, J_USR exit toward the front panel.

If FreeCAD model isn't built yet, do this check after the FreeCAD plan is executed.

- [ ] **Step 2: Confirm via spec §6 dimensions**

Open spec doc and re-read §6.2 (parts list). PCB at 150×80 mm vs base box 200×100 mm internal → 25 mm cable clearance each side. ✓

- [ ] **Step 3: Mark plan complete**

The PCB is ready for fabrication. Hand off artefacts:
- `smart_gate_carrier.kicad_pcb` — source
- `gerber/*.gbr` + `gerber/*.drl` — fab files (zip and send to JLCPCB / EasyEDA / PCBWay)
- `3d/smart_gate_carrier.step` — for FreeCAD assembly verification
- `smart_gate_carrier_pcb.pdf` — review artefact

---

## Verification checklist (run before sending to fab)

- [ ] DRC reports 0 errors, 0 unconnected
- [ ] All 24 functional footprints have routes (no airwires)
- [ ] 4 mounting holes present at corners, 3.2 mm drill
- [ ] Board outline closed rectangle on Edge.Cuts
- [ ] GND copper pour on bottom layer (and optionally top) filled and connected
- [ ] Silkscreen title and date present
- [ ] Reference designators visible and not over pads
- [ ] Gerber files generated (9 layers + drill)
- [ ] STEP 3D model exported for FreeCAD cross-check
- [ ] PDF print available for review
- [ ] All artefacts committed to git

---

## Out of scope (next plan or other sessions)

- BOM cost optimisation / component sourcing — separate sourcing task.
- Panelization for fab efficiency — usually fab handles this for small quantities.
- Assembly drawing (X/Y placement file for pick-and-place) — only needed if doing PnP assembly, prototypes are hand-soldered.
- Stencil paste mask design — only if reflow-soldering SMD parts.
- Schematic visual export — design deliverable was netlist + Python source; no Eeschema schematic file by choice.

---

## Risks / open items

1. **pcbnew Python API quirks** — KiCad 6.0.2 has been stable but the API has subtle method-name changes from KiCad 5. If a method call fails, check the API doc at `https://docs.kicad.org/doxygen-python-6.0/`.
2. **FreeRouting timeout / poor routing** — auto-routers can produce dense but ugly routes. If results look bad, route manually instead — the design is small enough (~30 nets) that manual routing in 1-2 hours is feasible.
3. **3.3 V LDO heat** — AMS1117-3.3 in SOT-223 has ~62 °C/W thermal resistance to ambient. At 150 mA load, drop is 1.7 V → 0.25 W → 15 °C rise above ambient. Acceptable, no heat sink needed.
4. **Servo current spikes on shared 5V rail** — covered by the 470 µF cap and routing the servo VCC trace separately from the LCD/RC522 trace (star topology back to buck output).
5. **DOIT V1 DevKit socket pin pitch** — confirm 23.0 mm rail-to-rail vs measurement (some clones are 22.86 mm = 0.9 inch). If misfit, regenerate placement script with corrected `J_ESP_R` x-coordinate.
