# Mica Gate Pillar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a single laser-cut SVG (+ PDF) file containing all 8 acrylic pieces of the mica gate pillar described in the spec, plus a 3D-printable STL for the camera tower.

**Architecture:** Pure-Python SVG generator using `svgwrite`. Geometry is built up from small reusable primitives (finger-jointed rectangle, pentagon, fillet-corner rectangle), each with focused pytest coverage. Pieces are composed from primitives + cutout helpers, then nested onto an 800×500 mm sheet. Final output: `freecad/laser_cut/exports/mica_gate_pillar.svg` (sent to shop) and `mica_gate_pillar.pdf` (visual review). Camera tower is a separate FreeCAD script producing `camera_tower.stl`.

**Tech Stack:** Python 3.11, `svgwrite` (SVG output), `cairosvg` (SVG→PDF), `pytest`. FreeCAD MCP for camera tower STL.

**Spec:** `docs/superpowers/specs/2026-05-31-mica-gate-pillar-design.md`

---

## File Structure

```
freecad/laser_cut/
├── __init__.py                  (empty)
├── geometry.py                  Primitives: finger-joint edges, pentagon, fillet rect
├── cutouts.py                   Per-cutout shape builders (LCD, servo, HC-SR04, …)
├── pieces.py                    Per-piece composition (FRONT, BACK, LEFT, …, ARM)
├── layout.py                    Sheet nesting (positions of each piece)
├── render.py                    SVG drawing + PDF conversion
├── build_mica_pillar.py         CLI entry: build_pieces() → render() → write files
└── exports/
    ├── mica_gate_pillar.svg     Laser shop input
    ├── mica_gate_pillar.pdf     Visual review
    └── README.txt               Spec for the shop

freecad/
└── build_camera_tower.py        FreeCAD script for the 3D-printed tower (STL out)

tests/laser_cut/
├── __init__.py
├── test_geometry.py
├── test_cutouts.py
├── test_pieces.py
└── test_layout.py
```

**Module responsibilities:**

- `geometry.py` — pure shape math. No SVG. Returns lists of `(x, y)` vertex tuples or path commands. Easy to unit-test.
- `cutouts.py` — internal cutout geometry (returns vertex list + center coordinates for placement). No piece context.
- `pieces.py` — composes outline + cutouts per piece. One function per piece (`build_front()`, `build_back()`, …). Returns a `Piece` dataclass with name, outline path, cut shapes list, engrave shapes list.
- `layout.py` — assigns each piece a `(x, y)` offset on the sheet. Returns dict of `name → offset`.
- `render.py` — given pieces + layout, writes the SVG file. Handles layer colors (red cut / black engrave) + labels + orientation arrows.
- `build_mica_pillar.py` — top-level: parameters → call builders → render → write to `exports/`.

---

## Conventions

- **Units:** millimeters throughout. SVG `viewBox` is sheet dimensions in mm.
- **Coordinate system per piece:** origin at bottom-left, X right, Y up (math convention). `render.py` flips Y to SVG convention on output.
- **Sheet:** 800 mm wide × 500 mm tall.
- **Layer colors in SVG:**
  - Cut: `stroke="#ff0000"`, `stroke-width="0.05"`, `fill="none"`
  - Engrave: `stroke="#000000"`, `stroke-width="0.1"`, `fill="none"`
- **Finger-joint params** (constants in `geometry.py`):
  - `MICA_T = 3.0` (sheet thickness, = tab depth)
  - `KERF = 0.1` (laser kerf compensation)
  - `JOINT_TOL = 0.15` (slot oversizing)
  - `TAB_W = 20.0` (tab width)

---

## Task 1: Scaffold project + dependencies

**Files:**
- Create: `freecad/laser_cut/__init__.py`
- Create: `tests/laser_cut/__init__.py`
- Modify: `pyproject.toml` (add svgwrite + cairosvg to dev or optional deps)

- [ ] **Step 1: Add the laser-cut package directory**

```bash
mkdir -p /home/nguyenvd/workspace/smart_gate/freecad/laser_cut/exports
mkdir -p /home/nguyenvd/workspace/smart_gate/tests/laser_cut
touch /home/nguyenvd/workspace/smart_gate/freecad/laser_cut/__init__.py
touch /home/nguyenvd/workspace/smart_gate/tests/laser_cut/__init__.py
```

- [ ] **Step 2: Install dependencies into the project venv**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pip install svgwrite==1.4.3 cairosvg==2.7.1
```

Expected: both packages install without error.

- [ ] **Step 3: Add the deps to pyproject.toml under an `[project.optional-dependencies]` table**

Open `pyproject.toml` and append after the `[project]` block:

```toml
[project.optional-dependencies]
laser_cut = [
    "svgwrite==1.4.3",
    "cairosvg==2.7.1",
]
```

- [ ] **Step 4: Add tests-laser_cut to pytest testpaths**

Modify the existing `[tool.pytest.ini_options]` block in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q --strict-markers"
markers = [
    "integration: integration tests using mocks",
]
```

(Already covers `tests/laser_cut/` since `testpaths` includes the whole `tests` dir. No change needed if it's already this way — verify and skip.)

- [ ] **Step 5: Verify pytest discovers the new package**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/ -v
```

Expected: `no tests ran in 0.01s` (empty package found, no tests yet).

- [ ] **Step 6: Commit**

```bash
git add freecad/laser_cut/ tests/laser_cut/ pyproject.toml && git commit -m "feat(laser_cut): scaffold package + svgwrite/cairosvg deps"
```

---

## Task 2: Finger-joint edge generator

**Files:**
- Create: `freecad/laser_cut/geometry.py`
- Create: `tests/laser_cut/test_geometry.py`

The function `finger_edge(length, n_tabs, tab_w, mica_t, start_with_tab, outward)` produces vertices along ONE edge of a piece. `outward=True` means tabs stick OUT of the piece (for the piece that owns the tabs); `outward=False` means slots cut INTO the piece (for the mating piece). `start_with_tab` lets neighboring pieces alternate so they interlock cleanly.

- [ ] **Step 1: Write the failing test**

```python
# tests/laser_cut/test_geometry.py
from freecad.laser_cut.geometry import finger_edge


def test_finger_edge_outward_two_tabs():
    # 60mm edge, 2 tabs of 20mm each, mica 3mm, starts with tab
    # Expected pattern (going left-to-right along X, tabs extending in +Y):
    # corner -> up over tab1 -> down -> up over tab2 -> down -> corner
    verts = finger_edge(length=60, n_tabs=2, tab_w=20, mica_t=3, start_with_tab=True, outward=True)
    assert verts[0] == (0.0, 0.0)
    assert verts[-1] == (60.0, 0.0)
    # 2 tabs sticking outward → 4 step-up corners, 4 step-down
    # Each tab contributes a "rise" then "fall" of 3mm in Y
    # Vertex count: 2 endpoints + 4 corners per tab × 2 tabs = 10
    assert len(verts) == 10
    # Tab 1 spans x=0..20, tab 2 spans x=20..40 — wait, that's pattern "tab,tab" — but
    # finger joints alternate tab/gap/tab/gap. With 2 tabs in 60mm:
    # tab(20) + gap(20) + tab(20) = 60. So tab1 0..20, gap 20..40, tab2 40..60.
    # Inner Y on tab top = +3mm
    tab_y = 3.0
    assert (0.0, tab_y) in verts
    assert (20.0, tab_y) in verts
    assert (40.0, tab_y) in verts
    assert (60.0, tab_y) in verts
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_geometry.py::test_finger_edge_outward_two_tabs -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'freecad.laser_cut.geometry'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# freecad/laser_cut/geometry.py
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
    verts = [(0.0, 0.0)]
    direction = +1 if outward else -1
    # Pattern: alternating tab/gap segments. With n_tabs tabs and tabs/gaps alternating,
    # total segments = 2*n_tabs - 1 if start_with_tab else 2*n_tabs + 1.
    # Each segment width = tab_w (we constrain length = (2*n_tabs - 1) * tab_w
    # when start_with_tab and matches at edges).
    segments = []
    x = 0.0
    is_tab = start_with_tab
    while x < length - 1e-6:
        seg_end = min(x + tab_w, length)
        segments.append((x, seg_end, is_tab))
        x = seg_end
        is_tab = not is_tab
    for seg_start, seg_end, is_tab in segments:
        if is_tab:
            # Rise at seg_start, traverse top, fall at seg_end
            verts.append((seg_start, direction * mica_t))
            verts.append((seg_end, direction * mica_t))
        else:
            # Stay at baseline y=0
            verts.append((seg_start, 0.0))
            verts.append((seg_end, 0.0))
    # Dedupe consecutive duplicates and ensure endpoint
    deduped = [verts[0]]
    for v in verts[1:]:
        if v != deduped[-1]:
            deduped.append(v)
    if deduped[-1] != (length, 0.0):
        deduped.append((length, 0.0))
    return deduped
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_geometry.py::test_finger_edge_outward_two_tabs -v
```

Expected: PASS.

- [ ] **Step 5: Add a slot-direction test**

```python
def test_finger_edge_inward_slots():
    verts = finger_edge(length=60, n_tabs=2, tab_w=20, mica_t=3, start_with_tab=True, outward=False)
    # Slots go into -Y direction
    assert (0.0, -3.0) in verts
    assert (20.0, -3.0) in verts
```

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_geometry.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add freecad/laser_cut/geometry.py tests/laser_cut/test_geometry.py && git commit -m "feat(laser_cut): finger-joint edge primitive"
```

---

## Task 3: Pentagon outline + fillet-corner rect

**Files:**
- Modify: `freecad/laser_cut/geometry.py`
- Modify: `tests/laser_cut/test_geometry.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/laser_cut/test_geometry.py`:

```python
from freecad.laser_cut.geometry import pentagon_outline, fillet_rect


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
    # 98x40 rect with R=4 fillet returns a path approximation; check bounds
    pts = fillet_rect(width=98, height=40, radius=4, segments=8)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert min(xs) == 0.0
    assert max(xs) == 98.0
    assert min(ys) == 0.0
    assert max(ys) == 40.0
    # 4 corners × 8 segments + 4 straights = 36 points; allow ±4 for impl detail
    assert 30 <= len(pts) <= 40
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_geometry.py -v
```

Expected: 2 tests fail (`ImportError` for `pentagon_outline`, `fillet_rect`).

- [ ] **Step 3: Implement both functions**

Append to `freecad/laser_cut/geometry.py`:

```python
import math


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
    """Rectangle [0,width] x [0,height] with all 4 corners rounded by radius."""
    r = radius
    pts: list[tuple[float, float]] = []
    # SW corner: arc from (0, r) up around to (r, 0) — center (r, r), angle 180→270
    # We trace CCW starting bottom-left going right.
    # Bottom edge: (r, 0) to (width-r, 0)
    pts.append((r, 0.0))
    pts.append((width - r, 0.0))
    # SE corner: center (width-r, r), angle 270→360
    for i in range(1, segments + 1):
        a = math.radians(270 + 90 * i / segments)
        pts.append((width - r + r * math.cos(a), r + r * math.sin(a)))
    # Right edge already ends at (width, r); go up to (width, height-r) implicitly
    pts.append((width, height - r))
    # NE corner: center (width-r, height-r), angle 0→90
    for i in range(1, segments + 1):
        a = math.radians(0 + 90 * i / segments)
        pts.append((width - r + r * math.cos(a), height - r + r * math.sin(a)))
    pts.append((r, height))
    # NW corner: center (r, height-r), angle 90→180
    for i in range(1, segments + 1):
        a = math.radians(90 + 90 * i / segments)
        pts.append((r + r * math.cos(a), height - r + r * math.sin(a)))
    pts.append((0.0, r))
    # SW corner: center (r, r), angle 180→270
    for i in range(1, segments + 1):
        a = math.radians(180 + 90 * i / segments)
        pts.append((r + r * math.cos(a), r + r * math.sin(a)))
    return pts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_geometry.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add freecad/laser_cut/geometry.py tests/laser_cut/test_geometry.py && git commit -m "feat(laser_cut): pentagon outline + fillet-corner rectangle"
```

---

## Task 4: Cutout shape builders

**Files:**
- Create: `freecad/laser_cut/cutouts.py`
- Create: `tests/laser_cut/test_cutouts.py`

Each cutout returns either a `Shape` dataclass with `kind` (`"cut"` or `"engrave"`) and a list of vertex tuples. Position-shifted by the caller (the piece).

- [ ] **Step 1: Define the `Shape` dataclass + write the failing test**

```python
# tests/laser_cut/test_cutouts.py
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
    # 16-segment approximation has 16 vertices
    assert len(s.points) == 16
    # All points equidistant from center
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
    # Centers along Y axis at cy±spacing/2 → wait, our spec says along the face's Y axis
    # which here is the RIGHT face's local Y. Test uses cx as the perpendicular center.
    # We choose convention: spacing is along the X axis of the face.
    centers = [(sum(p[0] for p in s.points) / len(s.points),
                sum(p[1] for p in s.points) / len(s.points))
               for s in shapes]
    centers.sort()
    assert abs(centers[0][0] - (60 - 13.5)) < 0.5
    assert abs(centers[1][0] - (60 + 13.5)) < 0.5


def test_rfid_engrave_marker_kind():
    shape = rfid_engrave_marker(cx=75, cy=21.2, w=50, h=30)
    assert shape.kind == "engrave"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_cutouts.py -v
```

Expected: all fail (`ModuleNotFoundError`).

- [ ] **Step 3: Implement cutouts.py**

```python
# freecad/laser_cut/cutouts.py
"""Cutout shape builders. Each returns a Shape (or list of Shapes) at the given center."""

from dataclasses import dataclass
import math

from freecad.laser_cut.geometry import fillet_rect


@dataclass
class Shape:
    kind: str  # "cut" or "engrave"
    points: list[tuple[float, float]]


def circle(cx: float, cy: float, radius: float, segments: int = 16) -> Shape:
    pts = [
        (cx + radius * math.cos(2 * math.pi * i / segments),
         cy + radius * math.sin(2 * math.pi * i / segments))
        for i in range(segments)
    ]
    return Shape(kind="cut", points=pts)


def rect(cx: float, cy: float, w: float, h: float, kind: str = "cut") -> Shape:
    return Shape(kind=kind, points=[
        (cx - w / 2, cy - h / 2),
        (cx + w / 2, cy - h / 2),
        (cx + w / 2, cy + h / 2),
        (cx - w / 2, cy + h / 2),
    ])


def lcd_window(cx: float, cy: float, w: float, h: float, r: float) -> Shape:
    # fillet_rect returns points with origin at (0,0); shift to center.
    local = fillet_rect(w, h, r)
    shifted = [(cx - w / 2 + x, cy - h / 2 + y) for (x, y) in local]
    return Shape(kind="cut", points=shifted)


def servo_cutout(cx: float, cy: float, shaft_d: float = 8.0,
                 flange_spacing: float = 28.0, flange_hole_d: float = 2.7) -> list[Shape]:
    """SG90 servo: central Ø8mm shaft hole + 2 flange screw holes."""
    return [
        circle(cx, cy, shaft_d / 2),
        circle(cx - flange_spacing / 2, cy, flange_hole_d / 2),
        circle(cx + flange_spacing / 2, cy, flange_hole_d / 2),
    ]


def hc_sr04_holes(cx: float, cy: float, spacing: float = 27.0,
                   radius: float = 8.0) -> list[Shape]:
    """Two transducer holes spaced along X."""
    return [
        circle(cx - spacing / 2, cy, radius),
        circle(cx + spacing / 2, cy, radius),
    ]


def rfid_engrave_marker(cx: float, cy: float, w: float = 50.0, h: float = 30.0) -> Shape:
    return rect(cx, cy, w, h, kind="engrave")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_cutouts.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add freecad/laser_cut/cutouts.py tests/laser_cut/test_cutouts.py && git commit -m "feat(laser_cut): cutout shape builders"
```

---

## Task 5: Per-piece builders (simple pieces first)

**Files:**
- Create: `freecad/laser_cut/pieces.py`
- Create: `tests/laser_cut/test_pieces.py`

Build the 4 "simple" pieces first: FRONT, BACK, BOTTOM, drop-ARM. Each `build_*()` returns a `Piece` with name, outline (list of vertices), and a list of internal shapes.

- [ ] **Step 1: Define the `Piece` dataclass + tests**

```python
# tests/laser_cut/test_pieces.py
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
    assert len(p.cuts) == 2  # 2 horn-mount holes
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_pieces.py -v
```

Expected: all fail.

- [ ] **Step 3: Implement the 4 simple pieces**

```python
# freecad/laser_cut/pieces.py
"""Per-piece composition. Each builder returns a Piece with outline + cuts + engraves."""

from dataclasses import dataclass, field

from freecad.laser_cut.cutouts import Shape, circle, rect, lcd_window, servo_cutout, hc_sr04_holes, rfid_engrave_marker
from freecad.laser_cut.geometry import pentagon_outline


@dataclass
class Piece:
    name: str
    outline: list[tuple[float, float]]
    cuts: list[Shape] = field(default_factory=list)
    engraves: list[Shape] = field(default_factory=list)


def _rect_outline(w: float, h: float) -> list[tuple[float, float]]:
    return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]


def build_front() -> Piece:
    return Piece(name="FRONT", outline=_rect_outline(150.0, 370.0))


def build_back() -> Piece:
    outline = _rect_outline(150.0, 400.0)
    cuts: list[Shape] = []
    # Adapter cable Ø10mm at (X=15, Z=15)
    cuts.append(circle(15.0, 15.0, 5.0))
    # 6× M3 mount holes Ø3.5mm
    for x, y in [
        (8.0, 8.0), (142.0, 8.0),
        (8.0, 392.0), (142.0, 392.0),
        (8.0, 200.0), (142.0, 200.0),
    ]:
        cuts.append(circle(x, y, 1.75))
    return Piece(name="BACK", outline=outline, cuts=cuts)


def build_bottom() -> Piece:
    outline = _rect_outline(150.0, 120.0)
    # 3 vent slots 30×3 mm centered along X at Y=30, 60, 90
    cuts = [rect(cx=75.0, cy=y, w=30.0, h=3.0) for y in (30.0, 60.0, 90.0)]
    return Piece(name="BOTTOM", outline=outline, cuts=cuts)


def build_arm() -> Piece:
    outline = _rect_outline(150.0, 15.0)
    # 2 mount holes Ø2.2mm at 5mm and 13mm from one short end, on Y centerline
    cuts = [
        circle(5.0, 7.5, 1.1),
        circle(13.0, 7.5, 1.1),
    ]
    return Piece(name="ARM", outline=outline, cuts=cuts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_pieces.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add freecad/laser_cut/pieces.py tests/laser_cut/test_pieces.py && git commit -m "feat(laser_cut): build FRONT, BACK, BOTTOM, ARM pieces"
```

---

## Task 6: TOP-FLAT, SLOPE, LEFT, RIGHT pieces

**Files:**
- Modify: `freecad/laser_cut/pieces.py`
- Modify: `tests/laser_cut/test_pieces.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/laser_cut/test_pieces.py`:

```python
from freecad.laser_cut.pieces import build_top, build_slope, build_left, build_right


def test_top_has_lcd_and_camera_features():
    p = build_top()
    assert p.name == "TOP"
    # 1 LCD cutout + 4 LCD mount holes + 4 camera mount holes + 1 camera cable hole = 10 cuts
    assert len(p.cuts) == 10
    assert len(p.engraves) == 0


def test_slope_has_engrave_marker():
    p = build_slope()
    assert p.name == "SLOPE"
    # Slope outline is 150 × 42.43 (rectangular when unfolded)
    xs = [pt[0] for pt in p.outline]
    ys = [pt[1] for pt in p.outline]
    assert max(xs) == 150.0
    assert abs(max(ys) - 42.43) < 0.1
    assert len(p.engraves) == 1
    assert p.engraves[0].kind == "engrave"


def test_left_is_pentagon_with_mount_holes():
    p = build_left()
    assert p.name == "LEFT"
    assert len(p.outline) == 5  # pentagon
    assert len(p.cuts) == 4  # 4 M3 corner mount holes


def test_right_has_servo_and_hc_sr04():
    p = build_right()
    assert p.name == "RIGHT"
    assert len(p.outline) == 5  # pentagon
    # 3 servo (1 shaft + 2 flange) + 2 HC-SR04 transducers + 2 HC-SR04 mount = 7
    assert len(p.cuts) == 7
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_pieces.py -v
```

Expected: 4 new tests fail.

- [ ] **Step 3: Implement the 4 complex pieces**

Append to `freecad/laser_cut/pieces.py`:

```python
import math


def build_top() -> Piece:
    outline = _rect_outline(150.0, 90.0)
    cuts: list[Shape] = []
    # LCD viewing window 98×40 fillet R=4, centered at (75, 35)
    cuts.append(lcd_window(cx=75.0, cy=35.0, w=98.0, h=40.0, r=4.0))
    # LCD mount holes Ø3.2 at corners 93×55 spacing
    for x, y in [(28.5, 7.5), (121.5, 7.5), (28.5, 62.5), (121.5, 62.5)]:
        cuts.append(circle(x, y, 1.6))
    # Camera tower cable hole Ø8 at (75, 77.5)
    cuts.append(circle(75.0, 77.5, 4.0))
    # Camera tower mount holes Ø3.2 at 4 corners of 16×16 inscribed square
    for x, y in [(67.0, 69.5), (83.0, 69.5), (67.0, 85.5), (83.0, 85.5)]:
        cuts.append(circle(x, y, 1.6))
    return Piece(name="TOP", outline=outline, cuts=cuts)


def build_slope() -> Piece:
    # SLOPE facet unfolded is rectangular 150 × hypotenuse
    slope_proj = 30.0
    hypotenuse = math.sqrt(slope_proj ** 2 + slope_proj ** 2)  # 42.426
    outline = _rect_outline(150.0, hypotenuse)
    # Engrave marker 50×30 centered
    engraves = [rfid_engrave_marker(cx=75.0, cy=hypotenuse / 2, w=50.0, h=30.0)]
    return Piece(name="SLOPE", outline=outline, engraves=engraves)


def build_left() -> Piece:
    outline = pentagon_outline(depth=120.0, height=400.0, slope=30.0)
    # 4 mount holes Ø3.5 near the 4 outer corners
    cuts = [
        circle(5.0, 8.0, 1.75),
        circle(115.0, 8.0, 1.75),
        circle(115.0, 392.0, 1.75),
        circle(5.0, 355.0, 1.75),
    ]
    return Piece(name="LEFT", outline=outline, cuts=cuts)


def build_right() -> Piece:
    outline = pentagon_outline(depth=120.0, height=400.0, slope=30.0)
    cuts: list[Shape] = []
    cuts.extend(servo_cutout(cx=60.0, cy=200.0))
    cuts.extend(hc_sr04_holes(cx=60.0, cy=300.0))
    # 2 HC-SR04 PCB mount holes Ø3.2 at (20, 300) and (100, 300)
    cuts.append(circle(20.0, 300.0, 1.6))
    cuts.append(circle(100.0, 300.0, 1.6))
    return Piece(name="RIGHT", outline=outline, cuts=cuts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_pieces.py -v
```

Expected: 8 tests PASS total.

- [ ] **Step 5: Commit**

```bash
git add freecad/laser_cut/pieces.py tests/laser_cut/test_pieces.py && git commit -m "feat(laser_cut): build TOP, SLOPE, LEFT, RIGHT pieces"
```

---

## Task 7: Sheet layout (nesting)

**Files:**
- Create: `freecad/laser_cut/layout.py`
- Create: `tests/laser_cut/test_layout.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/laser_cut/test_layout.py
from freecad.laser_cut.layout import compute_layout, SHEET_W, SHEET_H


def test_compute_layout_all_pieces_fit():
    positions = compute_layout()
    expected_names = {"FRONT", "BACK", "LEFT", "RIGHT", "TOP", "SLOPE", "BOTTOM", "ARM"}
    assert set(positions.keys()) == expected_names

    # Every piece's bounding box must lie inside the sheet
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
    # Cheap overlap check: bounding boxes don't intersect
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_layout.py -v
```

Expected: fail (`ImportError`).

- [ ] **Step 3: Implement layout.py**

```python
# freecad/laser_cut/layout.py
"""Sheet nesting layout. Each piece gets an (x, y) offset on the sheet."""

SHEET_W = 800.0
SHEET_H = 500.0
GAP = 8.0


def compute_layout() -> dict[str, tuple[float, float]]:
    """Returns {piece_name: (x_offset, y_offset)} on the SHEET_W × SHEET_H sheet."""
    # Row 1 (bottom, y=GAP): tall pieces FRONT(150x370) + BACK(150x400) + LEFT(120x400) + RIGHT(120x400)
    # Widths: 150 + 150 + 120 + 120 = 540, plus 3 gaps = 564. Fits in 800.
    x = GAP
    y = GAP
    positions: dict[str, tuple[float, float]] = {}
    positions["BACK"] = (x, y)         # 150 × 400
    x += 150.0 + GAP
    positions["FRONT"] = (x, y)        # 150 × 370
    x += 150.0 + GAP
    positions["LEFT"] = (x, y)         # pentagon bbox 120 × 400
    x += 120.0 + GAP
    positions["RIGHT"] = (x, y)        # pentagon bbox 120 × 400
    x += 120.0 + GAP
    # Row 2 (above, y = GAP + 400 + GAP = 416): TOP(150x90) + SLOPE(150x42.4) + BOTTOM(150x120) + ARM(150x15)
    # Stack to right of row1 in remaining width: x=564 to 800. Width 236. Fits TOP(150) plus narrow.
    # Better: dedicated row above the tall row.
    x2 = GAP
    y2 = y + 400.0 + GAP  # 416
    positions["TOP"] = (x2, y2)        # 150 × 90
    x2 += 150.0 + GAP
    positions["SLOPE"] = (x2, y2)      # 150 × 42.4
    x2 += 150.0 + GAP
    positions["BOTTOM"] = (x2, y2)     # 150 × 120
    x2 += 150.0 + GAP
    positions["ARM"] = (x2, y2)        # 150 × 15
    return positions
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_layout.py -v
```

Expected: 2 tests PASS. If the second row's `y2 = 416 + 120 = 536` exceeds `SHEET_H=500`, the first test fails — increase `SHEET_H` to 600 or relayout.

If overflow occurs, adjust `SHEET_H = 600.0` in `layout.py` and rerun. Spec called for 500 originally; document the increase in the commit message.

- [ ] **Step 5: Commit**

```bash
git add freecad/laser_cut/layout.py tests/laser_cut/test_layout.py && git commit -m "feat(laser_cut): compute sheet nesting layout"
```

---

## Task 8: SVG rendering + PDF conversion

**Files:**
- Create: `freecad/laser_cut/render.py`
- Create: `freecad/laser_cut/build_mica_pillar.py`

No unit tests for rendering — verify visually by opening the output SVG/PDF and eyeballing.

- [ ] **Step 1: Implement render.py**

```python
# freecad/laser_cut/render.py
"""Render pieces to SVG + convert to PDF."""

from pathlib import Path

import svgwrite
import cairosvg

from freecad.laser_cut.pieces import Piece
from freecad.laser_cut.cutouts import Shape
from freecad.laser_cut.layout import SHEET_W, SHEET_H


CUT_COLOR = "#ff0000"
ENGRAVE_COLOR = "#000000"
CUT_STROKE = "0.05"
ENGRAVE_STROKE = "0.1"


def _polyline_d(points: list[tuple[float, float]], close: bool = True) -> str:
    if not points:
        return ""
    cmds = [f"M {points[0][0]:.3f},{points[0][1]:.3f}"]
    for x, y in points[1:]:
        cmds.append(f"L {x:.3f},{y:.3f}")
    if close:
        cmds.append("Z")
    return " ".join(cmds)


def _to_svg_y(y: float) -> float:
    """Flip Y so math-convention bottom-left origin renders with bottom at sheet bottom."""
    return SHEET_H - y


def _draw_shape(dwg: svgwrite.Drawing, shape: Shape, offset: tuple[float, float]):
    ox, oy = offset
    shifted = [(p[0] + ox, _to_svg_y(p[1] + oy)) for p in shape.points]
    color = CUT_COLOR if shape.kind == "cut" else ENGRAVE_COLOR
    stroke = CUT_STROKE if shape.kind == "cut" else ENGRAVE_STROKE
    dwg.add(dwg.path(d=_polyline_d(shifted), stroke=color, stroke_width=stroke,
                     fill="none", fill_rule="evenodd"))


def _draw_label(dwg: svgwrite.Drawing, name: str, offset: tuple[float, float],
                outline: list[tuple[float, float]]):
    """Engrave the piece name near its top-left corner."""
    ox, oy = offset
    xs = [p[0] + ox for p in outline]
    ys = [p[1] + oy for p in outline]
    cx = min(xs) + 5.0
    cy = _to_svg_y(max(ys) - 5.0)
    dwg.add(dwg.text(name, insert=(cx, cy), fill=ENGRAVE_COLOR,
                     font_size="6px", font_family="sans-serif"))


def render_svg(pieces: list[Piece], positions: dict[str, tuple[float, float]],
               output_path: Path):
    """Write all pieces to an SVG file."""
    dwg = svgwrite.Drawing(
        str(output_path),
        size=(f"{SHEET_W}mm", f"{SHEET_H}mm"),
        viewBox=f"0 0 {SHEET_W} {SHEET_H}",
    )
    for piece in pieces:
        offset = positions[piece.name]
        # Outline (cut)
        outline_shape = Shape(kind="cut", points=piece.outline)
        _draw_shape(dwg, outline_shape, offset)
        # Cutouts
        for cut in piece.cuts:
            _draw_shape(dwg, cut, offset)
        # Engraves
        for eng in piece.engraves:
            _draw_shape(dwg, eng, offset)
        # Label
        _draw_label(dwg, piece.name, offset, piece.outline)
    dwg.save()


def svg_to_pdf(svg_path: Path, pdf_path: Path):
    cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
```

- [ ] **Step 2: Implement build_mica_pillar.py**

```python
# freecad/laser_cut/build_mica_pillar.py
"""CLI: build all pieces, render SVG + PDF, write to exports/."""

from pathlib import Path

from freecad.laser_cut.pieces import (
    build_front, build_back, build_left, build_right,
    build_top, build_slope, build_bottom, build_arm,
)
from freecad.laser_cut.layout import compute_layout
from freecad.laser_cut.render import render_svg, svg_to_pdf


def main():
    pieces = [
        build_front(), build_back(), build_left(), build_right(),
        build_top(), build_slope(), build_bottom(), build_arm(),
    ]
    positions = compute_layout()
    out_dir = Path(__file__).parent / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / "mica_gate_pillar.svg"
    pdf_path = out_dir / "mica_gate_pillar.pdf"
    render_svg(pieces, positions, svg_path)
    svg_to_pdf(svg_path, pdf_path)
    print(f"Wrote {svg_path}")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the build script**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && python -m freecad.laser_cut.build_mica_pillar
```

Expected output (something like):
```
Wrote freecad/laser_cut/exports/mica_gate_pillar.svg
Wrote freecad/laser_cut/exports/mica_gate_pillar.pdf
```

If `freecad` is not importable as a package, add an `__init__.py`:

```bash
touch /home/nguyenvd/workspace/smart_gate/freecad/__init__.py
```

Then re-run.

- [ ] **Step 4: Visually inspect the PDF**

Open `freecad/laser_cut/exports/mica_gate_pillar.pdf` in a viewer. Confirm:
- 8 pieces visible
- All pieces inside sheet bounds
- LCD cutout shows fillet corners
- Servo + HC-SR04 holes visible on RIGHT pentagon
- RFID rectangle on SLOPE is black (engrave), not red (cut)
- Piece labels visible

- [ ] **Step 5: Commit**

```bash
git add freecad/__init__.py freecad/laser_cut/render.py freecad/laser_cut/build_mica_pillar.py freecad/laser_cut/exports/mica_gate_pillar.svg freecad/laser_cut/exports/mica_gate_pillar.pdf && git commit -m "feat(laser_cut): SVG+PDF render pipeline"
```

---

## Task 9: 3D-printed camera tower STL

**Files:**
- Create: `freecad/build_camera_tower.py`

This task is FreeCAD-only; runs via FreeCAD MCP `execute_code`, not standalone Python. Output: `freecad/exports/camera_tower.stl`.

- [ ] **Step 1: Implement build_camera_tower.py**

```python
# freecad/build_camera_tower.py
"""Build the camera tower (3D-printed) for the mica gate pillar.

Run via FreeCAD MCP (mcp__freecad__execute_code), not standalone Python.

Spec: docs/superpowers/specs/2026-05-31-mica-gate-pillar-design.md §6, §13.4

Geometry:
- Cylinder Ø20mm × 120mm tall (hollow, Ø14mm inner for USB cable + webcam routing)
- Base flange Ø50mm × 3mm with Ø8mm central cable bore
- 4× M3 clearance Ø3.2mm holes on flange at 22mm-side inscribed square corners
"""

import os
import FreeCAD as App
import Part

DOC_NAME = "smart_gate_camera_tower"
OUT_DIR = os.path.join(os.path.dirname(__file__), "exports")

CYL_OD = 20.0
CYL_ID = 14.0
CYL_H = 120.0
FLANGE_OD = 50.0
FLANGE_T = 3.0
CABLE_BORE = 8.0
MOUNT_HOLE_D = 3.2
MOUNT_SQUARE = 22.0  # M3 clearance holes at corners of a 22×22 square


def build():
    doc = App.newDocument(DOC_NAME)
    # Hollow cylinder
    outer = Part.makeCylinder(CYL_OD / 2, CYL_H + FLANGE_T)
    inner = Part.makeCylinder(CYL_ID / 2, CYL_H + FLANGE_T + 0.1, App.Vector(0, 0, -0.05))
    tower = outer.cut(inner)
    # Flange disc with cable bore (replaces the bottom CYL_OD section with a wider disc)
    flange_disc = Part.makeCylinder(FLANGE_OD / 2, FLANGE_T)
    flange_bore = Part.makeCylinder(CABLE_BORE / 2, FLANGE_T + 0.2, App.Vector(0, 0, -0.1))
    flange = flange_disc.cut(flange_bore)
    # M3 mount holes at 4 corners of 22mm square
    half = MOUNT_SQUARE / 2
    for x, y in [(-half, -half), (half, -half), (half, half), (-half, half)]:
        hole = Part.makeCylinder(MOUNT_HOLE_D / 2, FLANGE_T + 0.2,
                                  App.Vector(x, y, -0.1))
        flange = flange.cut(hole)
    final = flange.fuse(tower)
    Part.show(final, "camera_tower")
    doc.recompute()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "camera_tower.stl")
    final.exportStl(out_path)
    print(f"Wrote {out_path}")


build()
```

- [ ] **Step 2: Run via FreeCAD MCP**

In Claude session, call the FreeCAD MCP tool:

```
mcp__freecad__execute_code with the contents of build_camera_tower.py
```

Or alternatively from CLI if FreeCAD is on PATH:

```bash
freecad -c freecad/build_camera_tower.py
```

Expected: `Wrote freecad/exports/camera_tower.stl`. Open in Cura/PrusaSlicer to verify the tower shape.

- [ ] **Step 3: Commit**

```bash
git add freecad/build_camera_tower.py freecad/exports/camera_tower.stl && git commit -m "feat(freecad): 3D-printable camera tower for mica gate pillar"
```

---

## Task 10: Shop-facing README

**Files:**
- Create: `freecad/laser_cut/exports/README.txt`

- [ ] **Step 1: Write the README**

```text
MICA GATE PILLAR — LASER CUT SPEC
=================================

Project: Smart gate pillar enclosure (Pi 4 + ESP32 + sensors)
Date:    2026-05-31
File:    mica_gate_pillar.pdf (or .svg)

VẬT LIỆU
--------
Mica acrylic trong suốt, độ dày 3 mm.
Khổ tấm: 800 × 500 mm (1 tấm đủ).

NÉT CẮT vs NÉT KHẮC
-------------------
- Đường màu ĐỎ (RGB 255,0,0):   CẮT THỦNG
- Đường màu ĐEN (RGB 0,0,0):    KHẮC NÔNG (engrave ~0.2mm)

DANH SÁCH 8 CHI TIẾT
--------------------
1. FRONT     150 × 370 mm  (mặt trước)
2. BACK      150 × 400 mm  (mặt sau, có lỗ adapter)
3. LEFT      120 × 400 mm  (ngũ giác, mặt trái)
4. RIGHT     120 × 400 mm  (ngũ giác, mặt phải, có lỗ servo + cảm biến)
5. TOP       150 × 90  mm  (mặt trên, có lỗ LCD)
6. SLOPE     150 × 42.4 mm (mặt vát 45°, có khắc đánh dấu RFID)
7. BOTTOM    150 × 120 mm  (mặt đáy)
8. ARM       150 × 15  mm  (cần chắn)

DUNG SAI
--------
±0.2 mm cho lỗ và mép.
Đường cắt cùng tấm phải canh khoảng cách >= 5mm để tránh vỡ mica.

CẢM ƠN!
```

- [ ] **Step 2: Commit**

```bash
git add freecad/laser_cut/exports/README.txt && git commit -m "docs(laser_cut): README for the laser shop"
```

---

## Task 11: End-to-end smoke test

**Files:**
- Create: `tests/laser_cut/test_integration.py`

- [ ] **Step 1: Write an integration test that runs the full build**

```python
# tests/laser_cut/test_integration.py
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_full_build_produces_svg_and_pdf(tmp_path, monkeypatch):
    """Run the build entry point and verify SVG + PDF exist and are non-empty."""
    # Redirect exports to tmp dir
    import freecad.laser_cut.build_mica_pillar as build_mod
    real_main = build_mod.main

    def patched_main():
        from freecad.laser_cut.pieces import (
            build_front, build_back, build_left, build_right,
            build_top, build_slope, build_bottom, build_arm,
        )
        from freecad.laser_cut.layout import compute_layout
        from freecad.laser_cut.render import render_svg, svg_to_pdf
        pieces = [
            build_front(), build_back(), build_left(), build_right(),
            build_top(), build_slope(), build_bottom(), build_arm(),
        ]
        positions = compute_layout()
        svg_path = tmp_path / "out.svg"
        pdf_path = tmp_path / "out.pdf"
        render_svg(pieces, positions, svg_path)
        svg_to_pdf(svg_path, pdf_path)
        return svg_path, pdf_path

    svg_path, pdf_path = patched_main()
    assert svg_path.exists()
    assert pdf_path.exists()
    assert svg_path.stat().st_size > 1000  # non-trivial SVG
    assert pdf_path.stat().st_size > 1000
```

- [ ] **Step 2: Run integration test**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/test_integration.py -v -m integration
```

Expected: PASS.

- [ ] **Step 3: Run full test suite to confirm nothing else broke**

```bash
cd /home/nguyenvd/workspace/smart_gate && source .venv/bin/activate && pytest tests/laser_cut/ -v
```

Expected: all laser_cut tests PASS (~15-20 total across geometry, cutouts, pieces, layout, integration).

- [ ] **Step 4: Commit**

```bash
git add tests/laser_cut/test_integration.py && git commit -m "test(laser_cut): end-to-end integration test"
```

---

## Final pre-cut human review

Once all tasks are complete:

1. Open `freecad/laser_cut/exports/mica_gate_pillar.pdf` and visually inspect.
2. Cross-check each piece against §5 of the spec:
   - FRONT: blank ✓
   - SLOPE: 50×30mm engrave centered ✓
   - TOP: LCD cutout 98×40 fillet R=4 + 4 LCD mount + 4 camera mount + Ø8 cable ✓
   - LEFT: pentagon + 4 mount holes ✓
   - RIGHT: pentagon + servo (shaft + 2 flange) + HC-SR04 (2 transducer + 2 mount) ✓
   - BACK: Ø10 adapter + 6 mount holes ✓
   - BOTTOM: 3 vent slots ✓
   - ARM: 2 mount holes ✓
3. Print the PDF at 100% scale on regular paper, lay it on a 800×500mm template, and verify each piece's outline lines up with measurements in §4.
4. Cut one test piece (per spec §11.2 — a 50×50mm square with one finger joint) before committing to a full sheet cut.
5. Send `mica_gate_pillar.pdf` + `README.txt` to the laser shop.

---

## Self-Review Notes

**Spec coverage:**
- §3 Architecture: covered by Task 5/6 (piece composition)
- §4 Dimensions: covered by piece builders (hardcoded constants per piece)
- §5 Per-face cutouts: covered by Task 5/6 (each cutout enumerated)
- §6 Internal mounting: documentation in README + assembly procedure (no code)
- §7 Cable routing: documentation only
- §8 Joint geometry: Task 2 (finger_edge); however, the **actual interlock between pieces is not modeled in this plan** — pieces are drawn as flat rectangles/pentagons WITHOUT finger-joint perturbations on their edges. This is acceptable as a v1 because the wooden corner posts + acrylic cement handle assembly without needing precise interlock geometry. If true finger joints are required, add Task 12 to modify piece outlines using `finger_edge()`.
- §9 PDF output: Task 8 covers
- §10 Assembly: documentation
- §11 Testing: pre-cut visual review in Task 8 + final review section
- §12-§14 Decisions/Open questions/Risks: spec-only

**Known simplification:** Pieces are drawn with **plain rectangular/pentagon outlines** rather than finger-joint outlines. Joints are achieved via wooden corner posts (per spec §3.4). If the user later prefers true finger-joint interlock without wooden posts, add a follow-up plan to modify piece builders to use `finger_edge()` along their edges.

**Open questions (from spec §13)** — these stay open and will need physical verification at assembly time:
1. PCB mount hole positions (read from KiCad file)
2. SG90 servo flange spacing (measure actual unit)
3. Buzzer mount location (decide before assembly)
4. Camera tower fit (depends on webcam model)
5. HC-SR04 transducer spacing (measure module)
6. Pi USB-C input not modeled (acceptable per design)
7. Drop-arm closed direction (visual choice at assembly)
