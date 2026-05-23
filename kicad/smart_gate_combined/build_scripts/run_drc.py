#!/usr/bin/env python3
"""Run DRC on the PCB and write a human-readable report.

Output: drc_report.txt in the project directory.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew  # type: ignore[import]

from pcb_common import PCB_FILE, open_board

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_FILE = os.path.join(PROJECT_DIR, 'drc_report.txt')


def main() -> None:
    board = open_board()
    ok = pcbnew.WriteDRCReport(board, REPORT_FILE,
                                pcbnew.EDA_UNITS_MILLIMETRES,
                                True)
    if not ok:
        print('WriteDRCReport returned False', file=sys.stderr)
        sys.exit(1)
    print(f'DRC report: {REPORT_FILE}')

    with open(REPORT_FILE) as f:
        content = f.read()
    print('---')
    print(content)


if __name__ == '__main__':
    main()
