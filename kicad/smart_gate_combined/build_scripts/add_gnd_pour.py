#!/usr/bin/env python3
"""Add GND copper pour zones on BOTH layers (F.Cu and B.Cu) covering the board.

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

from pcb_common import PCB_FILE, mm_to_iu, open_board, save_board

ZONE_MARGIN = 0.5   # mm from board edge


def get_board_outline_bbox(board):
    """Return (xmin, ymin, xmax, ymax) in mm from Edge.Cuts geometry."""
    edge_layer = board.GetLayerID('Edge.Cuts')
    xs, ys = [], []
    for d in board.GetDrawings():
        if d.GetLayer() != edge_layer:
            continue
        xs.extend([d.GetStart().x / 1e6, d.GetEnd().x / 1e6])
        ys.extend([d.GetStart().y / 1e6, d.GetEnd().y / 1e6])
    if not xs:
        raise RuntimeError('No Edge.Cuts geometry on board')
    return min(xs), min(ys), max(xs), max(ys)


def main() -> None:
    board = open_board()
    gnd_net = board.GetNetInfo().GetNetItem('GND')
    if gnd_net is None:
        print('GND net not found on board', file=sys.stderr)
        sys.exit(1)

    # Remove any previously-added GND zone (on either layer, for idempotency)
    for zone in list(board.Zones()):
        if zone.GetNetname() == 'GND':
            board.Remove(zone)

    # Detect actual board outline at runtime (so the pour always fits the
    # current Edge.Cuts geometry, regardless of pcb_common.BOARD_* values
    # which can drift from PCB content after manual edits / restores).
    xmin, ymin, xmax, ymax = get_board_outline_bbox(board)
    x0 = xmin + ZONE_MARGIN
    y0 = ymin + ZONE_MARGIN
    x1 = xmax - ZONE_MARGIN
    y1 = ymax - ZONE_MARGIN
    print(f'Board outline: ({xmin:.1f},{ymin:.1f}) -> ({xmax:.1f},{ymax:.1f})')
    print(f'Zone outline:  ({x0:.1f},{y0:.1f}) -> ({x1:.1f},{y1:.1f})')

    for layer_name in ('F.Cu', 'B.Cu'):
        layer_id = board.GetLayerID(layer_name)
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer_id)
        zone.SetNet(gnd_net)
        zone.SetIsRuleArea(False)
        zone.SetLocalClearance(mm_to_iu(0.25))
        zone.SetMinThickness(mm_to_iu(0.25))
        zone.SetThermalReliefGap(mm_to_iu(0.5))
        zone.SetThermalReliefSpokeWidth(mm_to_iu(0.5))

        outline = pcbnew.wxPoint_Vector()
        for (x, y) in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            outline.append(pcbnew.wxPoint(mm_to_iu(x), mm_to_iu(y)))
        zone.AddPolygon(outline)
        board.Add(zone)
        print(f'  + GND zone on {layer_name}')

    # Trigger fill computation
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())

    save_board(board)
    print(f'Saved GND pour zones (F.Cu + B.Cu) to {PCB_FILE}')


if __name__ == '__main__':
    main()
