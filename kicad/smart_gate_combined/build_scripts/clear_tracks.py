#!/usr/bin/env python3
"""Delete all routed tracks (and optionally GND zones) from the PCB.

Keeps:
  - Footprints
  - Board outline (Edge.Cuts)
  - Mounting holes
  - Netlist / pad-to-net assignments

Removes:
  - All PCB_TRACK segments (both F.Cu and B.Cu)
  - All PCB_VIA items
  - GND copper pour zones (toggle with --keep-zones)

Usage:
  python3 build_scripts/clear_tracks.py
  python3 build_scripts/clear_tracks.py --keep-zones    # keep the GND pour
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, open_board, save_board


def main() -> None:
    keep_zones = '--keep-zones' in sys.argv

    board = open_board()

    tracks_removed = 0
    vias_removed = 0
    for item in list(board.GetTracks()):
        cls = item.GetClass()
        if cls == 'PCB_TRACK':
            board.Remove(item)
            tracks_removed += 1
        elif cls == 'VIA':
            board.Remove(item)
            vias_removed += 1

    zones_removed = 0
    if not keep_zones:
        for zone in list(board.Zones()):
            board.Remove(zone)
            zones_removed += 1

    save_board(board)
    print(f'Removed {tracks_removed} tracks, {vias_removed} vias, {zones_removed} zones')
    print(f'Saved {PCB_FILE}')


if __name__ == '__main__':
    main()
