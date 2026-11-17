"""font_preview.py — render sample text in given faces to a PNG (Task 10): the inline
half-block preview and the sharp Quick Look PNG of the fonts screen."""
SAMPLE_TEXT = 'Kinetische Typografie — Äpfel über Größe · Quick brown fox 0123'


def render_sample(lines, width_px, fg, bg, scale=1.0):
    """lines: [(text, font_path, face_index, px)] -> PIL.Image of width_px*scale, each line
    drawn in its face at px*scale (clipped to the width), stacked vertically."""
    from PIL import Image, ImageDraw, ImageFont
    W = max(1, int(width_px * scale))
    prepared = []
    for text, font_path, face_index, px in lines:
        font = ImageFont.truetype(font_path, max(1, int(px * scale)), index=face_index)
        prepared.append((text, font, max(1, int(px * scale * 1.25))))
    H = sum(h for _t, _f, h in prepared) or 1
    img = Image.new('RGB', (W, H), bg)
    dr = ImageDraw.Draw(img)
    y = 0
    for text, font, h in prepared:
        dr.text((0, y), text, font=font, fill=fg)
        y += h
    return img
