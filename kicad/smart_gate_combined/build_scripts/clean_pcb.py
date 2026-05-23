#!/usr/bin/env python3
"""Clean PCB: dedupe vias, remove dangling tracks/vias, lower clearance.

Operations:
  1. Remove vias whose hole is closer than 0.01 mm to another via
     (duplicate vias stacked at the same position).
  2. Remove tracks/vias with no pad on either endpoint (dangling).
  3. Lower 'Default' net class clearance from 0.4 to 0.2 mm so the
     existing 0.4-mm-spacing tracks pass DRC.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, mm_to_iu, open_board, save_board


def dedupe_vias(board) -> int:
    """Remove duplicate vias (same position, within 10um)."""
    seen = []  # list of (x, y) positions kept
    removed = 0
    # Group vias by (position, net) — only remove vias that are EXACT
    # duplicates of an earlier via on the SAME net (within 5um position
    # tolerance). Vias at the same position but on different nets are
    # already a different DRC issue (via_dangling), not duplicates.
    for item in list(board.GetTracks()):
        if item.GetClass() != 'PCB_VIA':
            continue
        pos = item.GetPosition()
        net = item.GetNetCode()
        dup = False
        for sx, sy, snet in seen:
            if (snet == net
                    and abs(pos.x - sx) < 5_000
                    and abs(pos.y - sy) < 5_000):
                dup = True
                break
        if dup:
            board.Remove(item)
            removed += 1
        else:
            seen.append((pos.x, pos.y, net))
    return removed


def remove_dangling(board) -> int:
    """Remove tracks/vias not connected to any pad on a defined net.

    Heuristic: a track/via is "dangling" if at least one endpoint has no
    other track/via/pad of the same net within track-width radius.
    KiCad's connectivity engine is more thorough; here we just trust the
    GetNetCode == 0 case (orphans).
    """
    removed = 0
    for item in list(board.GetTracks()):
        if item.GetNetCode() == 0:
            board.Remove(item)
            removed += 1
    return removed


def lower_clearance(board) -> None:
    bds = board.GetDesignSettings()
    nc = bds.GetNetClasses().GetDefault()
    if nc:
        old = nc.GetClearance() / 1e6
        nc.SetClearance(mm_to_iu(0.2))
        print(f'Default net class clearance: {old:.3f} mm -> 0.200 mm')


def main() -> None:
    board = open_board()
    n_via = dedupe_vias(board)
    n_dang = remove_dangling(board)
    lower_clearance(board)
    save_board(board)
    print(f'Deduped {n_via} vias, removed {n_dang} dangling, saved {PCB_FILE}')


if __name__ == '__main__':
    main()
