"""zone_map.py — visual keep-out zone views for the zones screen (spec B3).

render_frame_map: a box-drawn frame of the project's aspect (2:1 cell height ratio) with each
zone of the current aspect as a labelled rectangle; the selected zone is bright_blue.
render_overlay: the background-test frame PNG as a half-block image with the zone borders drawn
into the pixels first (Pillow, neutral white, 2 px).
"""
import os

from rich.text import Text

_CORNERS = {'tl': '┌', 'tr': '┐', 'bl': '└', 'br': '┘'}
_H, _V = '─', '│'


def render_frame_map(width_px, height_px, zones, cols, rows, selected=None):
    """Box-drawn frame of the aspect fitted into cols x rows cells (cell height = 2x width),
    title '<W>×<H> (<aspect>)', each zone a labelled box, selected zone in bright_blue.
    Overlapping zones: later zones draw last (last wins). Zones outside the frame are clipped."""
    aspect = width_px / max(1, height_px)
    w = max(4, min(cols, int(rows * 2 * aspect)))
    h = max(3, min(rows, int(w / (2 * aspect))))
    grid = [[(' ', False)] * w for _ in range(h)]

    def put(x, y, ch, sel=False):
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = (ch, sel)

    for x in range(w):
        put(x, 0, _H)
        put(x, h - 1, _H)
    for y in range(h):
        put(0, y, _V)
        put(w - 1, y, _V)
    put(0, 0, _CORNERS['tl']); put(w - 1, 0, _CORNERS['tr'])
    put(0, h - 1, _CORNERS['bl']); put(w - 1, h - 1, _CORNERS['br'])

    for z in zones:
        x, y, zw, zh = z['rect']
        sel = z.get('section') == selected
        zx0 = max(0, min(w - 1, int(x / width_px * w)))
        zy0 = max(0, min(h - 1, int(y / height_px * h)))
        zx1 = max(0, min(w - 1, int((x + zw) / width_px * w)))
        zy1 = max(0, min(h - 1, int((y + zh) / height_px * h)))
        if zx1 < zx0:
            zx1 = zx0
        if zy1 < zy0:
            zy1 = zy0
        for x in range(zx0, zx1 + 1):
            put(x, zy0, _H, sel); put(x, zy1, _H, sel)
        for y in range(zy0, zy1 + 1):
            put(zx0, y, _V, sel); put(zx1, y, _V, sel)
        put(zx0, zy0, _CORNERS['tl'], sel); put(zx1, zy0, _CORNERS['tr'], sel)
        put(zx0, zy1, _CORNERS['bl'], sel); put(zx1, zy1, _CORNERS['br'], sel)
        # section name inside the box (clipped); on the top border when the box is one row tall
        label_y = zy0 + 1 if zy1 > zy0 + 1 else zy0
        for i, ch in enumerate(str(z.get('section', ''))):
            if zx0 + 1 + i < zx1:
                put(zx0 + 1 + i, label_y, ch, sel)

    out = Text(f'{width_px}×{height_px} (aspect {width_px / max(1, height_px):.3g})',
               style='bold')
    for row in grid:
        line = Text()
        run, run_sel = '', False
        for ch, sel in row:
            if sel != run_sel:
                if run:
                    line.append(run, style='bright_blue' if run_sel else None)
                run, run_sel = '', sel
            run += ch
        if run:
            line.append(run, style='bright_blue' if run_sel else None)
        out.append('\n')
        out.append(line)
    return out


def render_overlay(png_path, width_px, height_px, zones, max_w, max_h, selected=None):
    """The test-frame PNG as a half-block Text with the zone borders drawn into the image
    first (neutral white, 2 px; the selected zone bright_blue)."""
    from PIL import Image, ImageDraw

    from .ansi_image import render_ansi_image
    img = Image.open(png_path).convert('RGB')
    dr = ImageDraw.Draw(img)
    for z in zones:
        x, y, w, h = z['rect']
        box = [int(x / width_px * img.width), int(y / height_px * img.height),
               int((x + w) / width_px * img.width), int((y + h) / height_px * img.height)]
        sel = z.get('section') == selected
        colour = (80, 140, 255) if sel else (240, 240, 240)
        dr.rectangle(box, outline=colour, width=2)
    tmp = png_path + '.zones.png'
    img.save(tmp)
    try:
        return render_ansi_image(tmp, max_w=max_w, max_h=max_h)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
