#!/usr/bin/env python3
"""Set up design rules + net classes on the PCB.

  Default class: 0.25mm tracks, 0.2mm clearance, 0.6/0.3mm via
  Power   class: 0.5mm  tracks, 0.25mm clearance, 0.8/0.4mm via

Power nets: +12V, +5V, +3V3, GND, PI_5V_FILTERED
All other nets stay in Default.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, mm_to_iu, open_board, save_board

POWER_NETS = {'+12V', '+5V', '+3V3', 'GND', 'PI_5V_FILTERED'}


def main() -> None:
    board = open_board()
    bds = board.GetDesignSettings()

    # Get current net classes container
    nc_map = bds.GetNetClasses()
    # 'Default' net class is always present
    default = nc_map.GetDefault() if hasattr(nc_map, 'GetDefault') else None
    if default is None:
        default = bds.GetNetClasses().NetClasses().get('Default')
    if default:
        default.SetTrackWidth(mm_to_iu(0.25))
        default.SetClearance(mm_to_iu(0.20))
        default.SetViaDiameter(mm_to_iu(0.60))
        default.SetViaDrill(mm_to_iu(0.30))

    # Create Power class if it doesn't exist
    power = pcbnew.NETCLASS('Power')
    power.SetTrackWidth(mm_to_iu(0.50))
    power.SetClearance(mm_to_iu(0.25))
    power.SetViaDiameter(mm_to_iu(0.80))
    power.SetViaDrill(mm_to_iu(0.40))
    nc_map.NetClasses()['Power'] = power

    # Assign power nets to Power class
    netinfo = board.GetNetInfo()
    for net_name in POWER_NETS:
        net = netinfo.GetNetItem(net_name)
        if net is None:
            print(f'  WARN: net {net_name!r} not on board, skipping')
            continue
        net.SetNetClass(power)
        print(f'  net {net_name!r} -> Power class')

    bds.SetTrackWidth(mm_to_iu(0.25))
    bds.SetMinClearance(mm_to_iu(0.15))

    save_board(board)
    print(f'Saved {PCB_FILE}')


if __name__ == '__main__':
    main()
