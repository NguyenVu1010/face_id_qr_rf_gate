"""Shared constants and helpers for PCB layout scripts.

Imports are KiCad 6.0.2 ``pcbnew`` module — the same Python API used by
Pcbnew's built-in scripting console. All coordinates are in millimetres at
this layer; conversion to internal nanometre units happens at the
``pcbnew``-call boundary via ``mm_to_iu``.
"""

import os

import pcbnew  # type: ignore[import]

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB_FILE = os.path.join(PROJECT_DIR, 'smart_gate_carrier.kicad_pcb')

# Board outline (mm)
BOARD_W = 150.0
BOARD_H = 80.0
BOARD_ORIGIN_X = 100.0   # offset board into KiCad's page coordinate system
BOARD_ORIGIN_Y = 100.0

# Mounting holes (M3): 3.2 mm drill, 6 mm pad/keepout
MOUNT_OFFSET = 4.0       # mm from each board edge
MOUNT_HOLES = [
    (BOARD_ORIGIN_X + MOUNT_OFFSET,             BOARD_ORIGIN_Y + MOUNT_OFFSET),
    (BOARD_ORIGIN_X + BOARD_W - MOUNT_OFFSET,   BOARD_ORIGIN_Y + MOUNT_OFFSET),
    (BOARD_ORIGIN_X + MOUNT_OFFSET,             BOARD_ORIGIN_Y + BOARD_H - MOUNT_OFFSET),
    (BOARD_ORIGIN_X + BOARD_W - MOUNT_OFFSET,   BOARD_ORIGIN_Y + BOARD_H - MOUNT_OFFSET),
]

# Component placement: {ref: (x_mm, y_mm, rotation_deg)} in absolute pcbnew
# coordinates. Layout zones:
#   - Left column (X 105–135): power input + LDO + buck module + expansion hdr
#   - Centre column (X 155–180): ESP32 DevKit socket (vertical 1x15 sockets)
#   - Right column (X 205–230): peripheral headers + pull-ups + buzzer drive
PLACEMENT = {
    # Power input zone (top-left → bottom-left)
    'J_PWR':       (BOARD_ORIGIN_X + 10, BOARD_ORIGIN_Y + 15,  0),
    'D_REV':       (BOARD_ORIGIN_X + 25, BOARD_ORIGIN_Y + 15,  0),
    'C_BULK':      (BOARD_ORIGIN_X + 10, BOARD_ORIGIN_Y + 30,  0),
    'J_BUCK':      (BOARD_ORIGIN_X + 25, BOARD_ORIGIN_Y + 35,  0),
    'U_LDO':       (BOARD_ORIGIN_X + 10, BOARD_ORIGIN_Y + 55,  0),
    'C_LDOIN':     (BOARD_ORIGIN_X + 18, BOARD_ORIGIN_Y + 55,  0),
    'C_LDOOUT':    (BOARD_ORIGIN_X + 24, BOARD_ORIGIN_Y + 55,  0),

    # ESP32 DevKit socket (centre; rails 23 mm apart for DOIT V1 width)
    'J_ESP_L':     (BOARD_ORIGIN_X + 55, BOARD_ORIGIN_Y + 40, 90),
    'J_ESP_R':     (BOARD_ORIGIN_X + 78, BOARD_ORIGIN_Y + 40, 90),
    'C_ESP_3V3_1': (BOARD_ORIGIN_X + 45, BOARD_ORIGIN_Y + 25,  0),
    'C_ESP_3V3_2': (BOARD_ORIGIN_X + 45, BOARD_ORIGIN_Y + 30,  0),

    # Peripheral headers (right column, top → bottom)
    'J_RFID':      (BOARD_ORIGIN_X + 105, BOARD_ORIGIN_Y + 15, 90),  # 1x8
    'J_LCD':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 15, 90),  # 1x4
    'R_SDA':       (BOARD_ORIGIN_X + 122, BOARD_ORIGIN_Y + 28,  0),
    'R_SCL':       (BOARD_ORIGIN_X + 122, BOARD_ORIGIN_Y + 32,  0),
    'J_USR':       (BOARD_ORIGIN_X + 105, BOARD_ORIGIN_Y + 45, 90),  # 1x4
    'R_USR1':      (BOARD_ORIGIN_X + 112, BOARD_ORIGIN_Y + 55,  0),
    'R_USR2':      (BOARD_ORIGIN_X + 112, BOARD_ORIGIN_Y + 60,  0),
    'J_SVO':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 40, 90),  # 1x3
    'C_SVO':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 55,  0),

    # Buzzer block (bottom-right)
    'Q_BUZ':       (BOARD_ORIGIN_X + 105, BOARD_ORIGIN_Y + 67,  0),
    'R_BUZ':       (BOARD_ORIGIN_X + 113, BOARD_ORIGIN_Y + 67,  0),
    'J_BUZ':       (BOARD_ORIGIN_X + 130, BOARD_ORIGIN_Y + 67, 90),  # 1x2

    # Expansion header (bottom-left)
    'J_EXP':       (BOARD_ORIGIN_X + 35,  BOARD_ORIGIN_Y + 70, 90),  # 1x6
}


def mm_to_iu(value_mm: float) -> int:
    """Convert millimetres to pcbnew internal units (nanometres)."""
    return int(value_mm * 1_000_000)


def iu_to_mm(value_iu: int) -> float:
    """Convert pcbnew internal units (nanometres) to millimetres."""
    return value_iu / 1_000_000


def open_board(path: str = PCB_FILE):
    """Load a KiCad PCB from disk."""
    return pcbnew.LoadBoard(path)


def save_board(board, path: str = PCB_FILE) -> None:
    """Persist a KiCad PCB to disk."""
    board.Save(path)
