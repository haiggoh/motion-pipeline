"""Task 2 TUI tests: derive/preview/save/re-edit via Textual's run_test pilot."""
import json

import pytest
from textual.widgets import Input, ListView

from motion_pipeline.tui.colours_screen import MotionPipelineApp
from motion_pipeline import scheme as scheme_mod

DARK = {'name': 'tui-demo', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}


def text_of(widget):
    return str(widget.render())


@pytest.mark.asyncio
async def test_derive_preview_save_and_reedit(tmp_path, monkeypatch):
    monkeypatch.setattr('motion_pipeline.tui.colours_screen.PROJECTS', str(tmp_path))
    app = MotionPipelineApp()
    async with app.run_test() as pilot:
        app.screen.query_one('#name', Input).value = DARK['name']
        for k in scheme_mod.INPUT_KEYS[1:]:
            app.screen.query_one(f'#{k}', Input).value = DARK[k]
        await pilot.click('#derive')
        from textual.widgets import Static
        assert 'secondary_text: #a6b0c8' in text_of(app.screen.query_one('#preview', Static))
        await pilot.click('#save')
        p = tmp_path / DARK['name'] / 'scheme.json'
        assert p.is_file()
        assert json.loads(p.read_text()) == DARK
        # re-edit: change accent, save again, reload -> persisted
        app.screen.query_one('#accent', Input).value = '#00c2ff'
        await pilot.pause()
        await pilot.click('#save')
        await pilot.pause()
        assert json.loads(p.read_text())['accent'] == '#00c2ff'
        # the saved scheme appears in the re-edit list (G3)
        lv = app.screen.query_one('#schemes', ListView)
        assert any(getattr(i, 'id', '') == f'scheme-{DARK["name"]}' for i in lv.children)


@pytest.mark.asyncio
async def test_invalid_hex_shows_error_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr('motion_pipeline.tui.colours_screen.PROJECTS', str(tmp_path))
    app = MotionPipelineApp()
    async with app.run_test() as pilot:
        app.screen.query_one('#name', Input).value = 'bad'
        for k in scheme_mod.INPUT_KEYS[1:]:
            app.screen.query_one(f'#{k}', Input).value = '#0b1a4c'
        app.screen.query_one('#accent', Input).value = 'nope'
        await pilot.click('#save')
        from textual.widgets import Static
        assert 'invalid hex' in text_of(app.screen.query_one('#error', Static))
        assert not (tmp_path / 'bad' / 'scheme.json').exists()
