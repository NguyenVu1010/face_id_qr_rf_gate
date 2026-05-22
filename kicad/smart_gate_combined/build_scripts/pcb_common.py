"""Shared constants and helpers for combined motherboard PCB scripts."""

import os
import pcbnew  # type: ignore[import]

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB_FILE = os.path.join(PROJECT_DIR, 'smart_gate_combined.kicad_pcb')
NETLIST_FILE = os.path.join(PROJECT_DIR, 'smart_gate_combined.net')

# Board outline (mm) — larger than v1 to fit Pi GPIO socket + ESP32 + peripherals
BOARD_W = 250.0
BOARD_H = 150.0
BOARD_ORIGIN_X = 100.0
BOARD_ORIGIN_Y = 100.0

# Mounting holes (M3, 3.2 mm drill)
MOUNT_OFFSET = 5.0
MOUNT_HOLES = [
    (BOARD_ORIGIN_X + MOUNT_OFFSET,             BOARD_ORIGIN_Y + MOUNT_OFFSET),
    (BOARD_ORIGIN_X + BOARD_W - MOUNT_OFFSET,   BOARD_ORIGIN_Y + MOUNT_OFFSET),
    (BOARD_ORIGIN_X + MOUNT_OFFSET,             BOARD_ORIGIN_Y + BOARD_H - MOUNT_OFFSET),
    (BOARD_ORIGIN_X + BOARD_W - MOUNT_OFFSET,   BOARD_ORIGIN_Y + BOARD_H - MOUNT_OFFSET),
]

# Layout zones:
#   Top strip   (Y 10–28):    J_PI socket (2×20) — Pi body extends UP off-PCB
#   Power strip (Y 35–60):    DC jack → buck → 5V filter → TVS  (across full width)
#   LDO strip   (Y 65–80):    U_LDO + caps
#   ESP32 zone  (Y 85–110):   DevKit socket centred
#   Right zone  (X 140–235, Y 30–110): peripheral headers
#   Buzzer zone (Y 115–140, X 140–200): NPN + buzzer header
#   Expansion   (Y 125–140, X 15–50):  J_EXP header
PLACEMENT = {
    # Pi GPIO socket — horizontal 2×20, near top edge, Pi extends off the top
    'J_PI':        (BOARD_ORIGIN_X + 125, BOARD_ORIGIN_Y + 18,  0),

    # Power input chain (left)
    'J_PWR':       (BOARD_ORIGIN_X + 15,  BOARD_ORIGIN_Y + 40,  0),
    'D_REV':       (BOARD_ORIGIN_X + 30,  BOARD_ORIGIN_Y + 40,  0),
    'C_BULK':      (BOARD_ORIGIN_X + 15,  BOARD_ORIGIN_Y + 55,  0),
    'J_BUCK':      (BOARD_ORIGIN_X + 32,  BOARD_ORIGIN_Y + 55,  0),

    # 5 V filter chain (top edge below Pi)
    'C_5V_BULK':   (BOARD_ORIGIN_X + 55,  BOARD_ORIGIN_Y + 45,  0),
    'C_5V_BYP':    (BOARD_ORIGIN_X + 60,  BOARD_ORIGIN_Y + 50,  0),
    'FB_PI':       (BOARD_ORIGIN_X + 75,  BOARD_ORIGIN_Y + 45,  0),
    'C_PI_BULK':   (BOARD_ORIGIN_X + 90,  BOARD_ORIGIN_Y + 45,  0),
    'C_PI_BYP':    (BOARD_ORIGIN_X + 95,  BOARD_ORIGIN_Y + 50,  0),
    'D_TVS':       (BOARD_ORIGIN_X + 110, BOARD_ORIGIN_Y + 45,  0),

    # 3.3 V LDO + decoupling
    'U_LDO':       (BOARD_ORIGIN_X + 15,  BOARD_ORIGIN_Y + 75,  0),
    'C_LDOIN':     (BOARD_ORIGIN_X + 25,  BOARD_ORIGIN_Y + 75,  0),
    'C_LDOOUT':    (BOARD_ORIGIN_X + 32,  BOARD_ORIGIN_Y + 75,  0),
    'C_ESP_3V3_1': (BOARD_ORIGIN_X + 45,  BOARD_ORIGIN_Y + 75,  0),
    'C_ESP_3V3_2': (BOARD_ORIGIN_X + 52,  BOARD_ORIGIN_Y + 75,  0),

    # ESP32 DevKit socket (centre): single 2x15 footprint with rails 25.4mm apart
    'J_ESP':       (BOARD_ORIGIN_X + 92,  BOARD_ORIGIN_Y + 100, 90),

    # Peripheral headers (right column)
    'J_RFID':      (BOARD_ORIGIN_X + 150, BOARD_ORIGIN_Y + 50,  0),
    'J_LCD':       (BOARD_ORIGIN_X + 180, BOARD_ORIGIN_Y + 50,  0),
    'R_SDA':       (BOARD_ORIGIN_X + 178, BOARD_ORIGIN_Y + 65,  0),
    'R_SCL':       (BOARD_ORIGIN_X + 183, BOARD_ORIGIN_Y + 65,  0),
    'J_USR':       (BOARD_ORIGIN_X + 205, BOARD_ORIGIN_Y + 50,  0),
    'R_USR1':      (BOARD_ORIGIN_X + 205, BOARD_ORIGIN_Y + 65,  0),
    'R_USR2':      (BOARD_ORIGIN_X + 210, BOARD_ORIGIN_Y + 65,  0),
    'J_SVO':       (BOARD_ORIGIN_X + 230, BOARD_ORIGIN_Y + 50,  0),
    'C_SVO':       (BOARD_ORIGIN_X + 230, BOARD_ORIGIN_Y + 65,  0),

    # Buzzer block
    'Q_BUZ':       (BOARD_ORIGIN_X + 160, BOARD_ORIGIN_Y + 100, 0),
    'R_BUZ':       (BOARD_ORIGIN_X + 168, BOARD_ORIGIN_Y + 100, 0),
    'J_BUZ':       (BOARD_ORIGIN_X + 180, BOARD_ORIGIN_Y + 100, 0),

    # Expansion
    'J_EXP':       (BOARD_ORIGIN_X + 20,  BOARD_ORIGIN_Y + 130, 0),
}


def mm_to_iu(value_mm: float) -> int:
    return int(value_mm * 1_000_000)


def iu_to_mm(value_iu: int) -> float:
    return value_iu / 1_000_000


def open_board(path: str = PCB_FILE):
    return pcbnew.LoadBoard(path)


def save_board(board, path: str = PCB_FILE) -> None:
    board.Save(path)
