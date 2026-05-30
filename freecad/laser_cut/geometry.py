"""Geometry primitives for laser-cut acrylic pieces (all coords in mm)."""

import math

MICA_T = 5.0
KERF = 0.1
JOINT_TOL = 0.15
TAB_W = 20.0


def finger_edge(
    length: float,
    n_tabs: int,
    tab_w: float,
    mica_t: float,
    start_with_tab: bool,
    outward: bool,
) -> list[tuple[float, float]]:
    """Vertices along ONE edge, going left-to-right along X.

    Tabs stick in +Y when outward=True, in -Y (slots) when outward=False.

    Raises ValueError if n_tabs doesn't match the count derived from length / tab_w.
    """
    # Validate: the segment loop alternates tab/gap starting from start_with_tab,
    # so total segments = ceil(length / tab_w), and tab count depends on start_with_tab.
    n_segments = int((length + 1e-6) // tab_w)
    if abs(n_segments * tab_w - length) > 1e-6:
        raise ValueError(f"length={length} must be an integer multiple of tab_w={tab_w}")
    if start_with_tab:
        expected_tabs = (n_segments + 1) // 2
    else:
        expected_tabs = n_segments // 2
    if n_tabs != expected_tabs:
        raise ValueError(
            f"n_tabs={n_tabs} mismatches derived count {expected_tabs} "
            f"(length={length}, tab_w={tab_w}, start_with_tab={start_with_tab})"
        )
    direction = +1 if outward else -1
    segments = []
    x = 0.0
    is_tab = start_with_tab
    while x < length - 1e-6:
        seg_end = min(x + tab_w, length)
        segments.append((x, seg_end, is_tab))
        x = seg_end
        is_tab = not is_tab

    # Build vertex list.
    # The edge starts at (0, 0).
    # For each tab segment, emit the four corners of the rectangular tooth:
    #   (x_start, h), (x_end, h), (x_end, 0)   — the (x_start, 0) is
    #   already present from either the opening point or the previous
    #   segment's close.
    # For each gap segment, emit only (x_end, 0) — its start is already
    # present from the previous vertex.
    # This keeps the list compact while retaining all geometric corners.
    verts: list[tuple[float, float]] = [(0.0, 0.0)]
    for seg_start, seg_end, tab in segments:
        if tab:
            verts.append((seg_start, direction * mica_t))
            verts.append((seg_end, direction * mica_t))
            verts.append((seg_end, 0.0))
        else:
            verts.append((seg_end, 0.0))

    # Ensure the final vertex is exactly (length, 0.0).
    if verts[-1] != (length, 0.0):
        verts.append((length, 0.0))
    return verts


def pentagon_outline(depth: float, height: float, slope: float) -> list[tuple[float, float]]:
    """LEFT/RIGHT face outline. SW=(0,0), SE=(depth,0), NE=(depth,height),
    top edge to (slope, height), then slope down to (0, height-slope)."""
    return [
        (0.0, 0.0),
        (depth, 0.0),
        (depth, height),
        (slope, height),
        (0.0, height - slope),
    ]


def fillet_rect(width: float, height: float, radius: float, segments: int = 8) -> list[tuple[float, float]]:
    """Rectangle [0,width] x [0,height] with all 4 corners rounded by radius.

    Returns an OPEN polyline (last point != first point) walking CCW from
    the bottom edge: bottom-right tangent → SE arc → right edge top-tangent
    → NE arc → top edge → NW arc → left edge bottom-tangent → SW arc, ending
    at (r, 0.0).

    `segments` controls arc smoothness; default 8 trades smoothness for
    DXF/SVG file size (4 corners × 8 segments + 4 straight-edge anchors = 36
    vertices total).
    """
    r = radius
    pts: list[tuple[float, float]] = []
    pts.append((width - r, 0.0))
    # SE corner
    for i in range(1, segments + 1):
        a = math.radians(270 + 90 * i / segments)
        pts.append((width - r + r * math.cos(a), r + r * math.sin(a)))
    pts.append((width, height - r))
    # NE corner
    for i in range(1, segments + 1):
        a = math.radians(0 + 90 * i / segments)
        pts.append((width - r + r * math.cos(a), height - r + r * math.sin(a)))
    pts.append((r, height))
    # NW corner
    for i in range(1, segments + 1):
        a = math.radians(90 + 90 * i / segments)
        pts.append((r + r * math.cos(a), height - r + r * math.sin(a)))
    pts.append((0.0, r))
    # SW corner — last arc step lands exactly at (r, 0.0) by geometry; snap
    # to avoid floating-point drift on the closing vertex.
    for i in range(1, segments + 1):
        if i == segments:
            pts.append((r, 0.0))
        else:
            a = math.radians(180 + 90 * i / segments)
            pts.append((r + r * math.cos(a), r + r * math.sin(a)))
    return pts
