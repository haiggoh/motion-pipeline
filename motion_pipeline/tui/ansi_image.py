"""ansi_image.py — render a PNG as an ANSI half-block image (Textual Static renderable) using
PIL+numpy — one '▀' cell per 1x2 pixel block, fg = top pixel, bg = bottom pixel.

Moved here from tui/app.py in Task 10; app.py re-exports it for existing imports.
"""


def render_ansi_image(path, max_w=160, max_h=90):
    import numpy as np
    from PIL import Image as PILImage
    from rich.text import Text

    img = PILImage.open(path).convert('RGB')
    img.thumbnail((max_w, max_h * 2))  # 2 pixel rows per terminal cell row
    a = np.asarray(img)
    h, w = a.shape[:2]
    rows = h // 2
    out = Text()
    for y in range(rows):
        top = a[y * 2]
        bot = a[y * 2 + 1] if y * 2 + 1 < h else top
        for x in range(w):
            t, b = top[x], bot[x]
            out.append('▀', style=f'#{t[0]:02x}{t[1]:02x}{t[2]:02x} on #{b[0]:02x}{b[1]:02x}{b[2]:02x}')
        if y < rows - 1:
            out.append('\n')
    return out
