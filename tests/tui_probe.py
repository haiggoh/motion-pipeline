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
    """Region inside the screen AND actually painted there: the widget at the region's
    centre is this widget (or a child). A region alone is NOT clipped by a parent container,
    so a field hidden below its column's edge still has in-screen coordinates (0.5.0 fonts
    screen: two weight fields clipped while region-only checks passed)."""
    r = widget.region
    w, h = app.screen.size
    if not (r.width > 0 and r.height > 0 and r.x >= 0 and r.y >= 0
            and r.x + r.width <= w and r.y + r.height <= h):
        return False
    try:
        hit, _ = app.screen.get_widget_at(r.x + r.width // 2, r.y + r.height // 2)
    except Exception:
        return False
    return hit is widget or widget in hit.ancestors


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


async def choose(pilot, screen, action_id):
    """Pick an action row the way a user does: focus the action list, move the highlight to
    the row, press Enter (delivery path: OptionList selection -> ActionMenu.Chosen)."""
    menu = screen.query_one('#actions')
    menu.focus()
    menu.highlighted = menu.get_option_index(action_id)
    await pilot.pause()
    await pilot.press('enter')
    await pilot.pause()
