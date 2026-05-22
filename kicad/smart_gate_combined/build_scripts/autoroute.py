#!/usr/bin/env python3
"""Auto-route the PCB via FreeRouting.

Pipeline:
  1. ExportSpecctraDSN(board, dsn_path)
  2. java -jar freerouting.jar -de dsn -do ses
  3. ImportSpecctraSES(board, ses_path)
  4. Save board

Requires:
  - FreeRouting jar at FREEROUTING_BIN
  - Java 11 or later
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, open_board, save_board

FREEROUTING_BIN = os.path.expanduser(
    '~/tools/freerouting/1.7.0/freerouting-1.7.0-linux-x64/bin/freerouting'
)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSN_FILE = os.path.join(PROJECT_DIR, 'smart_gate_combined.dsn')
SES_FILE = os.path.join(PROJECT_DIR, 'smart_gate_combined.ses')


def main() -> None:
    board = open_board()

    print('Exporting Specctra DSN ...', flush=True)
    if not pcbnew.ExportSpecctraDSN(board, DSN_FILE):
        print('ExportSpecctraDSN failed', file=sys.stderr)
        sys.exit(1)
    print(f'  wrote {DSN_FILE} ({os.path.getsize(DSN_FILE)} bytes)')

    # Strong bias: change F.Cu layer type from 'signal' to 'power' so
    # FreeRouting refuses to use it for routing. Forces all signal nets to
    # B.Cu (the "wires on bottom, components on top" layout).
    # Also widen all tracks to 1.0 mm (1000 um) so FreeRouting plans routes
    # that actually fit a 1.0 mm track + clearance — at 2.54 mm pin pitch
    # this physically prevents tracks from weaving between component pins.
    print('Forcing F.Cu = power-only + track width 1.0 mm ...', flush=True)
    with open(DSN_FILE) as f:
        dsn = f.read()
    dsn = dsn.replace('(layer F.Cu\n      (type signal)',
                      '(layer F.Cu\n      (type power)', 1)
    # Override default trace width 250 µm -> 1000 µm. The string '(width 250)'
    # appears in (rule ...) blocks (board-level and per-net-class).
    dsn = dsn.replace('(width 250)', '(width 1000)')
    with open(DSN_FILE, 'w') as f:
        f.write(dsn)

    print('Running FreeRouting (this may take 1-3 minutes) ...', flush=True)
    cmd = [
        FREEROUTING_BIN,
        '-de', DSN_FILE,
        '-do', SES_FILE,
        '-mp', '20',           # max 20 passes for prototype-quality routing
        '-mt', '4',            # use 4 threads
    ]
    rc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print('FreeRouting exit code:', rc.returncode)
    if rc.stdout:
        for line in rc.stdout.splitlines()[-15:]:
            print('  stdout:', line)
    if rc.stderr:
        for line in rc.stderr.splitlines()[-5:]:
            print('  stderr:', line)
    if not os.path.exists(SES_FILE):
        print(f'SES file not produced at {SES_FILE}', file=sys.stderr)
        sys.exit(2)
    print(f'  wrote {SES_FILE} ({os.path.getsize(SES_FILE)} bytes)')

    # NOTE: do NOT call pcbnew.ImportSpecctraSES() here — it shifts the entire
    # board by an internal auxiliary origin offset, corrupting placement vs the
    # other scripts' coordinates. We let the custom build_scripts/import_ses.py
    # parse the SES file and add tracks afterwards.
    print(f'SES ready for custom import (run build_scripts/import_ses.py next).')

    # Quick stats
    tracks = list(board.GetTracks())
    vias = [t for t in tracks if t.GetClass() == 'VIA']
    segments = [t for t in tracks if t.GetClass() == 'PCB_TRACK']
    print(f'Stats: {len(segments)} track segments + {len(vias)} vias')


if __name__ == '__main__':
    main()
