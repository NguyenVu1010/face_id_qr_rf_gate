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
- **Y axis:** 0 → 240 mm — depth (FRONT face at Y=0, BACK face at Y=240)
- **Z axis:** 0 → 300 mm — height (BOTTOM at Z=0, TOP at Z=300)

User stands at Y<0 facing +Y direction to read the FRONT face during check-in. After scanning, user walks past the pillar's RIGHT side in +X direction. The drop-arm extends from the RIGHT face to block this +X path.

### 3.2 Silhouette (side view, looking at LEFT face from outside)

```
                Z=300 ┌──── TOP-FLAT (168mm Y-deep) ───┐
                      │                                │
                      │                                │
                      ╱  SLOPE 45° (RFID zone)         │
                Z=228 ╱   72mm × 72mm × 101.8mm hyp    │
                      │                                │
                      │                                │
                      │   FRONT vertical               │   BACK vertical
                      │                                │
                      │                                │
                Z=0   └────── BOTTOM (240mm Y) ───────┘
                      Y=0                              Y=240
```

LEFT and RIGHT faces are **pentagons**: rectangle 240×300mm with the top-front 72×72mm triangle corner removed (creating the 45° slope edge).

### 3.3 Face roster

| Face | Plane | Outline | Removable | Cutouts |
|---|---|---|---|---|
| FRONT | Y=0 | 150 × 228 | No | None (optional engraving) |
| SLOPE | 45° from Y=0,Z=228 to Y=72,Z=300 | 150 × 101.82 | No | RFID engrave marker |
| TOP-FLAT | Z=300 | 150 × 168 (X × Y, Y range 72–240) | No | LCD + camera tower mount + USB-plug pass-through |
| BACK | Y=240 | 150 × 300 | **Yes** | Adapter cable hole + 6× M3 |
| LEFT | X=0 | Pentagon 240×300 (top-front corner clipped) | **Yes** | 4× corner mount holes + 4× PCB standoff M3 |
| RIGHT | X=150 | Pentagon 240×300 (top-front corner clipped) | No | Arm slot + HC-SR04 + corner-mount HC-SR04 (no servo here) |
| BOTTOM | Z=0 | 150 × 240 | No | Optional vent slots |

### 3.4 Internal frame

Four vertical wooden corner posts (10×10mm pine wood × 280mm tall) at the four interior corners of the pillar. The wooden posts:
- Anchor the 7 acrylic faces via finger joints (for fixed faces) or M3 self-tap screws into the wood (for removable faces).
- Carry the load and stiffness — acrylic 5mm gives the pillar good rigidity at 30cm height (3mm would noticeably flex; 5mm is rigid in the hand). Wooden corner posts still anchor mounting/disassembly.
- Total 4 posts × 280mm = 1.12m of 10×10mm pine wood.

## 4. Dimensions & materials

### 4.1 External pillar dimensions

| Axis | Outer dimension | Inner dimension (after walls) |
|---|---|---|
| X (width) | 150 mm | 140 mm (150 - 2×5mm walls) |
| Y (depth) | 240 mm | 230 mm |
| Z (height) | 300 mm | 290 mm (300 - 5mm BOTTOM - 5mm TOP-region) |

### 4.2 Material list

| Item | Spec | Qty |
|---|---|---|
| Clear acrylic sheet | 5 mm thickness, transparent | ~0.30 m² (8 pieces) |
| Pine wood batten | 10 × 10 mm cross-section | 1.2 m (4 posts × 280mm + offcuts) |
| M3 × 12 Phillips screws | For BACK panel | 6 |
| M3 × 12 Phillips screws | For LEFT panel | 4 |
| M3 × 8 Phillips screws | For PCB to LEFT standoffs | 4 |
| M3 × 6 Phillips screws | For LCD module to TOP | 4 |
| M3 × 10 Phillips screws | For camera tower to TOP | 4 |
| M2 × 8 Phillips screws | For drop-arm to servo horn | 2 |
| M2.5 × 6 screws | For servo flange to bracket wall | 2 |
| Servo bracket STL (3D-printed) | PLA/PETG, base 50×40mm, wall H=97mm (TARGET_Z=100) | 1 |
| Nylon standoffs PCB | M3, OD 6mm, height 5mm | 4 |
| Acrylic cement | Cosmofen PMMA or Acrifix 1S | 50 ml bottle |
| Rubber grommet | Inner Ø6mm, outer Ø10mm | 1 (BACK cable hole) |

### 4.3 Sheet nesting

8 pieces fit on a single **1000 × 600 mm** acrylic sheet, or on 2 standard 600 × 400 mm sheets. Total cut area ~0.25 m² + ~25% gap/kerf overhead.

## 5. Per-face cutout coordinates

All coordinates are face-local: origin at bottom-left corner of the face when viewing from outside, X horizontal-right, Y vertical-up.

### 5.1 FRONT (150 × 228)

No through-cuts. Optional engrave at center: project name + version.

### 5.2 SLOPE facet (150 × 101.82)

Face-local coords: X 0–150, V 0–101.82 (V = position along the sloped hypotenuse, from FRONT-top edge at V=0 to TOP-FLAT-front edge at V=101.82).

- **RFID engrave marker:** rectangle 60 × 35 mm, centered. Outline only (engrave depth 0.2mm, not through-cut). Position: X 45–105, V 33.41–68.41.
- The RC522 RFID PCB mounts behind this marker on the inside surface. RF passes through 5mm acrylic with negligible loss (acrylic is non-conductive and non-magnetic; thickness does not measurably affect 13.56MHz RFID read range).

### 5.3 TOP-FLAT (150 × 168)

- **LCD viewing cutout:** 98 × 40 mm rectangle with **square corners** (no fillets). Centered at (X=75, Y=35). Cut bounds: X 26–124, Y 15–55.
- **LCD mounting holes:** 4× Ø3.2 mm clearance holes at (X, Y) = (28.5, 7.5), (121.5, 7.5), (28.5, 62.5), (121.5, 62.5). Spacing 93 × 55 mm (matches standard 20×4 I2C LCD module).
- **Camera tower mount:** Ø8mm cable hole centered at (X=75, Y=110). 4× Ø3.2mm clearance holes around it at (X, Y) = (67, 102), (83, 102), (67, 118), (83, 118). Tower flange bolts down with 4× M3. *(Camera cable hole shifted from Y=120 to Y=110 to leave room for USB pass-through.)*
- **USB-plug pass-through:** 20 × 12 mm rectangle at center (X=75, Y=160). Fits a USB-A male plug **including the plastic housing/strain-relief** (metal connector 12×4.5mm + typical housing 15-18×8-10mm + 2-4mm clearance). Approximately 50mm behind the camera cable hole; 2mm margin to BACK edge of TOP.

### 5.4 LEFT (pentagon, removable)

Outline vertices (face-local Y horizontal-back from FRONT edge, Z vertical-up):
```
(Y=0,   Z=0)     -- SW corner
(Y=240, Z=0)     -- SE corner (BACK side)
(Y=240, Z=300)   -- NE corner
(Y=72,  Z=300)   -- top edge meets slope
(Y=0,   Z=228)   -- slope meets FRONT edge
```

**Mount holes** (Ø3.5mm clearance for M3 screws into wooden corner posts):
- Bottom-front: (Y=5, Z=8)
- Bottom-back: (Y=235, Z=8)
- Top-back: (Y=235, Z=292)
- Top-front: (Y=5, Z=213)

Holes inset 5–8 mm from edges to land on the 10×10mm wooden posts.

**PCB standoff mount holes:** 4× Ø3.2mm clearance for M3 screws into nylon standoffs. The motherboard PCB (200×120mm) sits on these standoffs against the inside surface of the LEFT panel. PCB long axis runs along trụ Y (depth), short axis along trụ Z. Hole positions (face-local Y, Z):
- (Y=25, Z=95) — PCB SE corner
- (Y=215, Z=95) — PCB SW corner
- (Y=25, Z=205) — PCB NE corner
- (Y=215, Z=205) — PCB NW corner

These match PCB-local mount points 5mm inset from the 200×120mm PCB corners.

### 5.5 RIGHT (pentagon, fixed)

Same outline as LEFT (mirrored). **Servo is NOT mounted to this panel** — it has been moved inside the trụ on a 3D-printed bracket (see §6). Internal cutouts:

- **Arm retraction slot:** 20 × 200 mm rectangle at (Y=120, Z=190). Spans Y 110–130 × Z 90–290. Allows the 150mm drop-arm to retract through the panel for the full sweep from θ=0° (closed horizontal) to θ=78.5° (arm tip retracted just past the panel into trụ interior). Slot top has 10mm margin from panel-top edge; slot bottom has 42mm clearance above the HC-SR04 PCB.
- **HC-SR04 transducer holes:** 2× Ø16mm at (Y=107, Z=40) and (Y=133, Z=40). Center-to-center **26mm** per HC-SR04 datasheet.
- **HC-SR04 PCB corner mount holes:** 4× Ø2.2mm clearance (for M2 screws into the HC-SR04 board's own corner holes). Positions (Y, Z):
  - (Y=99.5, Z=32) — board top-left
  - (Y=140.5, Z=32) — board top-right
  - (Y=99.5, Z=48) — board bottom-left
  - (Y=140.5, Z=48) — board bottom-right
  
  Spacing 41×16mm, derived from 45×20mm HC-SR04 PCB with 2mm corner inset.

### 5.6 BACK (150 × 300, removable)

- **Adapter cable hole:** Ø10mm at (X=17, Z=110). Rubber grommet press-fit. Position aligned with J_PWR barrel axis when PCB is on LEFT-panel standoffs (stack: 5mm LEFT panel + 5mm standoff + 1.6mm PCB + ~6mm to barrel center axis = trụ X≈17.6; barrel axis exits toward BACK at Y≈221.5, Z=110). Cable jumper inside trụ from hole to J_PWR is ~20mm.
- **Mount holes:** 6× Ø3.5mm clearance for M3 screws into wooden corner posts:
  - Bottom edge: (X=8, Z=8), (X=142, Z=8)
  - Top edge: (X=8, Z=292), (X=142, Z=292)
  - Mid edges: (X=8, Z=150), (X=142, Z=150)

### 5.7 BOTTOM (150 × 240)

- **Vent slots (optional):** 5× rectangular 30×3 mm slots, centered along the X axis, at Y = 40, 80, 120, 160, 200 — or skip if user prefers sealed bottom. Default: include slots for passive cooling of Pi.

### 5.8 Drop-arm (150 × 15 × 3)

- **Mounting holes:** 2× Ø2.2mm at distance 5mm and 13mm from one short end (8mm spacing matches SG90 1-arm horn).
- **Decoration:** 4 engraved stripes 20×5mm at X = 30, 60, 90, 120 (paint red after cutting for red/white barrier look). Stripes clear the 2 mount holes at X=5/13 and stay inside the 150mm arm length.

## 6. Internal mounting strategy

| Component | Mounted to | Method | Position |
|---|---|---|---|
| Motherboard PCB (200×120mm) | LEFT panel inside surface | 4× nylon standoff Ø6mm × 5mm tall on inside of LEFT panel + 4× M3×8 screws from outside LEFT through standoffs into PCB mount holes | PCB plane at trụ X=10 (5mm panel + 5mm standoff); top of PCB at X=11.6. PCB long axis along trụ Y (depth), short axis along trụ Z. PCB extends Y=20–220, Z=90–210. Pi 4 USB stack reaches X≈41.6 (points into trụ interior in +X direction). |
| Pi 4B | J_PI socket on PCB | Plug-in via socket | Pi sits in +X direction from PCB (into trụ interior). Pi USB stack reaches X≈39.6. |
| ESP32 DevKit | J_ESP socket on PCB | Plug-in | Co-located with PCB |
| LM2596 buck module | J_BUCK header | Plug-in | On PCB |
| LCD 20×4 module | TOP-FLAT inside surface | 4× M3×6 self-tap from outside through TOP into LCD module standoffs | Module body at Y_local 5–65, X 26–124. Header on east short edge (X=124 side) facing +X to reach J_LCD. |
| RC522 RFID | SLOPE facet inside surface | 4× M3 standoffs 5mm tall glued to SLOPE inside with acrylic cement; RC522 PCB bolted to standoffs | RC522 antenna pointing outward through SLOPE. PCB parallel to slope plane. |
| HC-SR04 module | RIGHT face inside surface | Module sits on inside surface of RIGHT panel; 2 transducer cylinders pass through the 2× Ø16mm holes; 4× M2 screws through M2 PCB corner holes from outside RIGHT into M2 nylon standoffs glued to inside | Transducers poke through the 2× Ø16mm holes at (Y=107, Z=40) and (Y=133, Z=40) |
| SG90 servo | 3D-printed bracket (`freecad/exports/servo_bracket.stl`) bonded to BOTTOM face inside trụ | Bracket positions servo shaft at trụ (X=120, Y=120, Z=100) with shaft axis along Y. 2× M2.5 screws secure servo flange to bracket wall. Bracket base bonded to BOTTOM face inside with acrylic cement. (TARGET_Z = 100 in `freecad/build_servo_bracket.py`) | Servo body bounding box approx X=113–126, Y=120–143, Z=89–111 |
| Drop-arm pivot | SG90 servo horn outside the servo body | 2× M2 screws through arm into horn arm | Pivot at trụ (X=120, Y=120, Z=100). Arm 150mm × 15mm × 3mm. Closed: arm horizontal +X, tip at (X=270, Z=100), extends through RIGHT-face slot. Open at θ=78.5°: arm tip at (X=150, Z=247) just inside trụ; at θ=90° (full vertical) arm at X=120, Z=100..250 entirely inside. |
| Camera tower | TOP-FLAT outside surface | 4× M3×10 through TOP from inside upward into tower flange | Cylindrical 3D-printed tower, Ø20mm × 120mm tall, USB cable runs inside cylinder |

## 7. Cable routing

| Cable | Length | From | To | Path |
|---|---|---|---|---|
| 12V DC | ~20 mm | Adapter (external) | J_PWR on PCB | Through Ø10mm BACK grommet at (X=15, Z=110) → ~20mm straight jumper inside trụ to J_PWR barrel jack |
| Pi power (5V) | — | LM2596 output (on-PCB) | Pi GPIO 5V pins via J_PI socket | Internal PCB trace, no external cable |
| LCD I2C (4-wire) | 250 mm | J_LCD on PCB | LCD module on TOP | Up along inside of RIGHT face, then over to LCD east-edge header |
| RFID SPI (7-wire) | 200 mm | J_RFID on PCB | RC522 on SLOPE | Up along inside of FRONT face, then to RC522 header |
| Servo (3-wire) | 150 mm | J_SVO on PCB | SG90 on bracket (BOTTOM inside) | From PCB on LEFT panel → east along BOTTOM to servo bracket at (X=120, Y=120, Z=0) |
| HC-SR04 (4-wire) | 180 mm | J_USR on PCB | HC-SR04 on RIGHT face | From PCB on LEFT panel → east to RIGHT face, up to Z=80 |
| Buzzer (2-wire) | 150 mm | J_BUZ on PCB | Buzzer (mounted where?) | **TBD — see §13** |
| USB webcam | 250 mm | Webcam in camera tower | Pi 4 USB port | Webcam at tower top → cable down inside cylinder → through TOP Ø8mm hole at (X=75, Y=110) → USB-A plug (including housing) threaded through TOP 20×12mm USB pass-through at (X=75, Y=160) → plug into Pi USB port |

All cables use Dupont female-female 40-pin sets (already in shopping list).

## 8. Joint geometry

### 8.1 Finger joints (for fixed faces: FRONT, RIGHT, TOP, SLOPE, BOTTOM)

Faces interlock with each other and with the wooden corner posts via finger joints (mộng âm dương).

- **Tab width:** 20 mm
- **Slot width:** 20 mm + 0.15 mm tolerance (= 20.15 mm in CAD)
- **Tab thickness:** 5 mm (= sheet thickness)
- **Pattern:** alternating 4 tabs / 3 slots per long edge, with 5mm flat margins at each end
- **Edge engagement:** 5 mm depth (= sheet thickness)
- **Bonding:** apply acrylic cement (Cosmofen PMMA) to all finger joints during assembly. Once cured (~10 min), bond is permanent.

### 8.2 Screwed faces (LEFT, BACK)

LEFT and BACK use M3 screws into the wooden corner posts. No finger joints. Posts have pre-drilled Ø2.7mm pilot holes for M3 self-tap (in pine wood).

### 8.3 Slope facet attachment

SLOPE is a quadrilateral 150 × 101.82 mm. It attaches at:
- Top edge: finger-joints into the FRONT edge of TOP-FLAT
- Bottom edge: finger-joints into the TOP edge of FRONT
- Left/Right edges: finger-joints into the angled top-front edges of LEFT and RIGHT pentagons

All 4 edges of SLOPE have matching finger joints with their respective neighbors.

## 9. PDF output specification

### 9.1 Generator script

Python script `freecad/laser_cut/build_mica_pillar.py`:
- Library: `ezdxf` (DXF) or `reportlab` (PDF). Choose `ezdxf` then convert to PDF via `cairo` or `matplotlib` for cleaner vector output.
- Parameters at top of script:
  - `MICA_THICKNESS = 5.0` mm
  - `KERF = 0.1` mm (laser kerf compensation)
  - `JOINT_TOLERANCE = 0.15` mm
  - `PILLAR_W = 150`, `PILLAR_D = 240`, `PILLAR_H = 300`
  - `SLOPE_PROJECTION = 72` (mm of slope projected on Y and Z)
- Output: `freecad/laser_cut/exports/mica_gate_pillar.pdf`

### 9.2 PDF layout conventions

- **Page size:** 1000 × 600 mm (1:1 scale with the laser sheet). The PDF is a layout reference; laser shops typically import the SVG directly into their CAM tool which reads geometry in absolute mm, ignoring page size.
- **Cut lines:** RGB(255, 0, 0), stroke width 0.001 mm (hairline) — most laser cutters interpret red as "cut"
- **Engrave lines:** RGB(0, 0, 0), stroke width 0.1 mm — most cutters interpret black as "engrave"
- **Etch fills (for RFID marker rectangle interior):** RGB(0, 0, 255), stroke width 0.05 mm
- **Each piece labeled** with engraved text at one corner: `FRONT`, `BACK`, `LEFT`, `RIGHT`, `TOP`, `SLOPE`, `BOTTOM`, `ARM`. *Disabled by default in the build script (`include_labels=False`) because some laser CAM tools interpret `<text>` elements as additional engrave paths. Re-enable only for human-readable proofs.*
- **Orientation arrow** engraved on each piece pointing toward the piece's "TOP edge" (the edge that mounts upward in the assembled pillar)
- **Title block** at one corner of the page: project name, date, mica thickness, scale 1:1

### 9.3 Nesting

Pieces arranged on 1000 × 600 mm sheet.
- Row 1: LEFT (240×300) + RIGHT (240×300) + FRONT (150×228) + BACK (150×300) — width 812, height 300
- Row 2: TOP (150×168) + SLOPE (150×101.8) + BOTTOM (150×240) + ARM (150×15) — width 632, height 240

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
   b. Glue 4× nylon standoffs to LEFT panel inside surface at PCB mount positions (Y=25/215, Z=95/205).
   c. Glue RC522 standoffs to SLOPE inside.
   d. Glue 4× M2 nylon standoffs to RIGHT inside at HC-SR04 PCB corner positions (around the 2× Ø16mm transducer holes).
5. **Glue SLOPE facet** to FRONT-top + LEFT-top-front + RIGHT-top-front edges. Use clamps to hold during cure.
6. **Glue TOP-FLAT** to LEFT-top + RIGHT-top + SLOPE-top + the (still-open) BACK-top edge. Wait for cure.
7. **Install components**:
   a. Plug Pi 4 + ESP32 + LM2596 into PCB sockets.
   b. Connect peripheral cables (I2C → LCD pigtail, SPI → RC522 pigtail, servo, HC-SR04, buzzer).
   c. Mount PCB to LEFT panel standoffs via 4× M3×8.
   d. Mount LCD onto TOP via 4× M3×6 from outside.
   e. Mount RC522 onto SLOPE standoffs.
   f. Mount HC-SR04 onto RIGHT standoffs.
   7a. 3D-print the servo bracket (`freecad/exports/servo_bracket.stl`). Bolt SG90 servo onto the bracket wall with 2× M2.5. Bond bracket base to BOTTOM face inside the trụ at position (X=120, Y=120, Z=0) using acrylic cement.
   g. Mount SG90 servo (already on bracket) inside trụ; bracket bonded to BOTTOM face.
   h. Bolt drop-arm onto SG90 horn via 2× M2×8; thread arm through RIGHT-face slot.
   i. Bolt camera tower (3D-printed) onto TOP via 4× M3×10. Thread USB webcam cable down through TOP Ø8mm hole into trụ. Plug into Pi USB port.
8. **Attach LEFT panel** (which carries the PCB) to wooden posts via 4× M3×12.
9. **Attach BACK panel** to wooden posts via 6× M3×12.
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
| RFID won't read through 5mm mica | Should not occur (RF transparent); verify RC522 antenna parallel to slope |
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
| 8 | 2026-05-31 | 5mm clear acrylic | Standard cheap stock (slightly pricier than 3mm); transparent shows internals for demo; 5mm is rigid in the hand at 30cm height. |
| 9 | 2026-05-31 | Wooden corner posts + finger joints | Acrylic alone too flexible; posts also accept M3 self-tap for removable panels |
| 10 | 2026-05-31 | BACK and LEFT removable for maintenance | RIGHT carries arm slot + HC-SR04 → must be fixed; LEFT gives PCB/component access (PCB mounted on LEFT inside), BACK gives cable/connector access |
| 11 | 2026-05-31 | Adapter 12V cable enters via BACK Ø10mm grommet | User picked BACK lower corner |
| 12 | 2026-05-31 | PDF output single A2 page, red=cut / black=engrave | Standard laser shop convention |
| 13 | 2026-05-31 | Slope facet 30mm × 30mm (was 60mm) | 60mm slope left too little TOP depth for LCD + camera mount |
| 14 | 2026-05-31 | Slope facet enlarged to 72mm × 72mm (hyp 101.82mm) | Provides sufficient facet area (70×40mm RFID module fits on slope); TOP shortened to 168mm, FRONT to 228mm |
| 15 | 2026-05-31 | Pivot moved inside trụ; arm slides through RIGHT-face slot when opened; arm length 200mm; 5 engraved stripes for red/white painting after cut. | User redesign: arm now pivots inside bracket, cleaner mechanism, better aesthetics with striped arm |
| 16 | 2026-05-31 | Arm pivot moved inside trụ; RIGHT face gets 20×130mm arm slot; servo relocated from RIGHT panel to a 3D-printed bracket on BOTTOM face; HC-SR04 lowered to Z=80 to avoid the arm slot. | Cleaner RIGHT face; bracket gives servo precise positioning at (X=120, Y=120, Z=150) |
| 17 | 2026-05-31 | HC-SR04 mount geometry corrected to PCB datasheet — 26mm transducer spacing, 4 M2 holes at PCB corners (45×20mm board, 41×16mm hole spacing). | Previous spec used 27mm spacing and only 2 mount holes — inaccurate; replaced with full 4-corner M2 mount |
| 18 | 2026-05-31 | LCD cutout uses square corners (rect, no fillet) per user request. | Some laser CAM tools handle filled rects more reliably than filleted paths; simpler output |
| 19 | 2026-05-31 | PCB motherboard mounted on LEFT panel (not BACK) — PCB long axis along trụ Y, short axis along trụ Z; 4 mount holes added to LEFT panel. | Fixes load asymmetry; keeps BACK free for easy removal; BACK now only carries the adapter hole |
| 20 | 2026-05-31 | BACK adapter cable hole repositioned from (X=15, Z=15) to (X=15, Z=110) to align with J_PWR barrel axis (PCB-on-LEFT geometry). | Cable jumper inside trụ drops from ~120mm to ~20mm; avoids awkward routing across the pillar base |
| 21 | 2026-05-31 | TOP gains 20×12mm USB-plug pass-through at (X=75, Y=160), 50mm behind camera cable hole so the webcam USB-A connector (including its plastic housing) can thread down to the Pi. | Keeps USB connection accessible without opening any panel |
| 22 | 2026-05-31 | Mica thickness 3mm → 5mm | User requested switch for sturdier feel. Acrylic cost +70%, cut time slightly longer. BACK adapter hole X shifted 15→17 to keep J_PWR barrel-axis alignment. PCB face at trụ X=10 (was 8). |
| 23 | 2026-05-31 | Arm shortened 200→150mm, pivot Z dropped 150→100, HC-SR04 lowered to Z=40 | Slot now stays within panel (Z=90-290) without touching panel top. Arm reaches θ=78.5° (full retract inside trụ) instead of being clipped at θ=73.5°. Arm tip at full retract lands at (X=150, Z=247) — entirely inside trụ. |

## 13. Open questions

1. **PCB mount hole positions** — ~~Assumed at PCB corners 5mm inset.~~ Now anchored — see §5.4 (LEFT panel) and §6 (internal mounting). PCB mount holes locked at 5mm inset from PCB corners. **Status: RESOLVED.**
2. **SG90 servo flange dimensions** — Servo no longer mounted to RIGHT panel; flange constraint moved to the 3D-printed bracket (which still uses the 28mm assumption — verify against user's specific SG90 before printing bracket). **Status: PARTIAL — verify bracket flange spacing against actual SG90 before 3D-printing.**
3. **Buzzer mounting location** — Not yet assigned a face. Options: (a) inside trụ, sound escapes via vent slots (muffled); (b) RIGHT face with a small Ø10mm hole; (c) BACK face inside surface, sound through panel. Default: inside trụ near BOTTOM vents. Confirm with user during implementation. **Status: TBD.**
4. **Camera tower geometry** — Sized Ø20mm × 120mm tall in this spec, but exact webcam dimensions vary. If user's webcam is a Logitech C270 (60×30×60mm), tower needs a top platform instead of a cylinder cap. Confirm webcam model before designing 3D-print STL.
5. **HC-SR04 transducer hole spacing** — ~~Assumed 27mm center-to-center.~~ Set to **26mm** per datasheet. **Status: RESOLVED.**
6. **Pi USB-C power input** — Existing PCB design feeds Pi via GPIO 5V from LM2596. This spec assumes the same path (no USB-C cable into trụ). If user later needs USB-C power, add a Ø6mm slot on BACK panel.
7. **Drop-arm rest position when closed** — Spec says arm horizontal pointing -Y (forward of FRONT). Confirm this matches user's intent for physical demo, or whether arm should point +Y (backward) when closed.
8. **Q8 RESOLVED: Arm shortened to 150mm; at full retract (θ=78.5°) and full vertical (θ=90°) the arm stays entirely within the trụ envelope. No longer protrudes above TOP face.**

## 14. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Finger-joint tolerance wrong → pieces won't fit | High on first cut | Cut test piece per §11.2 before full sheet |
| Acrylic cracks during M3 self-tap | Medium | All M3 threading is into wood, not acrylic; acrylic only has Ø3.2 clearance holes |
| 5mm mica still flexes if pushed laterally at 30cm height | Low | Wooden corner posts anchor structure; 5mm is rigid in hand-feel test |
| RFID reads weakly through 5mm mica + standoff gap | Low | RC522 antenna designed for 1-5cm range; gap of 5mm + 5mm mica = 10mm, well within range |
| Cable bundle binds when closing LEFT panel | Medium | Route cables to BACK side, away from LEFT panel; allow 20mm slack |
| Servo can't lift drop-arm (150mm × 15mm × 3mm acrylic) under its own weight | Low | SG90 stall torque ~1.8 kg·cm; 150mm × 15mm × 3mm acrylic ≈ 6g, moment arm ~75mm → torque ~0.045 kg·cm — well within SG90's 1.8 kg·cm rating |
| Glue cement attacks acrylic surface finish | Low | Cosmofen PMMA is designed for acrylic; apply only on joint edges, not faces |
| 3D-printed camera tower wobbles | Medium | Tower base flange should be ≥50mm diameter for stability; consider 5mm wall thickness |
| User's specific SG90 / RC522 / HC-SR04 part dimensions differ from spec | Medium | Per-component verification step before cutting (see open questions §13) |
