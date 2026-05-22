#!/usr/bin/env python3
"""Generate gerber files + Excellon drill file for fab.

Output directory: ../gerber/

Layers plotted:
  F.Cu, B.Cu, F.Mask, B.Mask, F.SilkS, B.SilkS, F.Paste, B.Paste, Edge.Cuts
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, open_board

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GERBER_DIR = os.path.join(PROJECT_DIR, 'gerber')

LAYERS = [
    (pcbnew.F_Cu,    'F_Cu'),
    (pcbnew.B_Cu,    'B_Cu'),
    (pcbnew.F_Paste, 'F_Paste'),
    (pcbnew.B_Paste, 'B_Paste'),
    (pcbnew.F_SilkS, 'F_SilkS'),
    (pcbnew.B_SilkS, 'B_SilkS'),
    (pcbnew.F_Mask,  'F_Mask'),
    (pcbnew.B_Mask,  'B_Mask'),
    (pcbnew.Edge_Cuts, 'Edge_Cuts'),
]


def main() -> None:
    os.makedirs(GERBER_DIR, exist_ok=True)
    board = open_board()

    pc = pcbnew.PLOT_CONTROLLER(board)
    po = pc.GetPlotOptions()

    po.SetOutputDirectory(GERBER_DIR)
    po.SetPlotFrameRef(False)
    po.SetPlotValue(True)
    po.SetPlotReference(True)
    po.SetUseGerberProtelExtensions(True)
    po.SetUseGerberX2format(True)
    po.SetCreateGerberJobFile(True)
    po.SetSubtractMaskFromSilk(False)
    po.SetMirror(False)
    po.SetPlotMode(pcbnew.FILLED)
    po.SetDrillMarksType(pcbnew.PCB_PLOT_PARAMS.NO_DRILL_SHAPE)
    po.SetAutoScale(False)
    po.SetScale(1)

    for layer_id, suffix in LAYERS:
        pc.SetLayer(layer_id)
        pc.OpenPlotfile(suffix, pcbnew.PLOT_FORMAT_GERBER, suffix)
        if not pc.PlotLayer():
            print(f'  failed to plot layer {suffix}', file=sys.stderr)
            continue
        pc.ClosePlot()
        print(f'  plotted {suffix}')

    # Drill file
    drill = pcbnew.EXCELLON_WRITER(board)
    drill.SetMapFileFormat(pcbnew.PLOT_FORMAT_GERBER)
    drill.SetMergeOption(True)   # merge PTH and NPTH into one file
    drill.SetFormat(True)        # metric units (1 = metric)
    drill.SetOptions(False, False, pcbnew.wxPoint(0, 0), True)
    drill.CreateDrillandMapFilesSet(GERBER_DIR, True, True)
    print(f'  drill files written')

    print(f'\nAll output in {GERBER_DIR}/')


if __name__ == '__main__':
    main()
