import pytest

from freecad.laser_cut.geometry import finger_edge, pentagon_outline, fillet_rect


def test_finger_edge_outward_two_tabs():
    # 60mm edge, 2 tabs of 20mm each, mica 3mm, starts with tab
    verts = finger_edge(length=60, n_tabs=2, tab_w=20, mica_t=3, start_with_tab=True, outward=True)
    assert verts[0] == (0.0, 0.0)
    assert verts[-1] == (60.0, 0.0)
    # Tab pattern: tab(20) + gap(20) + tab(20) = 60mm.
    # Vertex count: start(1) + 2×tab(3) + 1×gap(1) = 8
    # Each tab emits: rise, plateau-end, descent (3 pts; start reuses prev).
    # Each gap emits: 1 pt (end; start reuses prev tab-descent).
    assert len(verts) == 8
    tab_y = 3.0
    assert (0.0, tab_y) in verts
    assert (20.0, tab_y) in verts
    assert (40.0, tab_y) in verts
    assert (60.0, tab_y) in verts


def test_finger_edge_inward_slots():
    verts = finger_edge(length=60, n_tabs=2, tab_w=20, mica_t=3, start_with_tab=True, outward=False)
    assert verts[0] == (0.0, 0.0)
    assert verts[-1] == (60.0, 0.0)
    assert len(verts) == 8
    # Slots go into -Y direction
    assert (0.0, -3.0) in verts
    assert (20.0, -3.0) in verts
    assert (40.0, -3.0) in verts
    assert (60.0, -3.0) in verts


def test_finger_edge_rejects_wrong_n_tabs():
    with pytest.raises(ValueError, match="n_tabs"):
        finger_edge(length=60, n_tabs=5, tab_w=20, mica_t=3, start_with_tab=True, outward=True)


def test_pentagon_outline_left_right_face():
    # LEFT/RIGHT face: 120 deep × 400 tall, top-front 30x30 corner removed
    pts = pentagon_outline(depth=120, height=400, slope=30)
    assert pts == [
        (0.0, 0.0),       # SW (front-bottom)
        (120.0, 0.0),     # SE (back-bottom)
        (120.0, 400.0),   # NE (back-top)
        (30.0, 400.0),    # slope-top
        (0.0, 370.0),     # slope-bottom (front-upper)
    ]


def test_fillet_rect_corner_count():
    width, height, radius, segments = 98, 40, 4, 8
    pts = fillet_rect(width=width, height=height, radius=radius, segments=segments)
    # Exact count: 4 corners × `segments` arc points + 4 straight-edge anchors
    assert len(pts) == 4 * segments + 4
    # Bounds: all points lie within [0, width] x [0, height]
    for x, y in pts:
        assert 0 - 1e-9 <= x <= width + 1e-9, f"x={x} out of [0,{width}]"
        assert 0 - 1e-9 <= y <= height + 1e-9, f"y={y} out of [0,{height}]"
    # Tangent anchors present (these mark each corner's start/end)
    assert (radius, 0.0) in pts
    assert (width - radius, 0.0) in pts
    # An arc point at SW corner should be at distance `radius` from center (r, r)
    sw_arc_pts = [(x, y) for x, y in pts if x < radius and y < radius]
    assert sw_arc_pts, "expected at least one SW arc point inside the corner quadrant"
    for x, y in sw_arc_pts:
        d = ((x - radius) ** 2 + (y - radius) ** 2) ** 0.5
        assert abs(d - radius) < 1e-9, f"arc point ({x},{y}) not on radius {radius}"
