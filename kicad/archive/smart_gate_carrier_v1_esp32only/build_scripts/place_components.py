#!/usr/bin/env python3
"""Move each component footprint to its planned coordinate.

Reads ``PLACEMENT`` from ``pcb_common``: a ``{ref: (x_mm, y_mm, rot_deg)}``
map. Footprints whose reference is not in the map are left at their current
position (e.g. mounting holes H1..H4).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import (
    PCB_FILE,
    PLACEMENT,
    mm_to_iu,
    open_board,
    save_board,
)


def main() -> None:
    board = open_board()
    placed = 0
    untouched = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in PLACEMENT:
            untouched.append(ref)
            continue
        x_mm, y_mm, rot_deg = PLACEMENT[ref]
        fp.SetPosition(pcbnew.wxPoint(mm_to_iu(x_mm), mm_to_iu(y_mm)))
        fp.SetOrientationDegrees(rot_deg)
        placed += 1
    save_board(board)
    print(f'Placed {placed} footprints.')
    print(f'Untouched (kept at current position): {sorted(untouched)}')
    print(f'Saved {PCB_FILE}')


if __name__ == '__main__':
    main()
