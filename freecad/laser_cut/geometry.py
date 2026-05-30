"""Geometry primitives for laser-cut acrylic pieces (all coords in mm)."""

from dataclasses import dataclass

MICA_T = 3.0
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
    """
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
