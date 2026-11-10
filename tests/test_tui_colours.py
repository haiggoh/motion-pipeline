"""Task 2 TUI tests: colours screen with live swatches + HSL sync + save/re-edit."""
import json

import pytest
from textual.widgets import Button, Input, Static

from tui_probe import choose
from motion_pipeline.tui.app import MenuApp
from motion_pipeline import scheme as scheme_mod

DARK = {'name': 'tui-demo', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}
COLOUR_KEYS = scheme_mod.INPUT_KEYS[1:]


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
        scr.query_one('#name', Input).value = DARK['name']
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
        scr.query_one('#name', Input).value = DARK['name']
        for k in COLOUR_KEYS:
            scr.query_one(f'#{k}', Input).value = DARK[k]
        await pilot.pause()
        await choose(pilot, scr, 'derive')
        await pilot.pause()
        assert 'secondary_text: #a6b0c8' in text_of(scr.query_one('#preview', Static))
        await choose(pilot, scr, 'save')
        await pilot.pause()
        p = tmp_path / DARK['name'] / 'scheme.json'
        assert p.is_file() and json.loads(p.read_text()) == DARK
        # re-edit: change accent, save again -> persisted
        scr.query_one('#accent', Input).value = '#00c2ff'
        await pilot.pause()
        await choose(pilot, scr, 'save')
        await pilot.pause()
        await pilot.pause()
        assert json.loads(p.read_text())['accent'] == '#00c2ff'
        # the saved scheme appears in the re-edit list
        from textual.widgets import ListView
        lv = scr.query_one('#schemes', ListView)
        assert any(getattr(i, 'id', '') == f'scheme-{DARK["name"]}' for i in lv.children)


@pytest.mark.asyncio
async def test_invalid_hex_shows_error_not_crash(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        scr.query_one('#name', Input).value = 'bad'
        for k in COLOUR_KEYS:
            scr.query_one(f'#{k}', Input).value = '#0b1a4c'
        scr.query_one('#accent', Input).value = 'nope'
        await choose(pilot, scr, 'save')
        await pilot.pause()
        await pilot.pause()
        assert 'invalid hex' in text_of(scr.query_one('#error', Static))
        assert not (tmp_path / 'bad' / 'scheme.json').exists()
