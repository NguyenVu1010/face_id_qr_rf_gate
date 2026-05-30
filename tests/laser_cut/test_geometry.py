from freecad.laser_cut.geometry import finger_edge


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
    assert (0.0, -3.0) in verts
    assert (20.0, -3.0) in verts
