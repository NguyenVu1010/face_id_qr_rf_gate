from freecad.laser_cut.cutouts import (
    Shape,
    circle,
    rect,
    lcd_window,
    servo_cutout,
    hc_sr04_holes,
    rfid_engrave_marker,
)


def test_circle_returns_cut_shape():
    s = circle(cx=10, cy=10, radius=5)
    assert s.kind == "cut"
    # 16-segment approximation
    assert len(s.points) == 16
    for x, y in s.points:
        assert abs(((x - 10) ** 2 + (y - 10) ** 2) ** 0.5 - 5) < 1e-6


def test_lcd_window_dimensions():
    shape = lcd_window(cx=75, cy=35, w=98, h=40, r=4)
    assert shape.kind == "cut"
    xs = [p[0] for p in shape.points]
    ys = [p[1] for p in shape.points]
    assert abs(min(xs) - (75 - 49)) < 0.01
    assert abs(max(xs) - (75 + 49)) < 0.01
    assert abs(min(ys) - (35 - 20)) < 0.01
    assert abs(max(ys) - (35 + 20)) < 0.01


def test_hc_sr04_holes_returns_two_circles():
    shapes = hc_sr04_holes(cx=60, cy=300, spacing=27, radius=8)
    assert len(shapes) == 2
    assert all(s.kind == "cut" for s in shapes)
    centers = [(sum(p[0] for p in s.points) / len(s.points),
                sum(p[1] for p in s.points) / len(s.points))
               for s in shapes]
    centers.sort()
    assert abs(centers[0][0] - (60 - 13.5)) < 0.5
    assert abs(centers[1][0] - (60 + 13.5)) < 0.5


def test_rfid_engrave_marker_kind():
    shape = rfid_engrave_marker(cx=75, cy=21.2, w=50, h=30)
    assert shape.kind == "engrave"
