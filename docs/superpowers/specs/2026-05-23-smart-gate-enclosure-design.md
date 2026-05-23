# Smart Gate Enclosure Design

**Date:** 2026-05-23
**Status:** Spec, pending implementation
**Owner:** dev_kicad (design session)
**Consumed by:** FreeCAD enclosure implementation (3D print)

## 1. Goal

Design a 3D-printed enclosure that houses the smart_gate controller PCB (motherboard + Pi 4B + ESP32 DevKit + LM2596 buck), with cable exits to peripherals mounted on the model gate pillar. The enclosure also carries the LCD 20×4 status display on its lid (admin view).

This spec replaces the previous ad-hoc 220×140×62.5mm box design that had incorrect Pi 4 orientation, a 47.8mm USB cable run, and an LCD cutout that overlapped a wall.

## 2. Scope

**In scope:**
- 3-piece 3D-printable enclosure (box body + connector plate + lid)
- PCB mounting (4× M3 standoff)
- External connector access (DC jack, Pi USB cluster, Pi USB-C, LCD on lid)
- Wire exit slots with strain relief for peripheral cables
- Assembly procedure & verification checklist

**Out of scope:**
- Mounting the enclosure to anything (sits free on desk for prototype)
- Weatherproofing / IP rating (indoor desk demo only)
- Camera/RFID/HC-SR04/buzzer/servo physical mounting (those live on the model gate pillar, not in this enclosure)
- PCB redesign — enclosure follows current PCB connector positions

## 3. Architecture

Three printed parts joined with M3 fasteners:

```
                          Box NORTH (Y=0)
                    ┌──────────────────────────┐
                    │ CONNECTOR PLATE (removable)│  ← Pi USB cluster
                    │ Eth | USB3 | USB2          │     (cable ~15mm)
   Box WEST         └──────────────────────────┘            Box EAST
   ┌─DC─┐    ┌────────────────────────────────────┐    ┌────────┐
   │jack│    │                                    │    │ wire   │
   │    │    │   PCB + Pi (Pi long axis ↕)        │    │ exits  │
   │    │    │   Pi extends X=[108.7, 164.7]      │    │ to LCD │
   │    │    │   Pi extends Y=[17.95, 102.95]     │    │ etc.   │
   │    │    │                                    │    │        │
   └────┘    └────────────────────────────────────┘    └────────┘
                    ┌──────────────────────────┐
                    │ USB-C cable hole         │  ← Pi USB-C (cable ~35mm)
                    └──────────────────────────┘
                          Box SOUTH (Y=135)
```

**Box body** (single piece): floor + 3 walls (south, east, west) + 4 corner pillars. North wall is open (just a thin 5mm frame with M3 threaded holes for plate mounting). Floor has 4 standoffs for PCB.

**Connector plate** (removable, north wall): holds Pi USB cluster opening. Detaching it exposes the entire Pi USB-side for Pi removal/reflash.

**Lid** (top): flat plate carrying the LCD 20×4 module. 4× M3 corner screws into heat-set inserts in the box body's corner pillars.

## 4. Dimensions & materials

### 4.1 Box dimensions

| Axis | Outer | Inner | Rationale |
|------|-------|-------|-----------|
| X (width) | **210 mm** | 205 mm | PCB 201.7mm + 1.65mm clearance each side |
| Y (depth) | **135 mm** | 130 mm | PCB 119.6mm + 5.2mm clearance each side |
| Z (height) | **70 mm** | 64 mm (floor top to lid bottom) | Tall Pi USB stack + 30mm headroom for cable management & airflow |

### 4.2 Vertical stack (Z budget)

```
z=70.0  ← top of lid
        Lid 3.5mm
z=66.5  ← lid bottom
        Empty (29.9mm — cable management + airflow)
z=36.6  ← top of Pi USB stack
        Pi USB connector 15.6mm
z=21.0  ← top of Pi PCB
        Pi PCB 1.4mm
z=19.6  ← bottom of Pi PCB
        J_PI socket 11mm (pin + housing)
z=8.6   ← top of motherboard PCB
        Motherboard PCB 1.6mm
z=7.0   ← bottom of motherboard PCB
        Standoff 4.5mm
z=2.5   ← top of floor
        Floor 2.5mm
z=0     ← box bottom
```

### 4.3 Material & print settings

- **Filament:** PLA (default). PETG acceptable.
- **Wall thickness:** 2.5mm (6 perimeters at 0.4mm nozzle).
- **Lid thickness:** 3.5mm.
- **Layer height:** 0.2mm.
- **Infill:** 20% gyroid.
- **Supports:** none — all walls flat, no overhangs >45°.
- **Print orientation:**
  - Box body: floor on bed.
  - Lid & connector plate: lying flat.

### 4.4 Fasteners

| Purpose | Type | Qty | Location |
|---------|------|-----|----------|
| Lid screws | M3×12 Phillips | 4 | Corner pillars (into heat-set inserts) |
| Plate screws | M3×8 Phillips | 4 | North wall frame (into heat-set inserts) |
| PCB screws | M3×6 | 4 | PCB mount holes into printed standoffs (self-tap into Ø2.7mm) |
| LCD module screws | M3×6 | 4 | LCD module corners into lid (self-tap into Ø2.7mm) |
| Heat-set inserts | M3 brass, OD 4.6mm, length 5mm | 8 | 4 lid pillars + 4 plate frame |
| Standoff (printed) | Ø6mm × 4.5mm tall, M3 self-tap pilot hole Ø2.7mm | 4 | Floor at PCB mount positions |

**Total filament estimate:** ~150g (~120g box + ~20g plate + ~30g lid).

## 5. Cutout positions

All coordinates in box reference frame: origin = SW-bottom corner, X→east, Y→north, Z→up.

PCB origin in box: PCB_OX=4.13mm, PCB_OY=7.69mm (PCB centered in inner box footprint).

### 5.1 PCB connector positions (derived from `smart_gate_combined.kicad_pcb`)

| Header | PCB-local (mm) | Box (mm) |
|--------|---------------|----------|
| J_PWR (DC jack) | (12.46, 19.68) | (16.59, 27.37) |
| J_PI (Pi 2×20 socket, rot=180°) | (108.06, 91.76) | (112.19, 99.45) |
| J_LCD (I2C 4-pin) | (186.80, 57.48) | (190.93, 65.17) |

### 5.2 Pi 4B orientation on motherboard

Pi 4B layout: GPIO on one long edge (85mm); USB-C/HDMI/audio on one short edge; Ethernet + USB stacks on the opposite short edge.

With J_PI rot=180°, Pi maps onto motherboard as:

| Pi-local edge | → motherboard edge | Box-Y position |
|---|---|---|
| Pi LEFT short edge (USB-C + HDMI + audio) | Pi SOUTH edge | box-Y ≈ 102.95 |
| Pi RIGHT short edge (Ethernet + USB) | Pi NORTH edge | box-Y ≈ 17.95 |
| Pi TOP long edge (GPIO) | aligned with socket | box-Y = 17.95 to 102.95 |
| Pi BOTTOM long edge (bare) | Pi WEST edge | box-X ≈ 108.69 |

Pi extends in box: X=[108.69, 164.69], Y=[17.95, 102.95].

### 5.3 Pi connector positions (in box coords)

**On Pi NORTH edge (box-Y ≈ 17.95):**

| Connector | Box X | Box Z center | Cable run to north wall |
|---|---|---|---|
| Ethernet RJ45 | 119.69 | 29 | 15.45mm |
| USB 3.0 pair | 133.69 | 29 | 15.45mm |
| USB 2.0 pair | 150.69 | 29 | 15.45mm |

**On Pi SOUTH edge (box-Y ≈ 102.95):**

| Connector | Box X | Box Z center | Cable run to south wall |
|---|---|---|---|
| USB-C power | 119.69 | 28 | 32.05mm |
| Micro-HDMI 0 | 133.69 | 28 | — (not exposed) |
| Micro-HDMI 1 | 143.69 | 28 | — (not exposed) |
| Audio jack | 157.69 | 28 | — (not exposed) |

### 5.4 Cutouts on box body

| Wall | Cutout | Position | Size |
|---|---|---|---|
| EAST (X=210) | DC jack | center (Y=27.4, Z=14.6) | round Ø11mm. Internal cable ~185mm from J_PWR header east to wall. |
| SOUTH (Y=135) | USB-C cable | center (X=119.7, Z=28) | oval 12×6mm |
| WEST (X=0) | Peripheral wire exits | distributed at peripheral header Y positions | rect 15×10mm each (Y×Z), 4 slots at Y=[25, 55, 80, 105] |
| North wall frame | Plate mount holes | 4× along frame | M3 heat-set holes Ø4.2mm |

Standoffs in floor (assume PCB mount holes at corners with 5mm inset):

| Standoff | Box X | Box Y |
|---|---|---|
| SW | 9.13 | 12.69 |
| SE | 200.87 | 12.69 |
| NW | 9.13 | 122.31 |
| NE | 200.87 | 122.31 |

**Note:** Actual PCB mount hole positions must be verified from the PCB file during implementation (MountingHole footprints or Edge.Cuts geometry). If different from above, adjust standoff positions accordingly.

### 5.5 Cutouts on connector plate (north wall, Y=0)

Single combined opening for Pi USB cluster:

- **Pi USB cluster cutout:** rectangular, X=[109, 159], Z=[20, 38]. Size 50×18mm.
- **4× M3 mounting holes** at plate corners, threading into heat-set inserts on box-body frame.

Rationale for single opening (vs. 3 separate per-connector cutouts): easier to print, more forgiving of ±1mm misalignment, USB cables plug in without precision.

### 5.6 Cutouts on lid

LCD 20×4 with I2C backpack (module 98×60mm, visible area 76×26mm, mount holes 93×55mm spacing).

LCD module mounted **on the underside of the lid** (display panel pointing down through lid cutout, viewable from above the box).

**LCD position on lid:**
- Long axis (98mm) along box X
- Short axis (60mm) along box Y
- Module center: box (X=105, Y=67.5)
- Line 1 of text on Y_low edge (= LCD module's north edge, closest to admin standing at north wall)
- Character 1 on X_low edge (read left-to-right with admin standing at north)

**Pin header (4-pin I2C) on LCD module's east short edge** (closest to J_LCD on PCB). The 4 LCD mount holes are arranged symmetrically (93×55mm spacing), so user can rotate LCD 180° if the specific module ships with header on a different short edge.

| Lid cutout | Position | Size |
|---|---|---|
| LCD viewing window | center (105, 67.5) | rect 76×26mm |
| LCD SW mount hole | (58.5, 40) | self-tap pilot Ø2.7mm × 5mm deep (M3) |
| LCD SE mount hole | (151.5, 40) | self-tap pilot Ø2.7mm × 5mm deep (M3) |
| LCD NW mount hole | (58.5, 95) | self-tap pilot Ø2.7mm × 5mm deep (M3) |
| LCD NE mount hole | (151.5, 95) | self-tap pilot Ø2.7mm × 5mm deep (M3) |
| Lid screws (4 corners) | (5, 5), (205, 5), (5, 130), (205, 130) | clearance hole Ø3.2mm (M3 pass-through to heat-set inserts in box) |

## 6. Cable management

### 6.1 Cable inventory

| Cable | From | To | Path |
|---|---|---|---|
| 12V DC | external power supply | J_PWR | West wall round hole |
| Pi 5V USB-C | external USB-C supply | Pi USB-C port | South wall oval, ~32mm into box |
| Pi USB (webcam) | external webcam | Pi USB port | Through connector plate cluster |
| Pi Ethernet | router | Pi RJ45 | Through connector plate cluster |
| LCD I2C (4 wires) | J_LCD on PCB | LCD on lid | Inside box: ~60mm up + ~37mm west |
| RFID SPI (7 wires) | J_RFID | RC522 on pillar | East wall slot |
| Ultrasonic (4 wires) | J_ULTRA | HC-SR04 on pillar | East wall slot |
| Servo (3 wires) | J_SERVO | SG90 on barrier | East wall slot |
| Buzzer (2 wires) | J_BUZ | Buzzer on pillar | East wall slot |

### 6.2 Strain relief

Each east-wall exit slot and the south-wall USB-C cutout has a **printed zip-tie post** on the floor:

- Post dimensions: 8mm tall, Ø4mm with a Ø2mm horizontal slot for zip-tie passage
- Position: 5mm inside the wall, aligned with the corresponding slot
- The wire bundle exits the slot, passes around the post, and is secured with a 2.5mm zip-tie
- External pulling force is borne by the post, not the PCB header

### 6.3 LCD I2C cable

- 4-pin Dupont cable, **150mm length** with female connectors on both ends
- Routes from J_LCD upward (Z+) then west to LCD east-edge header
- No specific cable channel — cable hangs loose in the 30mm headroom above PCB

## 7. Assembly procedure

1. Print all 3 parts. Trim burrs after printing.
2. Press 8× M3 heat-set inserts into the box body (4 lid pillars + 4 plate frame) with a soldering iron at 200°C.
3. Screw the motherboard PCB onto the 4 standoffs with M3×6 screws.
4. Plug Pi 4 into J_PI socket (orient with pin 1 alignment).
5. Plug ESP32 DevKit into J_ESP socket.
6. Connect peripheral wires (RFID, ultrasonic, servo, buzzer) to their PCB headers. Route bundles through east-wall slots, secure each with a zip-tie around the strain-relief post.
7. Plug I2C cable into J_LCD (other end left disconnected for now).
8. Screw LCD module onto the lid's underside with 4× M3×6 screws.
9. Plug the I2C cable's free end into the LCD module's I2C header.
10. Slide the connector plate against the north-wall frame, secure with 4× M3×8 screws.
11. Close the lid (route I2C cable so it isn't pinched). Secure with 4× M3×12 screws at corners.

**Total assembly time:** ~30-45 minutes first time, ~10 minutes on reassembly.

## 8. Testing & verification

### 8.1 Pre-print checks (FreeCAD)

- All cutouts present and approximately sized correctly (visual inspection)
- Boolean operations produced non-empty solid (`Shape.Volume > 0` for each piece)
- Wall thickness ≥ 2.5mm everywhere
- No overhangs > 45° (visual inspection of cutout edges)
- Standoff height = 4.5mm
- Heat-set insert holes Ø4.2mm × 5.5mm deep

### 8.2 Test prints (before full print)

To save filament and time, print 2 small fragments first:

1. **Calibration cube + 1 standoff + 1 heat-set hole** (~5g, ~30 min): verify heat-set insert fit and M3 screw threading.
2. **Mini connector plate fragment** showing only the Pi USB cluster cutout (~10g, ~45 min): verify USB cable + Ethernet RJ45 cable fit through the opening.

Proceed to full print only if both pass.

### 8.3 Full print

| Part | Filament | Time (Ender 3, 0.2mm, 20% infill) |
|---|---|---|
| Box body | ~100g | ~8-10h |
| Connector plate | ~20g | ~1.5h |
| Lid | ~30g | ~2.5h |
| **Total** | **~150g** | **~12-14h** |

### 8.4 Post-print fit checks

In order — stop if a step fails:

| Step | Pass criterion |
|---|---|
| 1. Install 8 heat-set inserts | All flush, none tilted or sunk too deep |
| 2. Mount PCB | 4× M3 screws thread cleanly, PCB sits flat |
| 3. Plug Pi 4 | Sits flat without force; top of Pi USB at z=36.5 ±1mm |
| 4. Verify Pi USB vs. plate cutout | Offset ≤ 1mm in both X and Z |
| 5. Connect external DC jack | Mates with J_PWR through west-wall hole |
| 6. Connect external USB-C | Cable passes through south-wall hole, plugs into Pi |
| 7. Route peripheral wires | No pinching; zip-tie posts hold under pull test |
| 8. Mount LCD + connect I2C | LCD sits flat; cable doesn't bind |
| 9. Close lid | Gap ≤ 0.5mm; 4 screws thread cleanly |
| 10. Power-on test | LCD displays text; Pi and ESP32 boot |

### 8.5 Iteration loop

| Failure mode | Fix |
|---|---|
| Cutout off by 1-2mm | Tweak constant in FreeCAD code, reprint just that part |
| Pi sits too high for cutout | Reduce standoff height; reprint box body |
| Wall too flexible | Increase infill to 35% or wall to 3.0mm |
| Heat-set insert too loose | Reduce insert hole Ø4.2 → 4.0mm; reprint |

### 8.6 Acceptance criteria

Enclosure is **accepted** when all of:
- All components (PCB, Pi, ESP32) fit without forcing
- All external connectors (DC, USB-C, Pi USB cluster) are accessible from outside
- LCD readable through the lid cutout, viewing from box NORTH side
- All peripheral wires exit east wall without binding
- Lid closes flush, screws hold securely
- Full system powers on and operates (Pi boots, ESP32 boots, LCD displays text)

## 9. Decisions log

| # | Date | Decision | Rationale |
|---|------|----------|-----------|
| 1 | 2026-05-23 | Enclosure houses controller PCB only; sensors live on the gate pillar | User requirement (desk prototype model) |
| 2 | 2026-05-23 | 3-piece design: box body + removable connector plate + lid | Modular (plate can be re-printed if PCB connectors change); easy service access |
| 3 | 2026-05-23 | Connector plate on NORTH wall (Pi USB cluster) | Pi short-edge with 3 connectors is the connector-richest wall |
| 4 | 2026-05-23 | Box outer 210×135×70mm | Fits PCB + Pi with airflow + cable management headroom |
| 5 | 2026-05-23 | 3D print FDM in PLA, 2.5mm walls, 4× M3 heat-set inserts for lid + 4× for plate | Prototype-grade; reusable threads for iterative assembly |
| 6 | 2026-05-23 | LCD 20×4 mounted on the lid underside, viewable from above | Admin reads system status from north side of box |
| 7 | 2026-05-23 | LCD I2C header on LCD module's east short edge | Minimizes I2C cable length to J_LCD on east of PCB |
| 8 | 2026-05-23 | DC jack on WEST wall (round Ø11mm) | J_PWR is 16mm from west wall — shortest cable path |
| 9 | 2026-05-23 | Pi USB-C accessed via cable through south-wall oval hole | No panel-mount adapter — user threads USB-C cable through the hole |
| 10 | 2026-05-23 | Peripheral wires exit east wall via oval slots with printed zip-tie posts | Most peripheral headers sit on east half of PCB |

## 10. Open questions

1. **PCB mount hole positions** — Assumed at (5, 5), (PCB_W-5, 5), (5, PCB_D-5), (PCB_W-5, PCB_D-5). Implementation must verify by reading actual MountingHole footprints from `smart_gate_combined.kicad_pcb`. If different, adjust standoff X/Y to match.
2. **DC barrel jack orientation** — Spec assumes J_PWR's plug opening faces west. Implementation must verify from PCB footprint rotation; if it faces north or south, the wall placement of the cutout changes.
3. **LCD module I2C header location** — Varies between manufacturers. Spec assumes east short edge; if not, user must rotate the LCD module physically or extend the I2C cable.
4. **Peripheral header positions on PCB** — East-wall wire-exit slots assume J_RFID, J_ULTRA, J_SERVO, J_BUZ are on the east half of the PCB. Implementation must extract actual positions and place slots accordingly.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Standoff height drift causes Pi USB to misalign with cutout | Use printed test cube to calibrate before full print |
| 210×135mm bed size too large for some printers | Spec fits Ender 3 (220×220 bed); for smaller printers, split box body into 2 halves with dovetail joint (not in current scope) |
| LCD I2C cable noise over 100mm+ length | Use shielded cable or twisted pair if SDA/SCL errors observed; reduce I2C speed to 100kHz |
| Pi USB cable pulls heavily on the connector plate | Zip-tie strain relief inside connector plate area (not currently specified — add if cable strain becomes an issue) |
| Filament shrinkage causes 0.5mm fit error | Print box body first as test, verify dimensions before printing lid + plate |
