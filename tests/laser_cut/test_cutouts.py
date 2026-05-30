from freecad.laser_cut.cutouts import (
    Shape,
    circle,
    rect,
    servo_cutout,
    hc_sr04_holes,
    hc_sr04_pcb_mount,
    rfid_engrave_marker,
    arm_slot,
)


def test_circle_returns_cut_shape():
    s = circle(cx=10, cy=10, radius=5)
    assert s.kind == "cut"
    # 16-segment approximation
    assert len(s.points) == 16
    for x, y in s.points:
        assert abs(((x - 10) ** 2 + (y - 10) ** 2) ** 0.5 - 5) < 1e-6


def test_hc_sr04_holes_default_spacing_26():
    # Default spacing must match the datasheet HC-SR04 transducer center-to-center
    shapes = hc_sr04_holes(cx=60, cy=300)
    assert len(shapes) == 2
    assert all(s.kind == "cut" for s in shapes)
    centers = [(sum(p[0] for p in s.points) / len(s.points),
                sum(p[1] for p in s.points) / len(s.points))
               for s in shapes]
    centers.sort()
    assert abs(centers[0][0] - (60 - 13.0)) < 0.5  # half of 26mm spacing
    assert abs(centers[1][0] - (60 + 13.0)) < 0.5


def test_hc_sr04_pcb_mount_returns_four_corner_holes():
    # PCB 45x20mm with hole spacing 41x16mm (insets 2mm from each edge)
    holes = hc_sr04_pcb_mount(cx=120, cy=80)
    assert len(holes) == 4
    centers = sorted([
        (sum(p[0] for p in h.points) / len(h.points),
         sum(p[1] for p in h.points) / len(h.points))
        for h in holes
    ])
    # Expect 4 corners: (99.5, 72), (99.5, 88), (140.5, 72), (140.5, 88)
    expected = sorted([(99.5, 72.0), (99.5, 88.0), (140.5, 72.0), (140.5, 88.0)])
    for got, exp in zip(centers, expected):
        assert abs(got[0] - exp[0]) < 0.1
        assert abs(got[1] - exp[1]) < 0.1


def test_rfid_engrave_marker_kind():
    shape = rfid_engrave_marker(cx=75, cy=21.2, w=50, h=30)
    assert shape.kind == "engrave"


def test_arm_slot_dimensions():
    s = arm_slot(cx=120, cy=220, w=20, h=160)
    assert s.kind == "cut"
    xs = [p[0] for p in s.points]
    ys = [p[1] for p in s.points]
    assert min(xs) == 110.0
    assert max(xs) == 130.0
    assert min(ys) == 140.0
    assert max(ys) == 300.0
