#!/usr/bin/env python3
"""Combined motherboard for smart_gate: Pi 5 + ESP32 DevKit + peripherals.

Per spec rev 2026-05-22:
  - Single 12V input, on-board buck 5V/5A feeds both Pi (via GPIO pin 2/4)
    and ESP32 (via LM1117-3.3 LDO for 3.3V logic).
  - Pi 5 plugs into 2x20 GPIO socket; ESP32 DevKit into 2x15 socket.
  - Runtime UART app comm: Pi pin 8/10 (GPIO14/15) <-> ESP32 GPIO 5/17.
  - USB cable from Pi to DevKit micro-USB retained for esptool flashing only.

Output:
  smart_gate_combined.net   -- KiCad netlist for PCB import
"""

import os
import sys

os.environ['KICAD6_SYMBOL_DIR'] = '/usr/share/kicad/symbols'
os.environ['KICAD6_FOOTPRINT_DIR'] = '/usr/share/kicad/footprints'

from skidl import (
    Part, Net, ERC, generate_netlist, generate_svg, generate_schematic,
    set_default_tool, KICAD,
    lib_search_paths, footprint_search_paths,
)

set_default_tool(KICAD)
lib_search_paths[KICAD].append('/usr/share/kicad/symbols')
footprint_search_paths[KICAD].append('/usr/share/kicad/footprints')

# =============================================================================
# Nets
# =============================================================================

GND  = Net('GND')
V12  = Net('+12V')
V5   = Net('+5V')
V3V3 = Net('+3V3')

# RC522 SPI
RC522_MOSI = Net('RC522_MOSI')
RC522_MISO = Net('RC522_MISO')
RC522_SCK  = Net('RC522_SCK')
RC522_CS   = Net('RC522_CS')
RC522_RST  = Net('RC522_RST')
RC522_IRQ  = Net('RC522_IRQ')

# LCD I2C
I2C_SDA = Net('I2C_SDA')
I2C_SCL = Net('I2C_SCL')

# HC-SR04
HCSR_TRIG     = Net('HCSR_TRIG')
HCSR_ECHO_5V  = Net('HCSR_ECHO_5V')
HCSR_ECHO_3V3 = Net('HCSR_ECHO_3V3')

SERVO_PWM = Net('SERVO_PWM')
BUZ_DRIVE = Net('BUZ_DRIVE')

# UART app link between Pi and ESP32 (3.3V CMOS, no level shifter)
PI_TX_TO_ESP_RX = Net('PI_TX_ESP_RX')   # Pi pin 8  -> ESP32 GPIO 5
PI_RX_FROM_ESP  = Net('ESP_TX_PI_RX')   # ESP32 GPIO 17 -> Pi pin 10

# Spare ESP32 GPIOs to expansion header
IO36 = Net('IO36')
IO39 = Net('IO39')


# =============================================================================
# Power input
# =============================================================================

J_PWR  = Part('Connector', 'Barrel_Jack', ref='J_PWR', value='12V_IN',
              footprint='Connector_BarrelJack:BarrelJack_Horizontal')
D_REV  = Part('Diode', '1N5817', ref='D_REV',
              footprint='Diode_THT:D_DO-201AD_P15.24mm_Horizontal')
C_BULK = Part('Device', 'C_Polarized', ref='C_BULK', value='100uF/25V',
              footprint='Capacitor_THT:CP_Radial_D8.0mm_P3.50mm')

J_PWR[1] += D_REV[2]
D_REV[1] += V12
J_PWR[2] += GND
C_BULK[1] += V12
C_BULK[2] += GND


# =============================================================================
# 5 V / 5 A buck module (off-the-shelf, represented as 4-pin header)
# =============================================================================

J_BUCK = Part('Connector_Generic', 'Conn_01x04', ref='J_BUCK', value='LM2596_Mini_Buck',
              footprint='smart_gate_combined:LM2596_Mini_Buck')
# Footprint pad numbering (custom LM2596_Mini_Buck):
#   pad 1 = IN+   (left top)
#   pad 2 = IN-   (left bottom)
#   pad 3 = OUT-  (right bottom)
#   pad 4 = OUT+  (right top)
J_BUCK[1] += V12   # IN+ (12V from D_REV)
J_BUCK[2] += GND   # IN-
J_BUCK[3] += GND   # OUT-
J_BUCK[4] += V5    # OUT+ (5V to filter / Pi GPIO)

# Bulk and filter on 5V rail (per spec §2.2)
C_5V_BULK = Part('Device', 'C_Polarized', ref='C_5V_BULK', value='1000uF/10V',
                 footprint='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm')
C_5V_BYP  = Part('Device', 'C', ref='C_5V_BYP', value='100nF',
                 footprint='Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm')
C_5V_BULK[1] += V5; C_5V_BULK[2] += GND
C_5V_BYP[1] += V5;  C_5V_BYP[2] += GND

# FB_PI ferrite bead removed (2026-05-23) — kept on V5 net only.
# Filter caps and TVS now attach directly to +5V (no separate filtered net).
PI_5V_NET = V5

C_PI_BULK = Part('Device', 'C_Polarized', ref='C_PI_BULK', value='1000uF/10V',
                 footprint='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm')
C_PI_BYP  = Part('Device', 'C', ref='C_PI_BYP', value='100nF',
                 footprint='Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm')
C_PI_BULK[1] += PI_5V_NET; C_PI_BULK[2] += GND
C_PI_BYP[1]  += PI_5V_NET; C_PI_BYP[2]  += GND

# TVS clamp for transient protection (5.0 V working, clamps ~9 V)
D_TVS = Part('Device', 'D_TVS', ref='D_TVS', value='SMAJ5.0A',
             footprint='Diode_THT:D_DO-15_P10.16mm_Horizontal')
D_TVS[1] += GND       # cathode = anode reversed for unidirectional TVS
D_TVS[2] += PI_5V_NET


# =============================================================================
# 3.3 V rail — sourced from ESP32 DevKit's onboard AMS1117-3.3
# =============================================================================
#
# The DevKit's 3V3 pin (J_ESP pin 1) is an OUTPUT from the onboard regulator
# that drops 5V (from VIN pin) down to 3.3V. Capacity ~500mA safe; our
# external 3V3 load is only ~31mA (RC522 ~30mA + LCD pull-ups ~1.4mA), well
# within budget. No separate LM1117 on the motherboard needed.


# =============================================================================
# Raspberry Pi 5 GPIO socket (2x20)
# Pi plugs DOWNWARDS into this socket; the motherboard hosts it.
# =============================================================================

J_PI = Part('Connector_Generic', 'Conn_02x20_Odd_Even', ref='J_PI',
            value='Pi_5_GPIO_2x20',
            footprint='Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical')

# Pin mapping per Raspberry Pi 5 GPIO header (BCM standard).
# Row A (odd pins, 1..39) on left side, Row B (even pins, 2..40) on right.
# Conn_02x20_Odd_Even numbering: pin 1=odd row1, pin 2=even row1, pin 3=odd row2 ...

J_PI[1]  += Net.fetch('_NC_PI_3V3_')   # Pi 3V3 out — not used by motherboard
J_PI[2]  += PI_5V_NET                   # 5V IN (powers Pi from buck)
J_PI[3]  += Net.fetch('_NC_PI3_SDA1_')  # GPIO 2 / I2C1 SDA — not used
J_PI[4]  += PI_5V_NET                   # 5V IN (parallel)
J_PI[5]  += Net.fetch('_NC_PI5_SCL1_')  # GPIO 3
J_PI[6]  += GND
J_PI[7]  += Net.fetch('_NC_PI7_GPIO4_') # GPIO 4
J_PI[8]  += PI_TX_TO_ESP_RX             # Pi GPIO14 / TX0
J_PI[9]  += GND
J_PI[10] += PI_RX_FROM_ESP              # Pi GPIO15 / RX0
J_PI[11] += Net.fetch('_NC_PI11_')      # GPIO 17
J_PI[12] += Net.fetch('_NC_PI12_')      # GPIO 18
J_PI[13] += Net.fetch('_NC_PI13_')      # GPIO 27
J_PI[14] += GND
J_PI[15] += Net.fetch('_NC_PI15_')      # GPIO 22
J_PI[16] += Net.fetch('_NC_PI16_')      # GPIO 23
J_PI[17] += Net.fetch('_NC_PI17_3V3_')  # Pi 3V3 out
J_PI[18] += Net.fetch('_NC_PI18_')      # GPIO 24
J_PI[19] += Net.fetch('_NC_PI19_')      # GPIO 10 / SPI0 MOSI
J_PI[20] += GND
J_PI[21] += Net.fetch('_NC_PI21_')      # GPIO 9 / SPI0 MISO
J_PI[22] += Net.fetch('_NC_PI22_')      # GPIO 25
J_PI[23] += Net.fetch('_NC_PI23_')      # GPIO 11 / SPI0 SCLK
J_PI[24] += Net.fetch('_NC_PI24_')      # GPIO 8 / SPI0 CE0
J_PI[25] += GND
J_PI[26] += Net.fetch('_NC_PI26_')      # GPIO 7 / SPI0 CE1
J_PI[27] += Net.fetch('_NC_PI27_ID_SD') # EEPROM data
J_PI[28] += Net.fetch('_NC_PI28_ID_SC') # EEPROM clock
J_PI[29] += Net.fetch('_NC_PI29_')      # GPIO 5
J_PI[30] += GND
J_PI[31] += Net.fetch('_NC_PI31_')      # GPIO 6
J_PI[32] += Net.fetch('_NC_PI32_')      # GPIO 12
J_PI[33] += Net.fetch('_NC_PI33_')      # GPIO 13
J_PI[34] += GND
J_PI[35] += Net.fetch('_NC_PI35_')      # GPIO 19
J_PI[36] += Net.fetch('_NC_PI36_')      # GPIO 16
J_PI[37] += Net.fetch('_NC_PI37_')      # GPIO 26
J_PI[38] += Net.fetch('_NC_PI38_')      # GPIO 20
J_PI[39] += GND
J_PI[40] += Net.fetch('_NC_PI40_')      # GPIO 21


# =============================================================================
# ESP32 DevKit socket (DOIT V1 30-pin, 2x 1x15 vertical female sockets)
# =============================================================================

# Single 2x15 connector with the project's custom footprint at 25.4 mm
# rail-to-rail spacing (matches DOIT V1 30-pin DevKit). Conn_02x15_Odd_Even
# numbering: odd pins = left rail (1, 3, 5, ..., 29), even pins = right
# rail (2, 4, 6, ..., 30), both top → bottom.
J_ESP = Part('Connector_Generic', 'Conn_02x15_Odd_Even', ref='J_ESP',
             value='ESP32_DevKit_V1',
             footprint='smart_gate_combined:ESP32_DevKit_V1_30pin')

# Pin map aligned with firmware decision #26 (2026-05-23):
#   RC522 CS=IO5, RST=IO17 (firmware config.h-aligned)
#   UART1 to Pi: TX=IO25 → Pi pin 10 (RX), RX=IO32 ← Pi pin 8 (TX)
#   I2C SDA moved to IO15 (strap HIGH, idle HIGH on I2C pull-up = OK)
#   HC-SR04 TRIG moved to IO4 (was RC522 RST, now free)
#
# --- Left rail (odd pins) per DOIT V1 silkscreen, top → bottom ---
J_ESP[1]  += V3V3                       # 3V3
J_ESP[3]  += Net.fetch('_NC_EN_')       # EN
J_ESP[5]  += IO36                       # VP / IO36
J_ESP[7]  += IO39                       # VN / IO39
J_ESP[9]  += HCSR_ECHO_3V3              # IO34 (in-only)
J_ESP[11] += RC522_MISO                 # IO35 (in-only)
J_ESP[13] += PI_TX_TO_ESP_RX            # IO32 = UART1 RX ← Pi TX (pin 8)
J_ESP[15] += I2C_SCL                    # IO33
J_ESP[17] += PI_RX_FROM_ESP             # IO25 = UART1 TX → Pi RX (pin 10)
J_ESP[19] += SERVO_PWM                  # IO26
J_ESP[21] += BUZ_DRIVE                  # IO27
J_ESP[23] += RC522_SCK                  # IO14
J_ESP[25] += Net.fetch('_NC_IO12_')     # IO12 strap LOW — NC
J_ESP[27] += GND
J_ESP[29] += RC522_MOSI                 # IO13

# --- Right rail (even pins) per DOIT V1 silkscreen, top → bottom ---
J_ESP[2]  += V5                         # VIN (5V)
J_ESP[4]  += GND
J_ESP[6]  += RC522_MOSI                 # IO13 (bridged with left pin 29)
J_ESP[8]  += Net.fetch('_NC_FLASH_D2_')
J_ESP[10] += Net.fetch('_NC_FLASH_D3_')
J_ESP[12] += Net.fetch('_NC_FLASH_CMD_')
J_ESP[14] += Net.fetch('_NC_FLASH_CLK_')
J_ESP[16] += Net.fetch('_NC_FLASH_SD0_')
J_ESP[18] += Net.fetch('_NC_FLASH_SD1_')
J_ESP[20] += I2C_SDA                    # IO15 = I2C SDA (strap HIGH, idle HIGH OK)
J_ESP[22] += Net.fetch('_NC_IO2_LED_')  # IO2 onboard LED — NC
J_ESP[24] += HCSR_TRIG                  # IO4  = HC-SR04 TRIG
J_ESP[26] += RC522_IRQ                  # IO16
J_ESP[28] += RC522_RST                  # IO17 = RC522 RST (firmware-aligned)
J_ESP[30] += RC522_CS                   # IO5  = RC522 CS  (firmware-aligned)

# ESP32 decoupling on 3V3
C_ESP_3V3_1 = Part('Device', 'C', ref='C_ESP_3V3_1', value='100nF',
                   footprint='Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm')
C_ESP_3V3_2 = Part('Device', 'C', ref='C_ESP_3V3_2', value='10uF',
                   footprint='Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm')
C_ESP_3V3_1[1] += V3V3;  C_ESP_3V3_1[2] += GND
C_ESP_3V3_2[1] += V3V3;  C_ESP_3V3_2[2] += GND


# =============================================================================
# Peripherals (unchanged from ESP32-only design)
# =============================================================================

J_RFID = Part('Connector_Generic', 'Conn_01x08', ref='J_RFID', value='RC522',
              footprint='Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
J_RFID[1] += RC522_CS
J_RFID[2] += RC522_SCK
J_RFID[3] += RC522_MOSI
J_RFID[4] += RC522_MISO
J_RFID[5] += RC522_IRQ
J_RFID[6] += GND
J_RFID[7] += RC522_RST
J_RFID[8] += V3V3

J_LCD = Part('Connector_Generic', 'Conn_01x04', ref='J_LCD', value='LCD_20x4_I2C',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical')
J_LCD[1] += GND
J_LCD[2] += V5
J_LCD[3] += I2C_SDA
J_LCD[4] += I2C_SCL

R_SDA = Part('Device', 'R', ref='R_SDA', value='4.7k',
             footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
R_SCL = Part('Device', 'R', ref='R_SCL', value='4.7k',
             footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
R_SDA[1] += I2C_SDA; R_SDA[2] += V3V3
R_SCL[1] += I2C_SCL; R_SCL[2] += V3V3

J_USR = Part('Connector_Generic', 'Conn_01x04', ref='J_USR', value='HC-SR04',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical')
J_USR[1] += V5
J_USR[2] += HCSR_TRIG
J_USR[3] += HCSR_ECHO_5V
J_USR[4] += GND

R_USR1 = Part('Device', 'R', ref='R_USR1', value='1k',
              footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
R_USR2 = Part('Device', 'R', ref='R_USR2', value='2k',
              footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
R_USR1[1] += HCSR_ECHO_5V
R_USR1[2] += HCSR_ECHO_3V3
R_USR2[1] += HCSR_ECHO_3V3
R_USR2[2] += GND

J_SVO = Part('Connector_Generic', 'Conn_01x03', ref='J_SVO', value='Servo_SG90',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical')
J_SVO[1] += GND
J_SVO[2] += V5
J_SVO[3] += SERVO_PWM
C_SVO = Part('Device', 'C_Polarized', ref='C_SVO', value='470uF/16V',
             footprint='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm')
C_SVO[1] += V5; C_SVO[2] += GND

J_BUZ = Part('Connector_Generic', 'Conn_01x02', ref='J_BUZ', value='Buzzer_Active',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical')
Q_BUZ = Part('Transistor_BJT', '2N3904', ref='Q_BUZ',
             footprint='Package_TO_SOT_THT:TO-92_Inline')
R_BUZ = Part('Device', 'R', ref='R_BUZ', value='1k',
             footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
BUZ_COLLECTOR = Net('BUZ_COLLECTOR')
Q_BUZ[1] += R_BUZ[2]
R_BUZ[1] += BUZ_DRIVE
Q_BUZ[2] += BUZ_COLLECTOR
Q_BUZ[3] += GND
J_BUZ[1] += V5
J_BUZ[2] += BUZ_COLLECTOR

J_EXP = Part('Connector_Generic', 'Conn_01x04', ref='J_EXP', value='Expansion',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical')
J_EXP[1] += V3V3
J_EXP[2] += GND
J_EXP[3] += IO36
J_EXP[4] += IO39


# =============================================================================
# Generate
# =============================================================================

if __name__ == '__main__':
    print('Running ERC ...', file=sys.stderr)
    ERC()
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_file = os.path.join(proj_dir, 'smart_gate_combined.net')
    generate_netlist(file_=out_file)
    print(f'Netlist written: {out_file}', file=sys.stderr)

    # Visualize the circuit (graphviz-driven auto layout — functional, not pretty)
    try:
        svg_file = os.path.join(proj_dir, 'smart_gate_combined.svg')
        generate_svg(file_=svg_file)
        print(f'SVG schematic written: {svg_file}', file=sys.stderr)
    except Exception as exc:   # noqa: BLE001
        print(f'generate_svg failed: {exc}', file=sys.stderr)
