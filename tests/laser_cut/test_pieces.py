from freecad.laser_cut.pieces import (
    Piece,
    build_front,
    build_back,
    build_bottom,
    build_arm,
)


def test_front_dimensions():
    p = build_front()
    assert p.name == "FRONT"
    xs = [pt[0] for pt in p.outline]
    ys = [pt[1] for pt in p.outline]
    assert max(xs) == 150.0
    assert max(ys) == 370.0


def test_back_has_cable_hole_and_six_mount_holes():
    p = build_back()
    assert p.name == "BACK"
    assert len(p.cuts) == 7  # 1 cable hole + 6 mount holes
    assert len(p.engraves) == 0


def test_bottom_has_vent_slots():
    p = build_bottom()
    assert p.name == "BOTTOM"
    assert len(p.cuts) == 3  # 3 vent slots


def test_arm_dimensions_and_holes():
    p = build_arm()
    assert p.name == "ARM"
    xs = [pt[0] for pt in p.outline]
    ys = [pt[1] for pt in p.outline]
    assert max(xs) == 150.0
    assert max(ys) == 15.0
    assert len(p.cuts) == 2
