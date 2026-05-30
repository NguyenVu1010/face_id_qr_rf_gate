# Mica Gate Pillar Enclosure Design

**Date:** 2026-05-31
**Status:** Spec, pending implementation
**Owner:** brainstorm session (dev_kicad)
**Consumed by:** Laser-cut PDF generator (`freecad/laser_cut/build_mica_pillar.py`)
**Replaces:** Active design coexists with `2026-05-23-smart-gate-enclosure-design.md` — user may use either the 3D-printed box (controller-only) or this mica pillar (whole-system model). This spec is a parallel implementation, not a replacement of the PCB or firmware specs.

## 1. Goal

Build a laser-cut clear acrylic enclosure shaped like a real check-in turnstile pillar at **1:2.5 scale**. The pillar contains the entire smart_gate system (motherboard PCB + Pi 4 + ESP32 + LCD + RFID + HC-SR04 + servo + USB webcam) and visually resembles a working office check-in gate. The deliverable is a single PDF file with all cut pieces ready for a laser shop.

## 2. Scope

**In scope:**
- 7-piece acrylic pillar (FRONT, BACK, LEFT, RIGHT, TOP-FLAT, SLOPE-FACET, BOTTOM)
- Drop-arm acrylic piece (8th piece, cut on the same sheet)
- Interior wooden corner posts for screw-on faces
- 3D-printed camera tower (separate part using existing FDM printer)
- Laser-cut PDF generator script + nesting layout
- Internal component mounting + cable routing
- Joint geometry (finger joints) and tolerances
- Assembly procedure

**Out of scope:**
- Mounting pillar to floor/base (pillar stands free on desk)
- Real LED status indicator (decorative cutout only, no electrical LEDs)
- Weatherproofing / IP rating
- PCB redesign (existing PCB used as-is; mount holes assumed at corners)
- Firmware changes (existing firmware drives servo/LCD/RFID/HC-SR04 unchanged)

## 3. Architecture

### 3.1 Reference frame

- Origin: SW-bottom corner (when looking at FRONT face from outside)
- **X axis:** 0 → 150 mm — width (LEFT face at X=0, RIGHT face at X=150)
- **Y axis:** 0 → 120 mm — depth (FRONT face at Y=0, BACK face at Y=120)
- **Z axis:** 0 → 400 mm — height (BOTTOM at Z=0, TOP at Z=400)

User stands at Y<0 facing +Y direction to read the FRONT face during check-in. After scanning, user walks past the pillar's RIGHT side in +X direction. The drop-arm extends from the RIGHT face to block this +X path.

### 3.2 Silhouette (side view, looking at LEFT face from outside)

```
                Z=400 ┌──── TOP-FLAT (90mm Y-deep) ────┐
                      │                                │
                      │                                │
                      ╱  SLOPE 45° (RFID zone)         │
                Z=370 ╱   30mm × 30mm × 42.4mm hyp     │
                      │                                │
                      │                                │
                      │   FRONT vertical               │   BACK vertical
                      │                                │
                      │                                │
                Z=0   └────── BOTTOM (120mm Y) ───────┘
                      Y=0                              Y=120
```

LEFT and RIGHT faces are **pentagons**: rectangle 120×400mm with the top-front 30×30mm triangle corner removed (creating the 45° slope edge).

### 3.3 Face roster

| Face | Plane | Outline | Removable | Cutouts |
|---|---|---|---|---|
| FRONT | Y=0 | 150 × 370 | No | None (optional engraving) |
| SLOPE | 45° from Y=0,Z=370 to Y=30,Z=400 | 150 × 42.43 | No | RFID engrave marker |
| TOP-FLAT | Z=400 | 150 × 90 (X × Y, Y range 30–120) | No | LCD + camera tower mount |
| BACK | Y=120 | 150 × 400 | **Yes** | Adapter cable hole + 6× M3 |
| LEFT | X=0 | Pentagon 120×400 (top-front corner clipped) | **Yes** | 4× M3 mount holes |
| RIGHT | X=150 | Pentagon 120×400 (top-front corner clipped) | No | Servo + HC-SR04 |
| BOTTOM | Z=0 | 150 × 120 | No | Optional vent slots |

### 3.4 Internal frame

Four vertical wooden corner posts (10×10mm pine wood × 380mm tall) at the four interior corners of the pillar. The wooden posts:
- Anchor the 7 acrylic faces via finger joints (for fixed faces) or M3 self-tap screws into the wood (for removable faces).
- Carry the load and stiffness — acrylic 3mm alone is too flexible for a 40cm-tall pillar.
- Total 4 posts × 380mm = 1.52m of 10×10mm pine wood.

## 4. Dimensions & materials

### 4.1 External pillar dimensions

| Axis | Outer dimension | Inner dimension (after walls) |
|---|---|---|
| X (width) | 150 mm | 144 mm (150 - 2×3mm walls) |
| Y (depth) | 120 mm | 114 mm |
| Z (height) | 400 mm | 397 mm (400 - 3mm BOTTOM) |

### 4.2 Material list

| Item | Spec | Qty |
|---|---|---|
| Clear acrylic sheet | 3 mm thickness, transparent | ~0.30 m² (8 pieces) |
| Pine wood batten | 10 × 10 mm cross-section | 1.6 m (4 posts × 380mm + offcuts) |
| M3 × 12 Phillips screws | For BACK panel | 6 |
| M3 × 12 Phillips screws | For LEFT panel | 4 |
| M3 × 8 Phillips screws | For PCB to BACK standoffs | 4 |
| M3 × 6 Phillips screws | For LCD module to TOP | 4 |
| M3 × 10 Phillips screws | For camera tower to TOP | 4 |
| M2 × 8 Phillips screws | For drop-arm to servo horn | 2 |
| M2.5 × 6 screws | For servo flange | 2 |
| Nylon standoffs PCB | M3, OD 6mm, height 5mm | 4 |
| Acrylic cement | Cosmofen PMMA or Acrifix 1S | 50 ml bottle |
| Rubber grommet | Inner Ø6mm, outer Ø10mm | 1 (BACK cable hole) |

### 4.3 Sheet nesting

8 pieces fit on a single **800 × 500 mm** acrylic sheet, or on 2 standard 600 × 400 mm sheets. Total cut area ~0.25 m² + ~25% gap/kerf overhead.

## 5. Per-face cutout coordinates

All coordinates are face-local: origin at bottom-left corner of the face when viewing from outside, X horizontal-right, Y vertical-up.

### 5.1 FRONT (150 × 370)

No through-cuts. Optional engrave at center: project name + version.

### 5.2 SLOPE facet (150 × 42.43)

Face-local coords: X 0–150, V 0–42.43 (V = position along the sloped hypotenuse, from FRONT-top edge at V=0 to TOP-FLAT-front edge at V=42.43).

- **RFID engrave marker:** rectangle 50 × 30 mm, centered. Outline only (engrave depth 0.2mm, not through-cut). Position: X 50–100, V 6.2–36.2.
- The RC522 RFID PCB mounts behind this marker on the inside surface. RF passes through 3mm acrylic with negligible loss.

### 5.3 TOP-FLAT (150 × 90)

- **LCD viewing cutout:** 98 × 40 mm rectangle with 4mm corner fillets. Centered at (X=75, Y=35). Cut bounds: X 26–124, Y 15–55.
- **LCD mounting holes:** 4× Ø3.2 mm clearance holes at (X, Y) = (28.5, 7.5), (121.5, 7.5), (28.5, 62.5), (121.5, 62.5). Spacing 93 × 55 mm (matches standard 20×4 I2C LCD module).
- **Camera tower mount:** Ø8mm cable hole centered at (X=75, Y=77.5). 4× Ø3.2mm clearance holes around it at (X, Y) = (67, 69.5), (83, 69.5), (67, 85.5), (83, 85.5). Tower flange bolts down with 4× M3.

### 5.4 LEFT (pentagon, removable)

Outline vertices (face-local Y horizontal-back from FRONT edge, Z vertical-up):
```
(Y=0,   Z=0)     -- SW corner
(Y=120, Z=0)     -- SE corner (BACK side)
(Y=120, Z=400)   -- NE corner
(Y=30,  Z=400)   -- top edge meets slope
(Y=0,   Z=370)   -- slope meets FRONT edge
```

**Mount holes** (Ø3.5mm clearance for M3 screws into wooden corner posts):
- Bottom-front: (Y=5, Z=8)
- Bottom-back: (Y=115, Z=8)
- Top-back: (Y=115, Z=392)
- Top-front: (Y=5, Z=355)

Holes inset 5–8 mm from edges to land on the 10×10mm wooden posts.

### 5.5 RIGHT (pentagon, fixed)

Same outline as LEFT (mirrored). Internal cutouts:

- **Servo shaft hole:** Ø8 mm at (Y=60, Z=200).
- **Servo flange mount holes:** 2× Ø2.7mm at (Y=46, Z=200) and (Y=74, Z=200). Spacing 28mm matches SG90 flange tabs. *Note: exact offset depends on the specific SG90 unit; verify against user's part before cutting (see §13).*
- **HC-SR04 transducer holes:** 2× Ø16mm at (Y=46.5, Z=300) and (Y=73.5, Z=300). Center-to-center 27mm (matches typical HC-SR04 board layout).
- **HC-SR04 PCB mount holes:** 2× Ø3.2mm at (Y=20, Z=300) and (Y=100, Z=300). For zip-tie or 2× M3 screws holding PCB flat against inside of RIGHT face.

### 5.6 BACK (150 × 400, removable)

- **Adapter cable hole:** Ø10mm at (X=15, Z=15). Bottom-left corner area, rubber grommet press-fit.
- **Mount holes:** 6× Ø3.5mm clearance for M3 screws into wooden corner posts:
  - Bottom edge: (X=8, Z=8), (X=142, Z=8)
  - Top edge: (X=8, Z=392), (X=142, Z=392)
  - Mid edges: (X=8, Z=200), (X=142, Z=200)

### 5.7 BOTTOM (150 × 120)

- **Vent slots (optional):** 4× rectangular 30×3 mm slots, centered along the X axis, at Y = 30, 60, 90 (3 slots) — or skip if user prefers sealed bottom. Default: include slots for passive cooling of Pi.

### 5.8 Drop-arm (150 × 15 × 3)

- **Mounting holes:** 2× Ø2.2mm at distance 5mm and 13mm from one short end (8mm spacing matches SG90 1-arm horn).
- **Decoration:** optional engrave red/white stripes (5 stripes of 30mm each along length).

## 6. Internal mounting strategy

| Component | Mounted to | Method | Position |
|---|---|---|---|
| Motherboard PCB (200×120mm) | BACK panel inside surface | 4× nylon standoff Ø6mm × 5mm tall, M3×8 screws from outside BACK through panel into standoff | PCB vertical: long axis along Z, short axis along X. PCB center at (X=75, Z=180). PCB extends Z=80–280, X=15–135. |
| Pi 4B | J_PI socket on PCB | Plug-in via socket | Pi sits in +Y direction from PCB toward FRONT. Pi USB stack reaches ~30mm into trụ interior. |
| ESP32 DevKit | J_ESP socket on PCB | Plug-in | Co-located with PCB |
| LM2596 buck module | J_BUCK header | Plug-in | On PCB |
| LCD 20×4 module | TOP-FLAT inside surface | 4× M3×6 self-tap from outside through TOP into LCD module standoffs | Module body at Y_local 5–65, X 26–124. Header on east short edge (X=124 side) facing +X to reach J_LCD. |
| RC522 RFID | SLOPE facet inside surface | 4× M3 standoffs 5mm tall glued to SLOPE inside with acrylic cement; RC522 PCB bolted to standoffs | RC522 antenna pointing outward through SLOPE. PCB parallel to slope plane. |
| HC-SR04 module | RIGHT face inside surface | 2× M3×6 through RIGHT into nylon standoffs glued to inside; or zip-tie via 2 board holes | Transducers poke through the 2× Ø16mm holes from inside |
| SG90 servo | RIGHT face inside surface | 2× M2.5×6 through RIGHT into servo flange tabs from outside | Servo body inside trụ, shaft axis along X, shaft pokes through Ø8mm hole to outside |
| Camera tower | TOP-FLAT outside surface | 4× M3×10 through TOP from inside upward into tower flange | Cylindrical 3D-printed tower, Ø20mm × 120mm tall, USB cable runs inside cylinder |

## 7. Cable routing

| Cable | Length | From | To | Path |
|---|---|---|---|---|
| 12V DC | 150 mm | Adapter (external) | J_PWR on PCB | Through Ø10mm BACK grommet → direct down to J_PWR |
| Pi power (5V) | — | LM2596 output (on-PCB) | Pi GPIO 5V pins via J_PI socket | Internal PCB trace, no external cable |
| LCD I2C (4-wire) | 250 mm | J_LCD on PCB | LCD module on TOP | Up along inside of RIGHT face, then over to LCD east-edge header |
| RFID SPI (7-wire) | 200 mm | J_RFID on PCB | RC522 on SLOPE | Up along inside of FRONT face, then to RC522 header |
| Servo (3-wire) | 150 mm | J_SVO on PCB | SG90 on RIGHT face | Direct from PCB east edge to servo body |
| HC-SR04 (4-wire) | 180 mm | J_USR on PCB | HC-SR04 on RIGHT face | Direct east, then up to Z=300 |
| Buzzer (2-wire) | 150 mm | J_BUZ on PCB | Buzzer (mounted where?) | **TBD — see §13** |
| USB webcam | 250 mm | Pi 4 USB port | Webcam in camera tower | Up through TOP Ø8mm hole, inside cylinder, to webcam at tower top |

All cables use Dupont female-female 40-pin sets (already in shopping list).

## 8. Joint geometry

### 8.1 Finger joints (for fixed faces: FRONT, RIGHT, TOP, SLOPE, BOTTOM)

Faces interlock with each other and with the wooden corner posts via finger joints (mộng âm dương).

- **Tab width:** 20 mm
- **Slot width:** 20 mm + 0.15 mm tolerance (= 20.15 mm in CAD)
- **Tab thickness:** 3 mm (= sheet thickness)
- **Pattern:** alternating 4 tabs / 3 slots per long edge, with 5mm flat margins at each end
- **Edge engagement:** 3 mm depth (= sheet thickness)
- **Bonding:** apply acrylic cement (Cosmofen PMMA) to all finger joints during assembly. Once cured (~10 min), bond is permanent.

### 8.2 Screwed faces (LEFT, BACK)

LEFT and BACK use M3 screws into the wooden corner posts. No finger joints. Posts have pre-drilled Ø2.7mm pilot holes for M3 self-tap (in pine wood).

### 8.3 Slope facet attachment

SLOPE is a quadrilateral 150 × 42.43 mm. It attaches at:
- Top edge: finger-joints into the FRONT edge of TOP-FLAT
- Bottom edge: finger-joints into the TOP edge of FRONT
- Left/Right edges: finger-joints into the angled top-front edges of LEFT and RIGHT pentagons

All 4 edges of SLOPE have matching finger joints with their respective neighbors.

## 9. PDF output specification

### 9.1 Generator script

Python script `freecad/laser_cut/build_mica_pillar.py`:
- Library: `ezdxf` (DXF) or `reportlab` (PDF). Choose `ezdxf` then convert to PDF via `cairo` or `matplotlib` for cleaner vector output.
- Parameters at top of script:
  - `MICA_THICKNESS = 3.0` mm
  - `KERF = 0.1` mm (laser kerf compensation)
  - `JOINT_TOLERANCE = 0.15` mm
  - `PILLAR_W = 150`, `PILLAR_D = 120`, `PILLAR_H = 400`
  - `SLOPE_PROJECTION = 30` (mm of slope projected on Y and Z)
- Output: `freecad/laser_cut/exports/mica_gate_pillar.pdf`

### 9.2 PDF layout conventions

- **Page size:** A2 (420 × 594 mm) — large enough for nesting 1 sheet
- **Cut lines:** RGB(255, 0, 0), stroke width 0.001 mm (hairline) — most laser cutters interpret red as "cut"
- **Engrave lines:** RGB(0, 0, 0), stroke width 0.1 mm — most cutters interpret black as "engrave"
- **Etch fills (for RFID marker rectangle interior):** RGB(0, 0, 255), stroke width 0.05 mm
- **Each piece labeled** with engraved text at one corner: `FRONT`, `BACK`, `LEFT`, `RIGHT`, `TOP`, `SLOPE`, `BOTTOM`, `ARM`
- **Orientation arrow** engraved on each piece pointing toward the piece's "TOP edge" (the edge that mounts upward in the assembled pillar)
- **Title block** at one corner of the page: project name, date, mica thickness, scale 1:1

### 9.3 Nesting

Pieces arranged on 800 × 500 mm sheet:
- Row 1: FRONT (150×370) + BACK (150×400) + LEFT (120×400) + RIGHT (120×400) — width 540, height 400
- Row 2: TOP (150×90) + SLOPE (150×42.4) + BOTTOM (150×120) + ARM (150×15) — width 600, height 120

Gap between pieces ≥ 5 mm (for kerf + handling).

## 10. Assembly procedure

1. **Cut all pieces.** Send PDF to laser shop. Receive 8 mica pieces.
2. **Prepare wooden posts.** Cut 4× pine wood batten 10×10×380 mm. Drill Ø2.7 mm pilot holes at the locations matching LEFT and BACK mount holes (see §5.4, §5.6).
3. **Assemble fixed faces** in this order:
   a. Glue BOTTOM to the 4 wooden posts (bottom 10mm of each post). Apply acrylic cement to BOTTOM tab edges; press posts into BOTTOM slots.
   b. Glue FRONT to posts (front 2 posts). Use a 90° square to ensure perpendicularity.
   c. Glue RIGHT to posts (back-right and front-right posts).
   d. Wait 10 min for cement to set.
4. **Mount internal components** through the open LEFT and BACK access:
   a. Install heat-shrink sleeves on cable bundles.
   b. Glue 4× nylon standoffs to BACK panel inside surface at PCB mount positions.
   c. Glue RC522 standoffs to SLOPE inside.
   d. Glue HC-SR04 standoffs to RIGHT inside (above the 2 transducer holes).
5. **Glue SLOPE facet** to FRONT-top + LEFT-top-front + RIGHT-top-front edges. Use clamps to hold during cure.
6. **Glue TOP-FLAT** to LEFT-top + RIGHT-top + SLOPE-top + the (still-open) BACK-top edge. Wait for cure.
7. **Install components**:
   a. Plug Pi 4 + ESP32 + LM2596 into PCB sockets.
   b. Connect peripheral cables (I2C → LCD pigtail, SPI → RC522 pigtail, servo, HC-SR04, buzzer).
   c. Mount PCB to BACK panel standoffs via 4× M3×8.
   d. Mount LCD onto TOP via 4× M3×6 from outside.
   e. Mount RC522 onto SLOPE standoffs.
   f. Mount HC-SR04 onto RIGHT standoffs.
   g. Mount SG90 servo onto RIGHT face via 2× M2.5×6.
   h. Bolt drop-arm onto SG90 horn via 2× M2×8.
   i. Bolt camera tower (3D-printed) onto TOP via 4× M3×10. Thread USB webcam cable down through TOP Ø8mm hole into trụ. Plug into Pi USB port.
8. **Attach BACK panel** (which now carries the PCB) to wooden posts via 6× M3×12.
9. **Attach LEFT panel** to wooden posts via 4× M3×12.
10. **Power test.** Plug 12V adapter through BACK grommet, into J_PWR. System boots; LCD displays; arm exercises.

**Total assembly time:** ~90 minutes first time. Most time is glue cure (~30 min total). Maintenance access (LEFT/BACK panel only): ~5 min reopen.

## 11. Testing & verification

### 11.1 Pre-cut checks (PDF review)

- All 8 pieces present in PDF
- Each piece labeled
- Finger-joint counts match between mating edges (count tabs on FRONT-bottom vs slots on BOTTOM-front, etc.)
- Cutout coordinates match per-face spec (visual check against §5)
- Total cut area fits target sheet size with ≥5mm gaps

### 11.2 Test piece (before full cut)

Cut 1 test piece first: a 50×50 mm square with one finger-joint edge mating to a wooden post 10×10×50. Verify:
- Tabs fit slots with 0.1–0.2 mm slack (snug but assemblable)
- Wood post pilot holes thread M3 cleanly
- Acrylic cement bond holds after 10 min cure

If test fails → adjust `JOINT_TOLERANCE` in generator script and re-cut test piece. Proceed to full cut only after test passes.

### 11.3 Post-assembly fit checks

| Step | Pass criterion |
|---|---|
| All 8 pieces interlock | All finger joints engage, no >0.5mm gap |
| BACK panel removable | Unscrew 6× M3, lift away without snagging cables |
| LEFT panel removable | Same |
| PCB sits flush on standoffs | All 4 mount holes clear, no twist |
| Pi 4 powers on | LED responds to 12V plug-in |
| LCD shows boot text | Visible through TOP cutout |
| RFID reads card | Tap card on SLOPE facet outside surface, RC522 detects |
| HC-SR04 returns valid distance | Wave hand 30cm in front of RIGHT face, distance reading sane |
| Servo drives arm | Send servo command, arm rotates from horizontal to vertical |
| Camera enumerates on Pi USB | `lsusb` shows webcam |

### 11.4 Iteration loop

| Failure | Fix |
|---|---|
| Finger joints too tight | Reduce `JOINT_TOLERANCE` (e.g., 0.15 → 0.2 mm), re-cut affected pieces |
| Finger joints too loose | Increase tolerance, re-cut |
| LCD cutout off-center | Tweak coords in §5.3, re-cut TOP-FLAT only |
| RFID won't read through 3mm mica | Should not occur (RF transparent); verify RC522 antenna parallel to slope |
| Pillar wobbles | Verify wooden posts are tight; add a base plate option |

## 12. Decisions log

| # | Date | Decision | Rationale |
|---|---|---|---|
| 1 | 2026-05-31 | Switch to laser-cut mica from 3D-print | User preference to model a real check-in gate |
| 2 | 2026-05-31 | Scale 1:2.5 (not 1:4) | 1:4 too small for PCB (200×120mm); 1:2.5 gives 40cm pillar that still fits PCB inside |
| 3 | 2026-05-31 | 7-piece pillar + 1 arm | Minimum pieces; pentagon LEFT/RIGHT carries slope facet |
| 4 | 2026-05-31 | Drop-arm style, arm on RIGHT face | User explicit choice; arm blocks +X path past trụ |
| 5 | 2026-05-31 | LCD on TOP-FLAT, RFID on SLOPE facet, HC-SR04 on RIGHT | Matches reference image; SLOPE provides ergonomic badge tap angle |
| 6 | 2026-05-31 | Camera tower as separate 3D-printed part | Avoids crowding TOP face cutouts; reuses existing FDM printer |
| 7 | 2026-05-31 | Decorative LED status bar removed | Simplification; firmware/BOM unchanged |
| 8 | 2026-05-31 | 3mm clear acrylic | Standard cheap stock; transparent shows internals for demo; rigid enough at 40cm |
| 9 | 2026-05-31 | Wooden corner posts + finger joints | Acrylic alone too flexible; posts also accept M3 self-tap for removable panels |
| 10 | 2026-05-31 | BACK and LEFT removable for maintenance | RIGHT carries servo/HC-SR04 → must be fixed; BACK gives PCB access, LEFT gives cable access |
| 11 | 2026-05-31 | Adapter 12V cable enters via BACK Ø10mm grommet | User picked BACK lower corner |
| 12 | 2026-05-31 | PDF output single A2 page, red=cut / black=engrave | Standard laser shop convention |
| 13 | 2026-05-31 | Slope facet 30mm × 30mm (was 60mm) | 60mm slope left too little TOP depth for LCD + camera mount |

## 13. Open questions

1. **PCB mount hole positions** — Assumed at PCB corners 5mm inset. Implementation must verify by reading actual MountingHole footprints from `smart_gate_combined.kicad_pcb`. If different, adjust standoff positions on BACK panel.
2. **SG90 servo flange dimensions** — Assumed 28mm hole spacing; exact value depends on user's specific SG90 unit (some clones vary ±1mm). Verify against the physical part before cutting RIGHT face.
3. **Buzzer mounting location** — Not yet assigned a face. Options: (a) inside trụ, sound escapes via vent slots (muffled); (b) RIGHT face with a small Ø10mm hole; (c) BACK face inside surface, sound through panel. Default: inside trụ near BOTTOM vents. Confirm with user during implementation.
4. **Camera tower geometry** — Sized Ø20mm × 120mm tall in this spec, but exact webcam dimensions vary. If user's webcam is a Logitech C270 (60×30×60mm), tower needs a top platform instead of a cylinder cap. Confirm webcam model before designing 3D-print STL.
5. **HC-SR04 transducer hole spacing** — Assumed 27mm center-to-center, standard. Verify on user's specific HC-SR04 module before cutting.
6. **Pi USB-C power input** — Existing PCB design feeds Pi via GPIO 5V from LM2596. This spec assumes the same path (no USB-C cable into trụ). If user later needs USB-C power, add a Ø6mm slot on BACK panel.
7. **Drop-arm rest position when closed** — Spec says arm horizontal pointing -Y (forward of FRONT). Confirm this matches user's intent for physical demo, or whether arm should point +Y (backward) when closed.

## 14. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Finger-joint tolerance wrong → pieces won't fit | High on first cut | Cut test piece per §11.2 before full sheet |
| Acrylic cracks during M3 self-tap | Medium | All M3 threading is into wood, not acrylic; acrylic only has Ø3.2 clearance holes |
| 3mm mica too flexible at 40cm height | Medium | Wooden corner posts provide structure; pillar should not be pushed laterally |
| RFID reads weakly through 3mm mica + standoff gap | Low | RC522 antenna designed for 1-5cm range; gap of 5mm + 3mm mica = 8mm, within range |
| Cable bundle binds when closing LEFT panel | Medium | Route cables to BACK side, away from LEFT panel; allow 20mm slack |
| Servo can't lift drop-arm (150mm × 15mm × 3mm acrylic) under its own weight | Low | SG90 stall torque ~1.8 kg·cm; arm mass ~7g, moment arm ~75mm → torque ~0.05 kg·cm — well within servo capability |
| Glue cement attacks acrylic surface finish | Low | Cosmofen PMMA is designed for acrylic; apply only on joint edges, not faces |
| 3D-printed camera tower wobbles | Medium | Tower base flange should be ≥50mm diameter for stability; consider 5mm wall thickness |
| User's specific SG90 / RC522 / HC-SR04 part dimensions differ from spec | Medium | Per-component verification step before cutting (see open questions §13) |
