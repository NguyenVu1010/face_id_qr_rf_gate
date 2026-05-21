# KiCad Schematic Implementation Plan — ESP32 Carrier Board

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Note for KiCad work:** schematic capture is mostly GUI-driven in Eeschema. The KiCad MCP server provides only read-only tools (`validate_project`, `extract_schematic_netlist`, `analyze_schematic_connections`) — use them to verify after each task instead of writing pytest. KiCad 6.0.2 (already installed) is sufficient; KiCad 9 upgrade is not blocking.

**Goal:** Produce a complete, ERC-clean KiCad schematic for the ESP32 carrier board described in spec §5 (pin assignment) and §2 (power topology). Output is `*.kicad_sch` files + netlist + BOM ready to hand off to the PCB layout plan.

**Architecture:** Single-sheet schematic. ESP32 DevKit socketed onto 2× 15-pin female headers — schematic shows the header pinout, not a bare WROOM-32 module. All peripherals are off-board modules connected via headers. Power input: 12 V DC barrel jack → buck module (4-pin header) → 5 V rail → AMS1117-3.3 LDO → 3.3 V rail.

**Tech Stack:** KiCad 6.0.2 (Eeschema), standard KiCad symbol libraries (`MCU_Module`, `Connector_Generic`, `Regulator_Linear`, `Device`, `Diode`, `Transistor_BJT`, `power`). No custom symbols required; if a part isn't in stock libraries, use generic connector + edit value/footprint manually.

**Spec source:** `docs/superpowers/specs/2026-05-21-smart-gate-architecture-design.md` — §2.2 power, §5 pin assignment.

**Project location:** `/home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier/`

---

## File Structure

```
smart_gate/
├── docs/superpowers/
│   ├── specs/2026-05-21-smart-gate-architecture-design.md   (input — read-only)
│   └── plans/2026-05-22-kicad-schematic.md                  (this file)
└── kicad/
    └── smart_gate_carrier/
        ├── smart_gate_carrier.kicad_pro      (project meta)
        ├── smart_gate_carrier.kicad_sch      (schematic — main and only sheet)
        ├── smart_gate_carrier.kicad_pcb      (empty placeholder; PCB plan fills this later)
        ├── sym-lib-table                     (project-local symbol libs, may be empty)
        ├── fp-lib-table                      (project-local footprint libs)
        ├── netlist/smart_gate_carrier.net    (generated)
        └── bom/smart_gate_carrier.csv        (generated)
```

---

## Components on schematic

| Ref | Value | Library / Symbol | Notes |
| --- | --- | --- | --- |
| `J_PWR` | DC barrel jack 5.5×2.1mm | `Connector:Barrel_Jack` | 12 V input |
| `D_REV` | 1N5817 | `Diode:1N5817` | Reverse-polarity protection on +12 V |
| `C_BULK` | 100 µF / 25 V electrolytic | `Device:C_Polarized` | After D_REV |
| `J_BUCK` | 4-pin header | `Connector_Generic:Conn_01x04` | Represents 12 V → 5 V buck module (MP1584/LM2596) |
| `U_LDO` | AMS1117-3.3 | `Regulator_Linear:AMS1117-3.3` | 5 V → 3.3 V |
| `C_LDOIN` / `C_LDOOUT` | 10 µF | `Device:C` | LDO bypass caps |
| `J_ESP_L` / `J_ESP_R` | 15-pin female header × 2 | `Connector_Generic:Conn_01x15` | ESP32 DevKit socket (left + right rails) |
| `C_ESP_3V3_1` | 100 nF | `Device:C` | Near ESP32 3.3 V pin |
| `C_ESP_3V3_2` | 10 µF | `Device:C` | Bulk near ESP32 3.3 V pin |
| `J_RFID` | 8-pin header | `Connector_Generic:Conn_01x08` | RC522 module |
| `J_LCD` | 4-pin header | `Connector_Generic:Conn_01x04` | LCD 20×4 I2C (GND/VCC/SDA/SCL) |
| `R_SDA` / `R_SCL` | 4.7 kΩ | `Device:R` | I2C pull-up to **3.3 V** |
| `J_USR` | 4-pin header | `Connector_Generic:Conn_01x04` | HC-SR04 |
| `R_USR1` / `R_USR2` | 1 kΩ / 2 kΩ | `Device:R` | ECHO voltage divider |
| `J_SVO` | 3-pin header | `Connector_Generic:Conn_01x03` | Servo SG90 |
| `C_SVO` | 470 µF / 16 V electrolytic | `Device:C_Polarized` | Servo bulk cap |
| `J_BUZ` | 2-pin header | `Connector_Generic:Conn_01x02` | Active buzzer |
| `Q_BUZ` | 2N3904 NPN | `Transistor_BJT:2N3904` | Buzzer driver |
| `R_BUZ` | 1 kΩ | `Device:R` | Q_BUZ base resistor |
| `D_BUZ` | 1N4148 | `Diode:1N4148` | Optional flyback across buzzer |
| `J_EXP` | 6-pin header | `Connector_Generic:Conn_01x06` | Spare GPIO breakout |

Power symbols: `+12V`, `+5V`, `+3V3`, `GND` (from `power` library), plus `PWR_FLAG` on the source side of each rail for ERC.

---

## Tasks

### Task 1: Initialize project and version control

**Files:**
- Create: `/home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier/smart_gate_carrier.kicad_pro`
- Create: `/home/nguyenvd/workspace/smart_gate/.gitignore`

- [ ] **Step 1: Initialize git in the smart_gate workspace** (if not already a repo)

```bash
cd /home/nguyenvd/workspace/smart_gate
git init
```

Expected: `Initialized empty Git repository in .../smart_gate/.git/`

- [ ] **Step 2: Create a .gitignore**

```bash
cat > /home/nguyenvd/workspace/smart_gate/.gitignore <<'EOF'
# KiCad backup and lock files
*-backups/
*.kicad_pcb-bak
*.kicad_sch-bak
*.kicad_prl
fp-info-cache
_autosave-*
# Generated artefacts
kicad/**/netlist/
kicad/**/bom/
kicad/**/gerber/
# Brainstorm session content
.superpowers/
# Python
__pycache__/
*.pyc
EOF
```

- [ ] **Step 3: Create the KiCad project directory**

```bash
mkdir -p /home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier
```

- [ ] **Step 4: Create the KiCad project in GUI**

Open KiCad: `kicad &` then File → New Project → set path to `/home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier/smart_gate_carrier.kicad_pro`. Uncheck "Create a new folder" (we created the folder ourselves).

KiCad will produce: `smart_gate_carrier.kicad_pro`, `smart_gate_carrier.kicad_sch`, `smart_gate_carrier.kicad_pcb`.

- [ ] **Step 5: Verify project is discoverable by the KiCad MCP**

Run via the MCP tool (in this Claude Code session):

```
mcp__kicad__list_projects
```

Expected: response includes an entry with `"path": ".../smart_gate_carrier/smart_gate_carrier.kicad_pro"`.

- [ ] **Step 6: Validate project file integrity**

```
mcp__kicad__validate_project  project_path="/home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier/smart_gate_carrier.kicad_pro"
```

Expected: `{"valid": true, "files_found": ["project", "pcb", "schematic"]}`.

- [ ] **Step 7: Commit the empty project**

```bash
cd /home/nguyenvd/workspace/smart_gate
git add .gitignore kicad/smart_gate_carrier/smart_gate_carrier.kicad_pro \
        kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch \
        kicad/smart_gate_carrier/smart_gate_carrier.kicad_pcb \
        docs/superpowers/specs/2026-05-21-smart-gate-architecture-design.md \
        docs/superpowers/plans/2026-05-22-kicad-schematic.md
git commit -m "chore: initialize smart_gate workspace with KiCad project and design docs"
```

---

### Task 2: Power input section (12 V jack + reverse protection + bulk cap)

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Open the schematic editor**

In KiCad project window, double-click `smart_gate_carrier.kicad_sch` to open Eeschema.

- [ ] **Step 2: Place the DC barrel jack**

Press `A` (Add Symbol). Search: `Barrel_Jack`. Pick `Connector:Barrel_Jack` (3-pin version with switch contact, or 2-pin version — 2-pin is fine for prototype). Place near top-left (X≈80mm, Y≈60mm). Set Reference: `J_PWR`. Set Value: `12V_IN`.

- [ ] **Step 3: Place the reverse-protection diode**

Press `A`. Search: `1N5817`. Place to the right of `J_PWR`. Set Reference: `D_REV`. Orient so anode connects to jack pin 1 (positive), cathode points toward the +12 V rail.

- [ ] **Step 4: Place the bulk capacitor**

Press `A`. Search: `C_Polarized`. Place to the right of `D_REV`. Set Reference: `C_BULK`. Set Value: `100uF/25V`.

- [ ] **Step 5: Add power port symbols**

Press `P` (Add Power Port). Place `+12V` at the cathode of D_REV. Place `GND` at the negative terminal of the jack and at the C_BULK negative pin. Add `PWR_FLAG` (from `power` library) attached to the +12V net (required for ERC to recognise the net as having a source).

- [ ] **Step 6: Wire everything**

Press `W` to start wires. Connect: J_PWR pin 1 → D_REV anode; D_REV cathode → C_BULK + → +12V. J_PWR pin 2 → GND. C_BULK − → GND. Press `Esc` to end wire.

- [ ] **Step 7: Save and run ERC**

`Ctrl+S` to save. Tools → Electrical Rules Checker (or button on toolbar). Run. Expected: no errors. Warnings about "unconnected" pins are normal at this stage — fix in later tasks.

- [ ] **Step 8: Validate via MCP and commit**

```
mcp__kicad__analyze_schematic_connections  project_path="/home/nguyenvd/workspace/smart_gate/kicad/smart_gate_carrier/smart_gate_carrier.kicad_pro"
```

Expected: nets `+12V`, `GND` reported.

```bash
cd /home/nguyenvd/workspace/smart_gate
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add 12V power input with reverse protection and bulk cap"
```

---

### Task 3: 5 V rail (buck module header)

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Place the buck module connector**

Press `A`. Search: `Conn_01x04`. Select `Connector_Generic:Conn_01x04`. Place below the 12 V section. Set Reference: `J_BUCK`. Set Value: `Buck_12V_to_5V`. Edit symbol fields → add note `MP1584 module or LM2596 module; pin order: VIN+, GND, GND, VOUT+`.

- [ ] **Step 2: Wire to power rails**

Press `W`. Connect pin 1 → +12V; pins 2 and 3 → GND; pin 4 → a new net. Press `L` (Add Label) and label that wire `+5V`. Add a `+5V` power port symbol on the same wire (Press `P`, search `+5V`). Add `PWR_FLAG` on the +5V net.

- [ ] **Step 3: Save and ERC**

`Ctrl+S`, then re-run ERC. Expected: still no errors; the `+5V` net should now appear.

- [ ] **Step 4: Validate via MCP and commit**

```
mcp__kicad__analyze_schematic_connections  project_path=".../smart_gate_carrier.kicad_pro"
```

Expected: nets list includes `+5V`.

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add 5V buck module header"
```

---

### Task 4: 3.3 V rail (AMS1117-3.3 LDO)

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Place the LDO**

Press `A`. Search: `AMS1117-3.3`. Select `Regulator_Linear:AMS1117-3.3`. Place to the right of the buck section. Reference: `U_LDO`. Pin order on this symbol: 1 = GND, 2 = VO, 3 = VI.

- [ ] **Step 2: Place input and output capacitors**

Press `A`. Search: `C`, place a non-polar 10 µF ceramic on the input side. Reference: `C_LDOIN`. Value: `10uF`. Place a second 10 µF on the output side. Reference: `C_LDOOUT`. Value: `10uF`.

- [ ] **Step 3: Wire it up**

- LDO pin 3 (VI) → +5V net (use label `+5V` or extend wire from previous section)
- LDO pin 2 (VO) → new net, label `+3V3`, attach `+3V3` power port + `PWR_FLAG`
- LDO pin 1 (GND) → GND
- C_LDOIN: one terminal to +5V, other to GND
- C_LDOOUT: one terminal to +3V3, other to GND

- [ ] **Step 4: Save, ERC, validate, commit**

`Ctrl+S`. Tools → ERC. Expected: no errors.

```
mcp__kicad__analyze_schematic_connections  project_path=".../smart_gate_carrier.kicad_pro"
```

Expected: `+3V3` net present.

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add AMS1117-3.3 LDO for 3.3V rail"
```

---

### Task 5: ESP32 DevKit socket (2× 15-pin headers)

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

The DevKit plugs into two parallel female headers. We represent each as a `Conn_01x15` and label each pin with its GPIO / function from spec §5.

- [ ] **Step 1: Place left header**

Press `A`. Search: `Conn_01x15`. Place on left of central area (X≈140mm, Y≈100mm). Reference: `J_ESP_L`. Value: `DevKit_L`.

- [ ] **Step 2: Place right header**

Same symbol, place ~25.4 mm (1 inch) to the right of `J_ESP_L`. Reference: `J_ESP_R`. Value: `DevKit_R`.

- [ ] **Step 3: Label every pin per DOIT ESP32 DevKit V1 (30-pin) left rail, top → bottom**

The DOIT V1 is the most common 30-pin DevKit. **GPIO 6–11 are connected to the SPI flash inside the WROOM-32 module and are NOT exposed on the header.** They never appear on the schematic.

Use `L` (Add Net Label) on each pin of `J_ESP_L`:

| Hdr pin | DevKit silkscreen | Net label |
| --- | --- | --- |
| 1 | `3V3` | `+3V3` (power port) |
| 2 | `EN` | leave open + No-Connect symbol |
| 3 | `VP` (GPIO36, IN only) | `IO36` |
| 4 | `VN` (GPIO39, IN only) | `IO39` |
| 5 | `IO34` (IN only) | `HCSR_ECHO_3V3` |
| 6 | `IO35` (IN only) | `RC522_MISO` |
| 7 | `IO32` | `I2C_SDA` |
| 8 | `IO33` | `I2C_SCL` |
| 9 | `IO25` | `HCSR_TRIG` |
| 10 | `IO26` | `SERVO_PWM` |
| 11 | `IO27` | `BUZ_DRIVE` |
| 12 | `IO14` | `RC522_SCK` |
| 13 | `IO12` (strap, must boot LOW) | leave open + No-Connect (do not route) |
| 14 | `GND` | `GND` (power port) |
| 15 | `IO13` | `RC522_MOSI` |

- [ ] **Step 4: Label every pin of `J_ESP_R` per DOIT V1 right rail, top → bottom**

| Hdr pin | DevKit silkscreen | Net label |
| --- | --- | --- |
| 1 | `VIN` | `+5V` (power port) |
| 2 | `GND` | `GND` (power port) |
| 3 | `IO13` | *(same GPIO as left pin 15 — DOIT V1 bridges IO13; share `RC522_MOSI`)* |
| 4 | `D2 / SHD` | leave open + No-Connect *(flash D2 pin, exposed on some revs but unsafe to drive)* |
| 5 | `D3 / SWP` | leave open + No-Connect |
| 6 | `CMD` | leave open + No-Connect |
| 7 | `CLK` | leave open + No-Connect |
| 8 | `SD0` | leave open + No-Connect |
| 9 | `SD1` | leave open + No-Connect |
| 10 | `IO15` (strap, must boot HIGH) | `RC522_CS` |
| 11 | `IO2` (strap, must boot LOW; onboard LED) | leave open + No-Connect (LED is on DevKit itself) |
| 12 | `IO4` | `RC522_RST` |
| 13 | `IO16` | `RC522_IRQ` |
| 14 | `IO17` | `IO17` (spare → J_EXP) |
| 15 | `IO5` (strap, must boot HIGH) | `IO5` (spare → J_EXP) |

*(Pin 4–9 on the right rail are flash signals routed out on some 30-pin DevKits but should NOT be connected externally. Mark each with a No-Connect symbol (`Q` key) to silence ERC.)*

- [ ] **Step 5: Mark No-Connect pins**

Per spec §5 (revised 2026-05-22 for 30-pin DevKit): IO18/19/21/22/23 are NOT exposed on the 30-pin header — they remain internal to the WROOM-32 module. SPI and I2C are remapped to GPIOs that ARE exposed (already labelled above). No "missing pins" to handle.

Use the No-Connect symbol (press `Q`) on every pin marked "leave open + No-Connect" in the two tables: pin 2 (EN), pin 13 (IO12 — strap LOW), and right-rail pins 4–9 (flash) and 11 (IO2 onboard LED).

- [ ] **Step 6: Save, ERC**

`Ctrl+S`. Run ERC. Expected: warnings about unconnected nets `RC522_*`, `I2C_*`, etc. — these resolve when peripheral connectors are added in Tasks 6–10.

- [ ] **Step 7: Add 3.3 V decoupling near ESP32**

Press `A`. Place two `C` symbols near the +3V3 pin of J_ESP_L. References: `C_ESP_3V3_1` (value `100nF`) and `C_ESP_3V3_2` (value `10uF`). Each between +3V3 and GND.

- [ ] **Step 8: Save, ERC, validate, commit**

```
mcp__kicad__analyze_schematic_connections  project_path=".../smart_gate_carrier.kicad_pro"
```

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add ESP32 DevKit socket and pin labels"
```

---

### Task 6: RC522 RFID connector

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

RC522 module standard 8-pin order: SDA(CS), SCK, MOSI, MISO, IRQ, GND, RST, 3.3V.

- [ ] **Step 1: Place the connector**

Press `A`. Place `Connector_Generic:Conn_01x08` near the right side of the sheet. Reference: `J_RFID`. Value: `RC522`.

- [ ] **Step 2: Label and wire each pin**

| Hdr pin | Net |
| --- | --- |
| 1 | `RC522_CS` |
| 2 | `RC522_SCK` |
| 3 | `RC522_MOSI` |
| 4 | `RC522_MISO` |
| 5 | `RC522_IRQ` |
| 6 | `GND` |
| 7 | `RC522_RST` |
| 8 | `+3V3` |

Use net labels (`L`) for pins 1–5 and 7; use power port symbols for pins 6 and 8.

- [ ] **Step 3: Save, ERC, validate, commit**

ERC: unconnected warnings on RC522_* nets should disappear (they now connect to ESP32 headers via shared net labels).

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add RC522 RFID connector"
```

---

### Task 7: LCD 20×4 I2C connector with pull-ups

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Place the connector**

Press `A`. Place `Connector_Generic:Conn_01x04`. Reference: `J_LCD`. Value: `LCD_20x4_I2C`.

Standard LCD I2C backpack pinout: GND, VCC (5 V), SDA, SCL.

| Hdr pin | Net |
| --- | --- |
| 1 | `GND` |
| 2 | `+5V` |
| 3 | `I2C_SDA` |
| 4 | `I2C_SCL` |

- [ ] **Step 2: Add pull-up resistors to 3.3 V**

Per spec §5.2, cut the LCD backpack's on-board 5 V pull-ups and use 3.3 V pull-ups on the carrier:

Press `A`. Place two `Device:R`. References: `R_SDA`, `R_SCL`. Values: `4.7k`. Connect:

- R_SDA: one terminal to `I2C_SDA` net, other to `+3V3`
- R_SCL: one terminal to `I2C_SCL` net, other to `+3V3`

- [ ] **Step 3: Add silkscreen note**

Add a graphical text annotation near `J_LCD`: `"⚠ Cut LCD backpack pull-ups (R8/R9); use 3V3 pull-ups on carrier"`. Right-click → Add → Text. Place near connector.

- [ ] **Step 4: Save, ERC, validate, commit**

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add LCD 20x4 I2C connector with 3V3 pull-ups"
```

---

### Task 8: HC-SR04 connector with ECHO voltage divider

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Place the connector**

Press `A`. `Connector_Generic:Conn_01x04`. Reference: `J_USR`. Value: `HC-SR04`.

| Hdr pin | Net |
| --- | --- |
| 1 | `+5V` |
| 2 | `HCSR_TRIG` |
| 3 | `HCSR_ECHO_5V` |
| 4 | `GND` |

- [ ] **Step 2: Build voltage divider on ECHO line**

Press `A`. Place two `Device:R`:
- `R_USR1` value `1k` — in series between `HCSR_ECHO_5V` (from connector) and `HCSR_ECHO_3V3` (to ESP32 GPIO 26)
- `R_USR2` value `2k` — from `HCSR_ECHO_3V3` to `GND`

This divides 5 V → ~3.33 V at the ESP32 pin.

- [ ] **Step 3: TRIG line direct**

`HCSR_TRIG` from connector goes directly to net label `HCSR_TRIG` (which is connected to ESP32 GPIO 27 via the ESP32 header in Task 5).

- [ ] **Step 4: Save, ERC, validate, commit**

```
mcp__kicad__analyze_schematic_connections  project_path=".../smart_gate_carrier.kicad_pro"
```

Expected: nets `HCSR_TRIG`, `HCSR_ECHO_5V`, `HCSR_ECHO_3V3` reported.

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add HC-SR04 connector with ECHO voltage divider"
```

---

### Task 9: Servo connector with bulk cap

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Place the connector**

Press `A`. `Connector_Generic:Conn_01x03`. Reference: `J_SVO`. Value: `Servo_SG90`.

Standard SG90 wire order: brown=GND, red=VCC, orange=signal.

| Hdr pin | Net |
| --- | --- |
| 1 | `GND` |
| 2 | `+5V` |
| 3 | `SERVO_PWM` |

- [ ] **Step 2: Add 470 µF bulk cap near connector**

Press `A`. `Device:C_Polarized`. Reference: `C_SVO`. Value: `470uF/16V`. Place visually close to `J_SVO`. Connect + to `+5V`, − to `GND`.

- [ ] **Step 3: Save, ERC, validate, commit**

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add servo connector with 470uF bulk cap"
```

---

### Task 10: Buzzer with NPN driver

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Place the buzzer header**

Press `A`. `Connector_Generic:Conn_01x02`. Reference: `J_BUZ`. Value: `Buzzer_Active`.

- [ ] **Step 2: Place the NPN driver**

Press `A`. Search: `2N3904`. Pick `Transistor_BJT:2N3904`. Reference: `Q_BUZ`. Place near the buzzer header.

- [ ] **Step 3: Place the base resistor**

Press `A`. `Device:R`. Reference: `R_BUZ`. Value: `1k`. One terminal to net `BUZ_DRIVE` (from ESP32 GPIO 14), other to Q_BUZ base.

- [ ] **Step 4: Wire the buzzer circuit**

- J_BUZ pin 1 (+) → `+5V`
- J_BUZ pin 2 (−) → Q_BUZ collector
- Q_BUZ emitter → `GND`
- Q_BUZ base → R_BUZ → `BUZ_DRIVE`

- [ ] **Step 5: Optional flyback diode**

Press `A`. Search `1N4148`. Reference: `D_BUZ`. Place across the buzzer (anode at collector, cathode at +5V). This protects against any inductive kickback if the buzzer has a coil element.

- [ ] **Step 6: Save, ERC, validate, commit**

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add active buzzer with NPN 2N3904 driver"
```

---

### Task 11: Expansion header for spare GPIOs

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Place the header**

Press `A`. `Connector_Generic:Conn_01x06`. Reference: `J_EXP`. Value: `Expansion`.

| Hdr pin | Net |
| --- | --- |
| 1 | `+3V3` |
| 2 | `GND` |
| 3 | `IO17` |
| 4 | `IO5` |
| 5 | `IO36` |
| 6 | `IO39` |

Spare GPIOs not exposed on this header (left as test points or unconnected): IO12 (strap, never route), IO2 (onboard LED on DevKit). All other GPIOs are either reserved for peripherals or do not exist on this DevKit variant.

- [ ] **Step 2: Save, ERC, validate, commit**

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "feat(kicad): add 6-pin expansion header with spare GPIOs"
```

---

### Task 12: Full ERC, annotate, and clean-up

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Annotate the schematic**

In Eeschema: Tools → Annotate Schematic. Use "Use the first free number after". Click Annotate. This sets every reference to a unique numbered value (R1, R2, … C1, C2, … J1, J2, …) if any were placeholders.

If you used custom references like `J_RFID`, `J_LCD`, etc. as suggested above, annotation should leave them alone (KiCad recognises them as already-set). Verify by scrolling the schematic — no `?` symbols on any reference.

- [ ] **Step 2: Run full ERC**

Tools → Electrical Rules Checker. Click "Run ERC".

Expected: **0 errors**. Warnings to investigate:
- "Pin not connected" on the ESP32 flash pins (IO6–11): expected; mark with "No-Connect" symbol (`Q` key) to silence.
- "Pin not connected" on ESP32 EN: expected; DevKit has its own EN pull-up. Mark No-Connect.
- "Power input not driven by a power output": means a PWR_FLAG is missing somewhere. Add it.

Fix all errors. Iterate until ERC reports 0 errors.

- [ ] **Step 3: Save and validate**

`Ctrl+S`.

```
mcp__kicad__analyze_schematic_connections  project_path=".../smart_gate_carrier.kicad_pro"
```

Expected: all expected nets present (+12V, +5V, +3V3, GND, RC522_*, I2C_*, HCSR_*, SERVO_PWM, BUZ_DRIVE, IO*).

- [ ] **Step 4: Commit**

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "fix(kicad): annotate references and resolve ERC errors"
```

---

### Task 13: Assign footprints

**Files:**
- Modify: `kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch`

- [ ] **Step 1: Open the footprint assignment dialog**

In Eeschema: Tools → Assign Footprints.

- [ ] **Step 2: Map each symbol to a footprint**

| Component | Footprint |
| --- | --- |
| `J_PWR` (DC jack) | `Connector_BarrelJack:BarrelJack_Horizontal` |
| `D_REV` (1N5817) | `Diode_SMD:D_SMA` or `Diode_THT:D_DO-201AD_P15.24mm_Horizontal` |
| `C_BULK` (100µF/25V) | `Capacitor_THT:CP_Radial_D8.0mm_P3.50mm` |
| `J_BUCK` (buck module hdr) | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical` |
| `U_LDO` (AMS1117-3.3) | `Package_TO_SOT_SMD:SOT-223-3_TabPin2` |
| `C_LDOIN`, `C_LDOOUT` (10µF) | `Capacitor_SMD:C_0805_2012Metric` |
| `J_ESP_L`, `J_ESP_R` | `Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical` *(female socket to receive DevKit headers)* |
| `C_ESP_3V3_1` (100nF) | `Capacitor_SMD:C_0805_2012Metric` |
| `C_ESP_3V3_2` (10µF) | `Capacitor_SMD:C_0805_2012Metric` |
| `J_RFID` | `Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical` |
| `J_LCD` | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical` |
| `R_SDA`, `R_SCL` (4.7k) | `Resistor_SMD:R_0805_2012Metric` |
| `J_USR` | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical` |
| `R_USR1` (1k), `R_USR2` (2k) | `Resistor_SMD:R_0805_2012Metric` |
| `J_SVO` | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical` |
| `C_SVO` (470µF) | `Capacitor_THT:CP_Radial_D10.0mm_P5.00mm` |
| `J_BUZ` | `Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical` |
| `Q_BUZ` (2N3904) | `Package_TO_SOT_THT:TO-92_Inline` |
| `R_BUZ` (1k) | `Resistor_SMD:R_0805_2012Metric` |
| `D_BUZ` (1N4148) | `Diode_SMD:D_SOD-123` |
| `J_EXP` | `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical` |

*(If a footprint is missing from your KiCad install, switch the symbol to use a similar generic footprint and note it in the commit message.)*

- [ ] **Step 3: Apply and close**

Click "Apply, Save Schematic & Continue" then close the dialog.

- [ ] **Step 4: Verify in BOM**

Tools → Generate BOM. Open the generated CSV. Verify every component has a footprint column populated.

- [ ] **Step 5: Commit**

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier.kicad_sch
git commit -m "chore(kicad): assign footprints to all schematic symbols"
```

---

### Task 14: Generate netlist and BOM

**Files:**
- Create: `kicad/smart_gate_carrier/netlist/smart_gate_carrier.net`
- Create: `kicad/smart_gate_carrier/bom/smart_gate_carrier.csv`

- [ ] **Step 1: Generate netlist**

In Eeschema: Tools → Generate Netlist File → KiCadXML or PCBnew (default). Save to `kicad/smart_gate_carrier/netlist/smart_gate_carrier.net`.

- [ ] **Step 2: Generate BOM**

Tools → Generate BOM. Use `bom_csv_grouped_by_value` plugin. Save to `kicad/smart_gate_carrier/bom/smart_gate_carrier.csv`.

- [ ] **Step 3: Validate via MCP**

```
mcp__kicad__extract_schematic_netlist  project_path=".../smart_gate_carrier.kicad_pro"
mcp__kicad__analyze_bom  project_path=".../smart_gate_carrier.kicad_pro"
```

Expected: BOM contains all ~20 unique components; netlist contains all expected nets.

- [ ] **Step 4: Commit (with generated artefacts tracked or git-ignored per policy)**

The `.gitignore` from Task 1 excludes `netlist/` and `bom/` by default, but tracking them with the repo is also reasonable. Pick one and document. If tracking:

```bash
# Override .gitignore for this commit
git add -f kicad/smart_gate_carrier/netlist/smart_gate_carrier.net kicad/smart_gate_carrier/bom/smart_gate_carrier.csv
git commit -m "chore(kicad): generate netlist and BOM"
```

---

### Task 15: Final verification and handoff

**Files:** none modified.

- [ ] **Step 1: Run all MCP validators one more time**

```
mcp__kicad__validate_project           project_path=".../smart_gate_carrier.kicad_pro"
mcp__kicad__get_project_structure      project_path=".../smart_gate_carrier.kicad_pro"
mcp__kicad__analyze_schematic_connections  project_path=".../smart_gate_carrier.kicad_pro"
mcp__kicad__extract_schematic_netlist  project_path=".../smart_gate_carrier.kicad_pro"
```

Expected: all return `valid=true` and lists of components/nets matching this plan.

- [ ] **Step 2: Cross-check against spec**

Open `docs/superpowers/specs/2026-05-21-smart-gate-architecture-design.md` §5 (pin assignment) and verify every row's ESP32 pin → net mapping is realised in the schematic.

Spot-check items (remapped pins for 30-pin DevKit):
- GPIO 13 → `RC522_MOSI` net → `J_RFID` pin 3 ✓
- GPIO 14 → `RC522_SCK` net → `J_RFID` pin 2 ✓
- GPIO 35 (IN only) → `RC522_MISO` net → `J_RFID` pin 4 ✓
- GPIO 15 → `RC522_CS` net → `J_RFID` pin 1 ✓
- GPIO 32 → `I2C_SDA` net → `J_LCD` pin 3 + R_SDA pull-up to +3V3 ✓
- GPIO 33 → `I2C_SCL` net → `J_LCD` pin 4 + R_SCL pull-up to +3V3 ✓
- GPIO 25 → `HCSR_TRIG` net → `J_USR` pin 2 ✓
- GPIO 34 (IN only) → `HCSR_ECHO_3V3` (via R_USR1/R_USR2 divider, not direct) ✓
- GPIO 26 → `SERVO_PWM` net → `J_SVO` pin 3 ✓
- GPIO 27 → `BUZ_DRIVE` → R_BUZ → Q_BUZ base ✓
- GPIO 12 → No-Connect (strap LOW at boot) ✓
- Flash pins (D2/D3/CMD/CLK/SD0/SD1) → No-Connect ✓
- IO2 (onboard LED) → No-Connect on header (LED is on DevKit) ✓

- [ ] **Step 3: Generate a PDF print of the schematic**

In Eeschema: File → Plot → Plot. Output format: PDF. Save to `kicad/smart_gate_carrier/smart_gate_carrier_schematic.pdf`.

```bash
git add kicad/smart_gate_carrier/smart_gate_carrier_schematic.pdf
git commit -m "docs(kicad): export schematic as PDF for review"
```

- [ ] **Step 4: Mark plan complete**

The schematic is ready to be the input to the next plan (KiCad PCB layout). Hand off:
- `smart_gate_carrier.kicad_sch` — source of truth
- `smart_gate_carrier.net` — netlist for PCB
- `smart_gate_carrier.csv` — BOM
- `smart_gate_carrier_schematic.pdf` — review artefact

---

## Verification checklist (run before merging or starting PCB plan)

- [ ] ERC reports 0 errors (warnings on flash pins acknowledged with No-Connect symbols)
- [ ] Every ESP32 GPIO in spec §5 has a labelled net on the schematic
- [ ] HC-SR04 ECHO has the 1 kΩ + 2 kΩ divider (NOT direct to 5 V)
- [ ] LCD I2C has 4.7 kΩ pull-ups to **3.3 V** (NOT 5 V), and a note about cutting backpack pull-ups
- [ ] Servo connector has 470 µF bulk cap
- [ ] Buzzer has 2N3904 + 1 kΩ base resistor + (optional) 1N4148 flyback
- [ ] +12 V has reverse-protection diode
- [ ] All four rails (+12V, +5V, +3V3, GND) have `PWR_FLAG`
- [ ] Every symbol has a footprint assigned
- [ ] Netlist and BOM generated and inspected
- [ ] PDF print produced for design review
- [ ] All changes committed to git with descriptive messages

---

## Out of scope (next plan)

- PCB layout (placement, routing, copper pours, silkscreen)
- Gerber generation
- 3D viewer verification against FreeCAD STEP
- Manufacturing assembly drawing
- Test points for production test

These are handled by the upcoming `2026-05-XX-kicad-pcb-layout.md` plan, which takes this schematic's netlist as input.
