"""Task 2 TUI tests: colours screen with live swatches + HSL sync + save/re-edit."""
import json

import pytest
from textual.widgets import Input, Static

from tui_probe import choose
from motion_pipeline.tui.app import MenuApp
from motion_pipeline import scheme as scheme_mod

DARK = {'name': 'tui-demo', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}
COLOUR_KEYS = scheme_mod.INPUT_KEYS[1:]


def _bg_rgb(style):
    # Static.render() yields Textual Style (.background: Color) — not Rich (.bgcolor)
    c = getattr(style, 'background', None)
    return tuple(c.rgb) if c is not None else None


def text_of(widget):
    return str(widget.render())


@pytest.mark.asyncio
async def test_swatches_and_hsl_sync_live(tmp_path, monkeypatch):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        # typing a hex updates the swatch AND the HSL fields live
        scr.query_one('#background_dark', Input).value = '#ff0000'
        await pilot.pause()
        sw = scr.query_one('#swatch-background_dark', Static)
        assert '255, 0, 0' in str(sw.styles.background), sw.styles.background
        assert scr.query_one('#h-background_dark', Input).value == '0'
        assert scr.query_one('#s-background_dark', Input).value == '100'
        assert scr.query_one('#l-background_dark', Input).value == '50'
        # editing an HSL field updates the hex + swatch
        scr.query_one('#h-accent', Input).value = '120'
        scr.query_one('#s-accent', Input).value = '100'
        scr.query_one('#l-accent', Input).value = '50'
        await pilot.pause()
        assert scr.query_one('#accent', Input).value == '#00ff00'
        assert '0, 255, 0' in str(scr.query_one('#swatch-accent', Static).styles.background)


@pytest.mark.asyncio
async def test_derive_preview_save_and_reedit(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        for k in COLOUR_KEYS:
            scr.query_one(f'#{k}', Input).value = DARK[k]
        await pilot.pause()
        await choose(pilot, scr, 'derive')
        await pilot.pause()
        prev = scr.query_one('#preview', Static).render()
        assert 'secondary text' in str(prev)
        assert any(_bg_rgb(sp.style) == (0xa6, 0xb0, 0xc8) for sp in prev.spans), prev.spans  # secondary-text swatch painted
        await choose(pilot, scr, 'save')
        await pilot.pause()
        p = tmp_path / 'scheme.json'   # directly in the project (v0.4.x nested <project>/<name>/)
        saved = json.loads(p.read_text())
        assert {k: saved[k] for k in COLOUR_KEYS} == {k: DARK[k] for k in COLOUR_KEYS}
        # re-edit: change accent, save again -> persisted
        scr.query_one('#accent', Input).value = '#00c2ff'
        await pilot.pause()
        await choose(pilot, scr, 'save')
        await pilot.pause()
        await pilot.pause()
        assert json.loads(p.read_text())['accent'] == '#00c2ff'
        # re-edit: re-opening the screen prefills the saved values
        app.pop_screen(); await pilot.pause()
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        assert app.screen.query_one('#accent', Input).value == '#00c2ff'
        assert '0, 194, 255' in str(app.screen.query_one('#swatch-accent', Static).styles.background)


@pytest.mark.asyncio
async def test_invalid_hex_shows_error_not_crash(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        for k in COLOUR_KEYS:
            scr.query_one(f'#{k}', Input).value = '#0b1a4c'
        scr.query_one('#accent', Input).value = 'nope'
        await choose(pilot, scr, 'save')
        await pilot.pause()
        await pilot.pause()
        assert 'invalid hex' in text_of(scr.query_one('#error', Static))
        assert not (tmp_path / 'scheme.json').exists()


@pytest.mark.asyncio
async def test_colour_rows_labelled_swatches_visible_hex_fully_shown(tmp_path):
    from motion_pipeline import scheme as sm
    sm.save_scheme(str(tmp_path / 'scheme.json'), DARK)
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        scr = app.screen
        from tui_probe import on_screen
        labels = [str(l.render()) for l in scr.query('.colour-label')]
        assert labels == ['background dark', 'background light', 'accent', 'text']
        for k in COLOUR_KEYS:
            inp = scr.query_one(f'#{k}', Input)
            assert inp.value == DARK[k]                       # prefilled from the project
            assert inp.content_region.width >= len(DARK[k]) + 1, f'{k}: hex cut off ({inp.content_region})'
            sw = scr.query_one(f'#swatch-{k}', Static)
            assert on_screen(app, sw) and sw.region.width >= 4
            assert tuple(sw.styles.background.rgb) == sm._hex_to_srgb(DARK[k]) or \
                '#%02x%02x%02x' % tuple(sw.styles.background.rgb) == DARK[k]
            assert sw.styles.border_top[0] in ('', 'none'), f'{k}: filled swatch still framed'
            for f in ('h', 's', 'l'):
                assert scr.query_one(f'#{f}-{k}', Input).value == str(dict(zip('hsl', sm.hex_to_hsl(DARK[k])))[f])
        # variants ON (+ the new-variant name field) must not push the action rows / hint off-screen
        scr.query_one('#multi').value = True; await pilot.pause()
        from textual.widgets import Select
        scr.query_one('#variant', Select).value = '__new__'; await pilot.pause()
        for sel in ('#actions', '.hint', '#variant', '#variant-name'):
            assert on_screen(app, scr.query_one(sel)), f'{sel} off-screen with variants on at 80x24'
        # an empty swatch is still visible: framed + marker
        scr.query_one('#accent', Input).value = 'zz'; await pilot.pause()
        sw = scr.query_one('#swatch-accent', Static)
        assert sw.styles.border_top[0] == 'round' and '░' in str(sw.render())
