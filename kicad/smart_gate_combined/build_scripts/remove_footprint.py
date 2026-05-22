#!/usr/bin/env python3
"""Remove a single footprint by reference from the PCB.

Usage:
  python3 build_scripts/remove_footprint.py FB_PI
  python3 build_scripts/remove_footprint.py FB_PI R_SDA C_SVO   # multiple
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, open_board, save_board


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    targets = set(sys.argv[1:])
    board = open_board()
    removed = []
    for fp in list(board.GetFootprints()):
        ref = fp.GetReference()
        if ref in targets:
            board.Remove(fp)
            removed.append(ref)

    save_board(board)
    print(f'Removed footprints: {removed}')
    not_found = targets - set(removed)
    if not_found:
        print(f'  WARN: refs not found on board: {sorted(not_found)}')


if __name__ == '__main__':
    main()
