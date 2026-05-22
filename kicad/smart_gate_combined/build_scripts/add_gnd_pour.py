#!/usr/bin/env python3
"""Add a GND copper pour zone on the TOP layer (F.Cu) covering the board.

Zone parameters:
  - Net: GND
  - Layer: B.Cu
  - Clearance: 0.25 mm
  - Min thickness: 0.25 mm
  - Thermal relief: enabled (default)
  - Outline: rectangular, just inside the board edge (no copper under board edge)

After this script, open the PCB in Pcbnew and press 'B' to refill the zone.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import (
    BOARD_H, BOARD_ORIGIN_X, BOARD_ORIGIN_Y, BOARD_W,
    PCB_FILE, mm_to_iu, open_board, save_board,
)

ZONE_MARGIN = 0.5   # mm from board edge


def main() -> None:
    board = open_board()
    gnd_net = board.GetNetInfo().GetNetItem('GND')
    if gnd_net is None:
        print('GND net not found on board', file=sys.stderr)
        sys.exit(1)

    fcu = board.GetLayerID('F.Cu')

    # Remove any previously-added GND zone (on either layer, for idempotency)
    for zone in list(board.Zones()):
        if zone.GetNetname() == 'GND':
            board.Remove(zone)

    zone = pcbnew.ZONE(board)
    zone.SetLayer(fcu)
    zone.SetNet(gnd_net)
    zone.SetIsRuleArea(False)
    zone.SetLocalClearance(mm_to_iu(0.25))
    zone.SetMinThickness(mm_to_iu(0.25))
    zone.SetThermalReliefGap(mm_to_iu(0.5))
    zone.SetThermalReliefSpokeWidth(mm_to_iu(0.5))

    # Build polygon outline (rectangle just inside board edge)
    x0 = BOARD_ORIGIN_X + ZONE_MARGIN
    y0 = BOARD_ORIGIN_Y + ZONE_MARGIN
    x1 = BOARD_ORIGIN_X + BOARD_W - ZONE_MARGIN
    y1 = BOARD_ORIGIN_Y + BOARD_H - ZONE_MARGIN
    outline = pcbnew.wxPoint_Vector()
    for (x, y) in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        outline.append(pcbnew.wxPoint(mm_to_iu(x), mm_to_iu(y)))
    zone.AddPolygon(outline)

    board.Add(zone)

    # Trigger fill computation
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

    save_board(board)
    print(f'Added GND zone on B.Cu, filled, saved to {PCB_FILE}')


if __name__ == '__main__':
    main()
