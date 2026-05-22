#!/usr/bin/env python3
"""Add 150x80 mm board outline (Edge.Cuts layer) and four M3 mounting holes.

Idempotent: re-running deletes any pre-existing outline/mount footprints
authored by this script before re-creating them, so manual placement work in
Pcbnew is not destroyed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import (
    BOARD_H,
    BOARD_ORIGIN_X,
    BOARD_ORIGIN_Y,
    BOARD_W,
    MOUNT_HOLES,
    PCB_FILE,
    mm_to_iu,
    open_board,
    save_board,
)

MOUNT_TAG = '__SG_MOUNT__'  # written into Description so re-runs can find them


def clear_previous(board) -> None:
    """Remove any Edge.Cuts shapes and mount-hole footprints from prior runs."""
    edge_layer = board.GetLayerID('Edge.Cuts')
    for drawing in list(board.GetDrawings()):
        if drawing.GetLayer() == edge_layer:
            board.Remove(drawing)
    for fp in list(board.GetFootprints()):
        ref = fp.GetReference()
        if ref.startswith('H') and len(ref) <= 4:
            # Heuristic: H1..H99 are mounting holes we added
            board.Remove(fp)


def add_edge_cuts_rectangle(board) -> None:
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
        seg.SetStart(pcbnew.wxPoint(mm_to_iu(pts[i][0]),   mm_to_iu(pts[i][1])))
        seg.SetEnd(  pcbnew.wxPoint(mm_to_iu(pts[i+1][0]), mm_to_iu(pts[i+1][1])))
        board.Add(seg)


MOUNT_LIB = '/usr/share/kicad/footprints/MountingHole.pretty'
MOUNT_FP_NAME = 'MountingHole_3.2mm_M3'


def add_mounting_hole(board, ref: str, x_mm: float, y_mm: float) -> None:
    fp = pcbnew.FootprintLoad(MOUNT_LIB, MOUNT_FP_NAME)
    if fp is None:
        raise RuntimeError(
            f'MountingHole footprint not found at {MOUNT_LIB}/{MOUNT_FP_NAME}'
        )
    fp.SetReference(ref)
    fp.SetPosition(pcbnew.wxPoint(mm_to_iu(x_mm), mm_to_iu(y_mm)))
    board.Add(fp)


def main() -> None:
    board = open_board()
    clear_previous(board)
    add_edge_cuts_rectangle(board)
    for i, (x, y) in enumerate(MOUNT_HOLES, start=1):
        add_mounting_hole(board, f'H{i}', x, y)
    save_board(board)
    print(f'Wrote board outline ({BOARD_W}x{BOARD_H} mm) and '
          f'{len(MOUNT_HOLES)} mounting holes to {PCB_FILE}')


if __name__ == '__main__':
    main()
