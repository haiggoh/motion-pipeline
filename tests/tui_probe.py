"""tui_probe.py — delivery-level probes for the Textual menu (plan 0.5.0 Task 0).

Tests built on these assert what the user SEES — the computed style of a widget after
hover/focus, and whether its region is fully inside the screen — never CSS source text or
mere widget existence (playbook "Declared != delivered").

  bg_is_default(style)   Rich Style's background is the terminal's own (None / ANSI default)
  fg_is_blue(style)      foreground is ANSI bright-blue (csl highlight/hover colour)
  on_screen(app, w)      widget region non-empty and fully inside the screen
  shot(app, name)        save SVG (+PNG if rsvg-convert exists) under $MP_SHOT_DIR; no-op unset
"""
import os
import shutil
import subprocess


def bg_is_default(style) -> bool:
    bg = style.bgcolor
    return bg is None or bg.is_default


def fg_is_blue(style) -> bool:
    c = style.color
    return c is not None and c.name in ('bright_blue', 'color(12)') or (
        c is not None and c.number == 12)


def on_screen(app, widget) -> bool:
    r = widget.region
    w, h = app.screen.size
    return r.width > 0 and r.height > 0 and r.x >= 0 and r.y >= 0 \
        and r.x + r.width <= w and r.y + r.height <= h


def shot(app, name):
    d = os.environ.get('MP_SHOT_DIR')
    if not d:
        return None
    os.makedirs(d, exist_ok=True)
    svg = os.path.join(d, f'{name}.svg')
    app.save_screenshot(svg)
    if shutil.which('rsvg-convert'):
        subprocess.run(['rsvg-convert', svg, '-o', svg[:-4] + '.png'], check=False)
    return svg
