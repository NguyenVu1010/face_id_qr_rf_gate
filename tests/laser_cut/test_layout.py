from freecad.laser_cut.layout import compute_layout, SHEET_W, SHEET_H


def test_compute_layout_all_pieces_fit():
    positions = compute_layout()
    expected_names = {"FRONT", "BACK", "LEFT", "RIGHT", "TOP", "SLOPE", "BOTTOM", "ARM"}
    assert set(positions.keys()) == expected_names

    from freecad.laser_cut.pieces import (
        build_front, build_back, build_left, build_right,
        build_top, build_slope, build_bottom, build_arm,
    )
    builders = {
        "FRONT": build_front, "BACK": build_back, "LEFT": build_left, "RIGHT": build_right,
        "TOP": build_top, "SLOPE": build_slope, "BOTTOM": build_bottom, "ARM": build_arm,
    }
    for name, builder in builders.items():
        ox, oy = positions[name]
        piece = builder()
        xs = [pt[0] + ox for pt in piece.outline]
        ys = [pt[1] + oy for pt in piece.outline]
        assert min(xs) >= 0
        assert max(xs) <= SHEET_W
        assert min(ys) >= 0
        assert max(ys) <= SHEET_H


def test_compute_layout_pieces_dont_overlap():
    positions = compute_layout()
    from freecad.laser_cut.pieces import (
        build_front, build_back, build_left, build_right,
        build_top, build_slope, build_bottom, build_arm,
    )
    builders = {
        "FRONT": build_front, "BACK": build_back, "LEFT": build_left, "RIGHT": build_right,
        "TOP": build_top, "SLOPE": build_slope, "BOTTOM": build_bottom, "ARM": build_arm,
    }
    boxes = {}
    for name, builder in builders.items():
        ox, oy = positions[name]
        piece = builder()
        xs = [pt[0] + ox for pt in piece.outline]
        ys = [pt[1] + oy for pt in piece.outline]
        boxes[name] = (min(xs), min(ys), max(xs), max(ys))
    names = list(boxes.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = boxes[names[i]]; b = boxes[names[j]]
            overlap = not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
            assert not overlap, f"{names[i]} overlaps {names[j]}"
