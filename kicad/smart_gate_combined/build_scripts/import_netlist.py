#!/usr/bin/env python3
"""Import the SKiDL-generated netlist into the PCB file.

This replaces KiCad 6's interactive "Update PCB from Netlist" (F8) workflow
with a programmatic pass: it parses ``smart_gate_carrier.net``, loads each
component's footprint from the KiCad system library, adds it to the board,
and assigns pad nets per the netlist.

Idempotent: existing footprints with matching references are skipped (so
re-runs after manual placement do not overwrite positions).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sexpdata
import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, NETLIST_FILE, open_board, save_board
FOOTPRINT_DIR = '/usr/share/kicad/footprints'


def parse_netlist(path: str):
    """Return (components, nets).

    ``components`` is a list of dicts ``{ref, value, footprint}``.
    ``nets`` is a list of ``(name, [(ref, pin_num), ...])``.
    """
    with open(path) as f:
        tree = sexpdata.loads(f.read())

    def sym(x):
        return x.value() if isinstance(x, sexpdata.Symbol) else x

    def find_all(node, key: str):
        out = []
        for child in node[1:]:
            if isinstance(child, list) and child and sym(child[0]) == key:
                out.append(child)
        return out

    def get_val(node, key: str, default=None):
        for child in node[1:]:
            if isinstance(child, list) and child and sym(child[0]) == key:
                if len(child) > 1:
                    return sym(child[1])
        return default

    components = []
    for comp_section in find_all(tree, 'components'):
        for comp in find_all(comp_section, 'comp'):
            ref = get_val(comp, 'ref')
            value = get_val(comp, 'value')
            fp = get_val(comp, 'footprint') or ''
            if ref and not ref.startswith('#'):  # skip PWR_FLAG-style virtual
                components.append({'ref': ref, 'value': value, 'footprint': fp})

    nets = []
    for nets_section in find_all(tree, 'nets'):
        for net in find_all(nets_section, 'net'):
            name = get_val(net, 'name')
            pins = []
            for node in find_all(net, 'node'):
                ref = get_val(node, 'ref')
                pin = get_val(node, 'pin')
                if ref and pin and not ref.startswith('#'):
                    pins.append((ref, str(pin)))
            if name and pins:
                nets.append((name, pins))

    return components, nets


def load_footprint(lib_name: str, fp_name: str):
    """Load a footprint from /usr/share/kicad/footprints/<lib>.pretty/<fp>.kicad_mod."""
    pretty_dir = os.path.join(FOOTPRINT_DIR, f'{lib_name}.pretty')
    if not os.path.isdir(pretty_dir):
        raise FileNotFoundError(f'Footprint library missing: {pretty_dir}')
    fp = pcbnew.FootprintLoad(pretty_dir, fp_name)
    if fp is None:
        raise ValueError(f'Footprint {lib_name}:{fp_name} not found in {pretty_dir}')
    return fp


def ensure_net(board, name: str):
    """Return the existing PCB net for ``name``, creating it if absent."""
    nets = board.GetNetsByName()
    if name in nets:
        return nets[name]
    netinfo = pcbnew.NETINFO_ITEM(board, name)
    board.Add(netinfo)
    return netinfo


def main() -> None:
    board = open_board()
    components, nets = parse_netlist(NETLIST_FILE)

    existing_refs = {fp.GetReference() for fp in board.GetFootprints()}

    added = 0
    for comp in components:
        ref = comp['ref']
        if ref in existing_refs:
            continue
        fp_full = comp['footprint']
        if ':' not in fp_full:
            print(f'  WARN: {ref} has no footprint assignment, skipping')
            continue
        lib_name, fp_name = fp_full.split(':', 1)
        try:
            fp = load_footprint(lib_name, fp_name)
        except (FileNotFoundError, ValueError) as exc:
            print(f'  WARN: {ref}: {exc}')
            continue
        fp.SetReference(ref)
        fp.SetValue(comp['value'] or '')
        # Place at (0,0) for now; placement script will move it later
        fp.SetPosition(pcbnew.wxPoint(0, 0))
        board.Add(fp)
        added += 1
    print(f'Loaded {added} new footprints (already present: {len(existing_refs)}).')

    # Assign pad → net
    by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    pad_assignments = 0
    for net_name, pins in nets:
        netinfo = ensure_net(board, net_name)
        for ref, pin_num in pins:
            fp = by_ref.get(ref)
            if not fp:
                continue
            pad = fp.FindPadByNumber(pin_num)
            if pad is None:
                # Some footprints number pads by integer
                pad = fp.FindPadByNumber(str(pin_num))
            if pad is None:
                print(f'  WARN: pad {ref}.{pin_num} not found')
                continue
            pad.SetNet(netinfo)
            pad_assignments += 1
    print(f'Assigned {pad_assignments} pads to nets.')

    save_board(board)
    print(f'Saved {PCB_FILE}')


if __name__ == '__main__':
    main()
