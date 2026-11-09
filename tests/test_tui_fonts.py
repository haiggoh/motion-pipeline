"""Task 3 TUI tests: font config save + licence warning for client fonts."""
import json

import pytest
from textual.widgets import Button, Input, Select, Static

from motion_pipeline.tui.fonts_screen import FontsScreen
from motion_pipeline.tui.colours_screen import MotionPipelineApp


def text_of(widget):
    return str(widget.render())


@pytest.mark.asyncio
async def test_save_bundled_font_config(tmp_path, monkeypatch):
    monkeypatch.setattr('motion_pipeline.tui.colours_screen.PROJECTS', str(tmp_path))
    monkeypatch.setattr('motion_pipeline.tui.fonts_screen.PROJECTS', str(tmp_path))
    app = MotionPipelineApp()
    async with app.run_test() as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        app.screen.query_one('#name', Input).value = 'fp'
        app.screen.query_one('#family', Select).value = 'Montserrat'
        await pilot.pause()
        app.screen.query_one('#save', Button).press()
        await pilot.pause()
        cfg = json.loads((tmp_path / 'fp' / 'project.json').read_text())
        assert cfg['fonts']['family'] == 'Montserrat'
        assert cfg['fonts']['roles']['headline'] == 700
        # bundled family -> no licence warning
        assert text_of(app.screen.query_one('#licence-warning', Static)) == ''


@pytest.mark.asyncio
async def test_client_font_shows_licence_warning(tmp_path, monkeypatch):
    monkeypatch.setattr('motion_pipeline.tui.colours_screen.PROJECTS', str(tmp_path))
    monkeypatch.setattr('motion_pipeline.tui.fonts_screen.PROJECTS', str(tmp_path))
    proj = tmp_path / 'cp'
    (proj / 'fonts').mkdir(parents=True)
    (proj / 'fonts' / 'ClientFont-Regular.ttf').write_bytes(b'fixture')
    app = MotionPipelineApp()
    async with app.run_test() as pilot:
        app.push_screen(FontsScreen(extra_families=['ClientFont']))
        await pilot.pause()
        app.screen.query_one('#name', Input).value = 'cp'
        app.screen.query_one('#family', Select).value = 'ClientFont'
        await pilot.pause()
        warn = text_of(app.screen.query_one('#licence-warning', Static))
        assert 'LICENCE WARNING' in warn and 'non-OFL' in warn
        app.screen.query_one('#save', Button).press()
        await pilot.pause()
        # gate passes (client font found) but flagged; config saved
        cfg = json.loads((tmp_path / 'cp' / 'project.json').read_text())
        assert cfg['fonts']['family'] == 'ClientFont'
