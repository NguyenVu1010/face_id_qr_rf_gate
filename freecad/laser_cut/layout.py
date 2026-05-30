"""Sheet nesting layout. Each piece gets an (x, y) offset on the sheet."""

SHEET_W = 1000.0
SHEET_H = 600.0  # 600mm — accommodates 2 rows (tall pieces ~300mm + gap + small pieces ~240mm)
GAP = 8.0


def compute_layout() -> dict[str, tuple[float, float]]:
    """Returns {piece_name: (x_offset, y_offset)} on the SHEET_W x SHEET_H sheet."""
    positions: dict[str, tuple[float, float]] = {}
    # Row 1: LEFT, RIGHT, FRONT, BACK (tall pentagons + tall rects)
    x = GAP
    y = GAP
    positions["LEFT"] = (x, y); x += 240.0 + GAP
    positions["RIGHT"] = (x, y); x += 240.0 + GAP
    positions["FRONT"] = (x, y); x += 150.0 + GAP
    positions["BACK"] = (x, y); x += 150.0 + GAP
    # Row 2: TOP, SLOPE, BOTTOM, ARM (smaller)
    x2 = GAP
    y2 = y + 300.0 + GAP
    positions["TOP"] = (x2, y2); x2 += 150.0 + GAP
    positions["SLOPE"] = (x2, y2); x2 += 150.0 + GAP
    positions["BOTTOM"] = (x2, y2); x2 += 150.0 + GAP
    positions["ARM"] = (x2, y2)
    return positions
