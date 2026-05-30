import pytest


@pytest.mark.integration
def test_full_build_produces_svg_and_pdf(tmp_path):
    """Build all pieces, layout, and render to SVG+PDF in a tmp dir."""
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

    assert svg_path.exists()
    assert pdf_path.exists()
    assert svg_path.stat().st_size > 1000
    assert pdf_path.stat().st_size > 1000
