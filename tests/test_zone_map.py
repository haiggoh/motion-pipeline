"""Task 14 (spec B3): zone_map frame map + test-frame overlay."""
from PIL import Image

from motion_pipeline.tui.zone_map import render_frame_map, render_overlay


def test_frame_map_title_and_bottom_left_zone():
    t = render_frame_map(1920, 1080, [{'section': 'intro', 'rect': [0, 540, 960, 540]}], 40, 12, None)
    lines = t.plain.splitlines()
    assert '1920×1080' in lines[0], lines[0]
    # the zone box is in the bottom-left quadrant and carries its section label
    label_rows = [(y, line) for y, line in enumerate(lines) if 'intro' in line]
    assert label_rows, t.plain
    y, _ = label_rows[0]
    body = lines[1:]
    assert y - 1 >= len(body) // 2, (y, len(body))          # bottom half
    row = lines[y]
    assert row.index('intro') < len(row) // 2, row           # left half
    # frame border is box-drawn
    assert '┌' in t.plain and '┘' in t.plain


def test_frame_map_clips_zone_exceeding_frame():
    # must not crash; the box is clipped at the frame edge
    t = render_frame_map(1920, 1080, [{'section': 'x', 'rect': [1800, 1000, 500, 500]}], 40, 12, None)
    assert t.plain


def test_frame_map_selected_zone_is_bright_blue():
    t = render_frame_map(1920, 1080,
                         [{'section': 'a', 'rect': [0, 0, 100, 100]},
                          {'section': 'b', 'rect': [0, 540, 960, 540]}], 40, 12, 'b')
    blue_spans = [s for s in t.spans if s.style and 'bright_blue' in str(s.style)]
    assert blue_spans, t.spans
    # the blue spans render some of the selected zone's box characters
    assert any(any(c in t.plain[s.start:s.end] for c in '─│┌┐└┘b')
               for s in blue_spans), t.spans


def test_overlay_draws_zone_borders_into_image(tmp_path):
    png = tmp_path / 'frame.png'
    Image.new('RGB', (192, 108), (10, 10, 30)).save(png)
    zones = [{'section': 'intro', 'rect': [0, 54, 96, 54]}]   # bottom-left in frame px
    # 1 px per cell so the 2 px border survives the half-block downscale
    t = render_overlay(str(png), 1920, 1080, zones, 192, 54, None)
    assert t.plain.strip(), 'overlay rendered empty'
    t2 = render_overlay(str(png), 1920, 1080, [], 192, 54, None)
    styles1 = {s.style for s in t.spans}
    styles2 = {s.style for s in t2.spans}
    assert styles1 - styles2, 'zone border did not change the rendered image (styles)'
