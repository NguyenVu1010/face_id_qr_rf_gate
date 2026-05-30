from freecad.laser_cut.pieces import (
    Piece,
    build_front,
    build_back,
    build_bottom,
    build_arm,
)
from freecad.laser_cut.pieces import build_top, build_slope, build_left, build_right


def test_front_dimensions():
    p = build_front()
    assert p.name == "FRONT"
    xs = [pt[0] for pt in p.outline]
    ys = [pt[1] for pt in p.outline]
    assert max(xs) == 150.0
    assert max(ys) == 228.0


def test_back_has_cable_hole_and_six_mount_holes():
    p = build_back()
    assert p.name == "BACK"
    assert len(p.cuts) == 7  # 1 cable hole + 6 mount holes
    assert len(p.engraves) == 0


def test_bottom_has_vent_slots():
    p = build_bottom()
    assert p.name == "BOTTOM"
    assert len(p.cuts) == 5  # 5 vent slots


def test_arm_dimensions_and_holes():
    p = build_arm()
    assert p.name == "ARM"
    xs = [pt[0] for pt in p.outline]
    ys = [pt[1] for pt in p.outline]
    assert max(xs) == 200.0
    assert max(ys) == 15.0
    assert len(p.cuts) == 2
    assert len(p.engraves) == 5


def test_top_has_lcd_and_camera_features():
    p = build_top()
    assert p.name == "TOP"
    # 1 LCD rect + 4 LCD mount + 1 camera cable + 4 camera mount + 1 USB plug = 11 cuts
    assert len(p.cuts) == 11
    # LCD cutout must be a plain rectangle (4 vertices), not a fillet
    lcd = p.cuts[0]
    assert len(lcd.points) == 4, "LCD cutout should be a 4-vertex rectangle"
    assert len(p.engraves) == 0


def test_slope_is_blank_panel():
    p = build_slope()
    assert p.name == "SLOPE"
    xs = [pt[0] for pt in p.outline]
    ys = [pt[1] for pt in p.outline]
    assert max(xs) == 150.0
    assert abs(max(ys) - 101.82) < 0.1
    assert len(p.cuts) == 0
    assert len(p.engraves) == 0


def test_left_is_pentagon_with_mount_holes():
    p = build_left()
    assert p.name == "LEFT"
    assert len(p.outline) == 5
    # 4 corner mount holes (panel→post) + 4 PCB standoff mount holes = 8
    assert len(p.cuts) == 8


def test_right_has_arm_slot_and_hc_sr04():
    p = build_right()
    assert p.name == "RIGHT"
    assert len(p.outline) == 5
    # hc-sr04 transducers: 2; PCB corner mount holes: 4; arm slot: 1 → 7
    assert len(p.cuts) == 7
