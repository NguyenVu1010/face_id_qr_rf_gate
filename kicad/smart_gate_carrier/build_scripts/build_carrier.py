#!/usr/bin/env python3
"""
Smart Gate ESP32 Carrier Board — circuit description in SKiDL.

Generates a KiCad netlist that can be imported directly into Pcbnew (PCB layout
editor) without going through Eeschema (schematic capture). The netlist captures
all electrical connections per spec §5 (pin assignment) and §2 (power topology).

Spec source:
  docs/superpowers/specs/2026-05-21-smart-gate-architecture-design.md

Output:
  smart_gate_carrier.net   — KiCad netlist
"""

import os
import sys

# Tell SKiDL where to find KiCad 6 symbol libraries (Ubuntu 22.04 default path).
os.environ['KICAD6_SYMBOL_DIR'] = '/usr/share/kicad/symbols'
os.environ['KICAD6_FOOTPRINT_DIR'] = '/usr/share/kicad/footprints'

from skidl import (
    Part, Net, ERC, generate_netlist, set_default_tool, KICAD,
    lib_search_paths, footprint_search_paths,
)
# NC is injected into Python builtins by skidl on import (default_circuit.NC)

set_default_tool(KICAD)
lib_search_paths[KICAD].append('/usr/share/kicad/symbols')
footprint_search_paths[KICAD].append('/usr/share/kicad/footprints')


# =============================================================================
# Nets
# =============================================================================

# Power rails
GND  = Net('GND')
V12  = Net('+12V')
V5   = Net('+5V')
V3V3 = Net('+3V3')

# Signal nets — names match spec §4 net contract
RC522_MOSI = Net('RC522_MOSI')
RC522_MISO = Net('RC522_MISO')
RC522_SCK  = Net('RC522_SCK')
RC522_CS   = Net('RC522_CS')
RC522_RST  = Net('RC522_RST')
RC522_IRQ  = Net('RC522_IRQ')

I2C_SDA = Net('I2C_SDA')
I2C_SCL = Net('I2C_SCL')

HCSR_TRIG     = Net('HCSR_TRIG')
HCSR_ECHO_5V  = Net('HCSR_ECHO_5V')
HCSR_ECHO_3V3 = Net('HCSR_ECHO_3V3')

SERVO_PWM = Net('SERVO_PWM')
BUZ_DRIVE = Net('BUZ_DRIVE')

# Spare pins exposed on expansion header
IO5  = Net('IO5')
IO17 = Net('IO17')
IO36 = Net('IO36')
IO39 = Net('IO39')


# =============================================================================
# Power input — 12V jack → reverse-protection diode → bulk cap
# =============================================================================

J_PWR = Part('Connector', 'Barrel_Jack', ref='J_PWR', value='12V_IN',
             footprint='Connector_BarrelJack:BarrelJack_Horizontal')
D_REV = Part('Diode', '1N5817', ref='D_REV',
             footprint='Diode_THT:D_DO-201AD_P15.24mm_Horizontal')
C_BULK = Part('Device', 'C_Polarized', ref='C_BULK', value='100uF/25V',
              footprint='Capacitor_THT:CP_Radial_D8.0mm_P3.50mm')

# Barrel_Jack: pin 1 = +, pin 2 = -, pin 3 = switch (NC for 2-pin variant)
J_PWR[1] += D_REV['K' if 'K' in [p.name for p in D_REV.pins] else 1]  # see below
# Simpler form using pin numbers (standard KiCad diode: 1=K, 2=A or vice versa)
# Let SKiDL/KiCad confirm; net connectivity is what matters.
# We connect anode→ to J_PWR+, cathode→ to +12V net.
# 1N5817 from KiCad library: pin K=1, A=2 (cathode is pin 1)
# Reset and redo cleanly:
J_PWR[1] += D_REV[2]   # anode (pin 2 = A in KiCad Diode lib)
D_REV[1] += V12        # cathode (pin 1 = K) → +12V rail
J_PWR[2] += GND
C_BULK[1] += V12       # + terminal of polarized cap
C_BULK[2] += GND


# =============================================================================
# 5V rail — buck module (pre-made, represented as 4-pin header)
# =============================================================================

J_BUCK = Part('Connector_Generic', 'Conn_01x04', ref='J_BUCK', value='Buck_12V_to_5V',
              footprint='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical')
# Pinout convention for off-the-shelf MP1584/LM2596 module:
#   pin 1 = VIN+
#   pin 2 = GND (VIN-)
#   pin 3 = GND (VOUT-)
#   pin 4 = VOUT+
J_BUCK[1] += V12
J_BUCK[2] += GND
J_BUCK[3] += GND
J_BUCK[4] += V5


# =============================================================================
# 3.3V rail — AMS1117-3.3 LDO
# =============================================================================

U_LDO   = Part('Regulator_Linear', 'AMS1117-3.3', ref='U_LDO',
               footprint='Package_TO_SOT_SMD:SOT-223-3_TabPin2')
C_LDOIN  = Part('Device', 'C', ref='C_LDOIN',  value='10uF',
                footprint='Capacitor_SMD:C_0805_2012Metric')
C_LDOOUT = Part('Device', 'C', ref='C_LDOOUT', value='10uF',
                footprint='Capacitor_SMD:C_0805_2012Metric')

# AMS1117-3.3 KiCad symbol: pin 1=GND, pin 2=VO, pin 3=VI
U_LDO[1] += GND
U_LDO[2] += V3V3
U_LDO[3] += V5

C_LDOIN[1] += V5;  C_LDOIN[2] += GND
C_LDOOUT[1] += V3V3; C_LDOOUT[2] += GND


# =============================================================================
# ESP32 DevKit socket — 2× 1×15 female headers (DOIT V1 30-pin)
# =============================================================================

J_ESP_L = Part('Connector_Generic', 'Conn_01x15', ref='J_ESP_L', value='DevKit_L',
               footprint='Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical')
J_ESP_R = Part('Connector_Generic', 'Conn_01x15', ref='J_ESP_R', value='DevKit_R',
               footprint='Connector_PinSocket_2.54mm:PinSocket_1x15_P2.54mm_Vertical')

# Left rail, top → bottom per DOIT V1 silkscreen
J_ESP_L[1]  += V3V3            # 3V3
J_ESP_L[2]  += NC              # EN — handled by DevKit internally
J_ESP_L[3]  += IO36            # VP / IO36 (in-only)
J_ESP_L[4]  += IO39            # VN / IO39 (in-only)
J_ESP_L[5]  += HCSR_ECHO_3V3   # IO34 (in-only) ← divider output
J_ESP_L[6]  += RC522_MISO      # IO35 (in-only)
J_ESP_L[7]  += I2C_SDA         # IO32
J_ESP_L[8]  += I2C_SCL         # IO33
J_ESP_L[9]  += HCSR_TRIG       # IO25
J_ESP_L[10] += SERVO_PWM       # IO26
J_ESP_L[11] += BUZ_DRIVE       # IO27
J_ESP_L[12] += RC522_SCK       # IO14
J_ESP_L[13] += NC              # IO12 strap LOW — must not be routed
J_ESP_L[14] += GND
J_ESP_L[15] += RC522_MOSI      # IO13

# Right rail, top → bottom
J_ESP_R[1]  += V5              # VIN
J_ESP_R[2]  += GND
J_ESP_R[3]  += RC522_MOSI      # IO13 (DOIT V1 bridges IO13 across rails)
J_ESP_R[4]  += NC              # D2/SHD  flash
J_ESP_R[5]  += NC              # D3/SWP  flash
J_ESP_R[6]  += NC              # CMD     flash
J_ESP_R[7]  += NC              # CLK     flash
J_ESP_R[8]  += NC              # SD0     flash
J_ESP_R[9]  += NC              # SD1     flash
J_ESP_R[10] += RC522_CS        # IO15
J_ESP_R[11] += NC              # IO2 onboard LED — DevKit drives it internally
J_ESP_R[12] += RC522_RST       # IO4
J_ESP_R[13] += RC522_IRQ       # IO16
J_ESP_R[14] += IO17            # IO17 spare
J_ESP_R[15] += IO5             # IO5  spare


# =============================================================================
# ESP32 3.3 V decoupling
# =============================================================================

C_ESP_3V3_1 = Part('Device', 'C', ref='C_ESP_3V3_1', value='100nF',
                   footprint='Capacitor_SMD:C_0805_2012Metric')
C_ESP_3V3_2 = Part('Device', 'C', ref='C_ESP_3V3_2', value='10uF',
                   footprint='Capacitor_SMD:C_0805_2012Metric')
C_ESP_3V3_1[1] += V3V3;  C_ESP_3V3_1[2] += GND
C_ESP_3V3_2[1] += V3V3;  C_ESP_3V3_2[2] += GND


# =============================================================================
# RC522 RFID — 8-pin connector (SDA/SCK/MOSI/MISO/IRQ/GND/RST/3.3V)
# =============================================================================

J_RFID = Part('Connector_Generic', 'Conn_01x08', ref='J_RFID', value='RC522',
              footprint='Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
J_RFID[1] += RC522_CS      # SDA = CS
J_RFID[2] += RC522_SCK
J_RFID[3] += RC522_MOSI
J_RFID[4] += RC522_MISO
J_RFID[5] += RC522_IRQ
J_RFID[6] += GND
J_RFID[7] += RC522_RST
J_RFID[8] += V3V3


# =============================================================================
# LCD 20×4 I2C — 4-pin connector with 3.3 V pull-ups
# =============================================================================

J_LCD = Part('Connector_Generic', 'Conn_01x04', ref='J_LCD', value='LCD_20x4_I2C',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical')
J_LCD[1] += GND
J_LCD[2] += V5
J_LCD[3] += I2C_SDA
J_LCD[4] += I2C_SCL

R_SDA = Part('Device', 'R', ref='R_SDA', value='4.7k',
             footprint='Resistor_SMD:R_0805_2012Metric')
R_SCL = Part('Device', 'R', ref='R_SCL', value='4.7k',
             footprint='Resistor_SMD:R_0805_2012Metric')
R_SDA[1] += I2C_SDA;  R_SDA[2] += V3V3
R_SCL[1] += I2C_SCL;  R_SCL[2] += V3V3


# =============================================================================
# HC-SR04 ultrasonic — 4-pin connector + ECHO voltage divider
# =============================================================================

J_USR = Part('Connector_Generic', 'Conn_01x04', ref='J_USR', value='HC-SR04',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical')
J_USR[1] += V5
J_USR[2] += HCSR_TRIG
J_USR[3] += HCSR_ECHO_5V
J_USR[4] += GND

R_USR1 = Part('Device', 'R', ref='R_USR1', value='1k',
              footprint='Resistor_SMD:R_0805_2012Metric')
R_USR2 = Part('Device', 'R', ref='R_USR2', value='2k',
              footprint='Resistor_SMD:R_0805_2012Metric')
# Divider: 5V echo → R1 → ESP32 node → R2 → GND
R_USR1[1] += HCSR_ECHO_5V
R_USR1[2] += HCSR_ECHO_3V3
R_USR2[1] += HCSR_ECHO_3V3
R_USR2[2] += GND


# =============================================================================
# Servo SG90 — 3-pin connector + 470 µF bulk cap
# =============================================================================

J_SVO = Part('Connector_Generic', 'Conn_01x03', ref='J_SVO', value='Servo_SG90',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical')
J_SVO[1] += GND
J_SVO[2] += V5
J_SVO[3] += SERVO_PWM

C_SVO = Part('Device', 'C_Polarized', ref='C_SVO', value='470uF/16V',
             footprint='Capacitor_THT:CP_Radial_D10.0mm_P5.00mm')
C_SVO[1] += V5
C_SVO[2] += GND


# =============================================================================
# Active buzzer + NPN driver
# =============================================================================

J_BUZ = Part('Connector_Generic', 'Conn_01x02', ref='J_BUZ', value='Buzzer_Active',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical')
Q_BUZ = Part('Transistor_BJT', '2N3904', ref='Q_BUZ',
             footprint='Package_TO_SOT_THT:TO-92_Inline')
R_BUZ = Part('Device', 'R', ref='R_BUZ', value='1k',
             footprint='Resistor_SMD:R_0805_2012Metric')

# 2N3904 KiCad pin order: 1=B (Base), 2=C (Collector), 3=E (Emitter)
Q_COLLECTOR_NET = Net('BUZ_COLLECTOR')   # local net between Q collector and buzzer-
Q_BUZ[1] += R_BUZ[2]            # base ← R_BUZ
R_BUZ[1] += BUZ_DRIVE           # base resistor from GPIO
Q_BUZ[2] += Q_COLLECTOR_NET     # collector
Q_BUZ[3] += GND                 # emitter
J_BUZ[1] += V5                  # buzzer +
J_BUZ[2] += Q_COLLECTOR_NET     # buzzer − ← collector


# =============================================================================
# Expansion header — spare GPIOs + power
# =============================================================================

J_EXP = Part('Connector_Generic', 'Conn_01x06', ref='J_EXP', value='Expansion',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical')
J_EXP[1] += V3V3
J_EXP[2] += GND
J_EXP[3] += IO17
J_EXP[4] += IO5
J_EXP[5] += IO36
J_EXP[6] += IO39


# =============================================================================
# Power flags — required for ERC to recognize power sources
# =============================================================================

# KiCad's PWR_FLAG symbol marks a net as having a power source. Without it,
# ERC complains "power input not driven by a power output". One flag per rail
# is enough. Skip +3V3 — the AMS1117 LDO output pin is already a POWER-OUT.
PWR_FLAG_12V = Part('power', 'PWR_FLAG', ref='#FLG01')
PWR_FLAG_5V  = Part('power', 'PWR_FLAG', ref='#FLG02')
PWR_FLAG_GND = Part('power', 'PWR_FLAG', ref='#FLG03')
PWR_FLAG_12V[1] += V12
PWR_FLAG_5V[1]  += V5
PWR_FLAG_GND[1] += GND


# =============================================================================
# Generate output
# =============================================================================

if __name__ == '__main__':
    print('Running ERC ...', file=sys.stderr)
    ERC()
    print('Generating netlist ...', file=sys.stderr)
    out_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'smart_gate_carrier.net',
    )
    generate_netlist(file_=out_file)
    print(f'Netlist written: {out_file}', file=sys.stderr)
