#!/usr/bin/env python3
"""Parse a FreeRouting Specctra SES output and apply routes to the KiCad PCB.

KiCad 6's pcbnew.ImportSpecctraSES() requires GUI context and returns False
when called from a headless Python script. So we parse the SES ourselves and
add PCB_TRACK + VIA primitives to the board.

SES resolution from the file header is taken literally: '(resolution um 10)'
means 10 µm per unit — but in practice FreeRouting writes (resolution um 10)
followed by integer X/Y values where each unit is 0.1 µm = 100 nm
(matching KiCad's internal nm scale at a factor of 100).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sexpdata
import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, open_board, save_board

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SES_FILE = os.path.join(PROJECT_DIR, 'smart_gate_combined.ses')

# SES unit -> nm. FreeRouting emits coords in 100nm steps (resolution um 10).
SES_TO_NM = 100

# Override SES-encoded track width (FreeRouting writes 0.25mm by default).
# 1.0 mm = 1_000_000 nm — high current capacity + at 2.54mm pin pitch / 1.8mm
# pad → only 0.74mm gap between adjacent pad edges, which physically cannot
# fit a 1.0mm track + clearance → routes are forced to go around component
# pin clusters instead of weaving between pins.
FORCE_TRACK_WIDTH_NM = 500_000   # 0.5mm — balance of current capacity vs density


def sym_str(x):
    return x.value() if isinstance(x, sexpdata.Symbol) else x


def find_children(node, key):
    out = []
    for child in node[1:]:
        if isinstance(child, list) and child and sym_str(child[0]) == key:
            out.append(child)
    return out


def parse_ses(path):
    """Return list of (net_name, [(layer, width_nm, [(x_nm, y_nm), ...])])."""
    # SES uses '(net +12V ...)' where the net name is unquoted; sexpdata
    # parses it as a Symbol. Quote bare net names so sexpdata accepts them.
    with open(path) as f:
        text = f.read()
    tree = sexpdata.loads(text)

    nets_section = None
    routes = find_children(tree, 'routes')
    if not routes:
        raise RuntimeError("SES file has no 'routes' section")
    nets_section = find_children(routes[0], 'network_out')
    if not nets_section:
        raise RuntimeError("SES file has no 'network_out' section")

    out = []
    for net in find_children(nets_section[0], 'net'):
        net_name = sym_str(net[1])
        wires = []
        vias = []
        for child in net[2:]:
            if not isinstance(child, list):
                continue
            head = sym_str(child[0])
            if head == 'wire':
                path_node = find_children(child, 'path')
                if not path_node:
                    continue
                path_args = path_node[0][1:]  # skip 'path' keyword
                layer = sym_str(path_args[0])
                width = int(path_args[1]) * SES_TO_NM
                # Remaining are alternating X Y numbers
                coords = path_args[2:]
                pts = []
                for i in range(0, len(coords), 2):
                    x = int(coords[i]) * SES_TO_NM
                    y = -int(coords[i + 1]) * SES_TO_NM   # SES Y is flipped vs KiCad
                    pts.append((x, y))
                wires.append((layer, width, pts))
            elif head == 'via':
                # (via padstack_name x y)
                pad_name = sym_str(child[1])
                x = int(child[2]) * SES_TO_NM
                y = -int(child[3]) * SES_TO_NM
                vias.append((pad_name, x, y))
        out.append((net_name, wires, vias))
    return out


def main() -> None:
    board = open_board()
    net_info = board.GetNetInfo()
    layer_id = {
        'F.Cu': board.GetLayerID('F.Cu'),
        'B.Cu': board.GetLayerID('B.Cu'),
    }

    parsed = parse_ses(SES_FILE)
    seg_added = 0
    via_added = 0
    for net_name, wires, vias in parsed:
        net_item = net_info.GetNetItem(net_name)
        if net_item is None:
            print(f'  WARN: net {net_name!r} unknown to board, skipping')
            continue
        for layer, width, pts in wires:
            lid = layer_id.get(layer)
            if lid is None:
                print(f'  WARN: unknown layer {layer!r}')
                continue
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                trk = pcbnew.PCB_TRACK(board)
                trk.SetLayer(lid)
                trk.SetWidth(FORCE_TRACK_WIDTH_NM if FORCE_TRACK_WIDTH_NM else width)
                trk.SetStart(pcbnew.wxPoint(x1, y1))
                trk.SetEnd(pcbnew.wxPoint(x2, y2))
                trk.SetNet(net_item)
                board.Add(trk)
                seg_added += 1
        for _padstack, x, y in vias:
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.wxPoint(x, y))
            via.SetWidth(int(0.8 * 1_000_000))   # 0.8 mm via OD
            via.SetDrill(int(0.4 * 1_000_000))   # 0.4 mm drill
            via.SetLayerPair(layer_id['F.Cu'], layer_id['B.Cu'])
            via.SetNet(net_item)
            board.Add(via)
            via_added += 1

    save_board(board)
    print(f'Added {seg_added} track segments + {via_added} vias to {PCB_FILE}')


if __name__ == '__main__':
    main()
