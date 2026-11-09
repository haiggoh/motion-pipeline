"""Task 3 TUI tests: font search over system fonts + bundled OFL + licence warning."""
import json
import os

import pytest
from textual.widgets import Button, Input, ListView, Static

from motion_pipeline.tui.fonts_screen import FontsScreen, system_fonts
from motion_pipeline.tui.app import MenuApp as MotionPipelineApp


def text_of(widget):
    return str(widget.render())


def test_system_fonts_enumerated():
    fams = system_fonts()
    assert len(fams) > 20, f'only {len(fams)} families — font dirs missing?'
    assert all(isinstance(p, str) and os.path.isfile(p) for p in fams.values())


@pytest.mark.asyncio
async def test_font_search_filters_and_selects(tmp_path):
    app = MotionPipelineApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        lv = scr.query_one('#fonts', ListView)
        total = len(lv.children)
        assert total > 20
        # bundled OFL families listed first (path None = bundled)
        assert scr._shown[0][1] is None and scr._shown[0][0] in ('Inter', 'Montserrat'), scr._shown[:2]
        # filter narrows the list live
        scr.query_one('#font-search', Input).value = 'montserrat'
        await pilot.pause()
        assert len(scr._shown) < total
        assert any(f == 'Montserrat' for f, _p, _s in scr._shown)
        # selecting a system font copies it into the project's gitignored fonts/ + warns
        allfams = system_fonts()
        sysfam = next((f for f in allfams if 'Avenir' in f), sorted(allfams)[10])
        scr.query_one('#font-search', Input).value = sysfam[:6]
        await pilot.pause()
        _f, _p, seq = next(s for s in scr._shown if s[0] == sysfam)
        from types import SimpleNamespace
        scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))
        await pilot.pause()
        assert (tmp_path / 'fonts' / os.path.basename(system_fonts()[sysfam])).is_file()
        warn = text_of(scr.query_one('#licence-warning', Static))
        assert 'LICENCE WARNING' in warn and 'gitignored' in warn


@pytest.mark.asyncio
async def test_save_bundled_font_config(tmp_path):
    app = MotionPipelineApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        _f, _p, seq = next(s for s in scr._shown if s[0] == 'Montserrat')
        from types import SimpleNamespace
        scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))
        await pilot.pause()
        scr.query_one('#save', Button).press()
        await pilot.pause()
        await pilot.pause()
        cfg = json.loads((tmp_path / 'project.json').read_text())
        assert cfg['fonts']['family'] == 'Montserrat'
        assert cfg['fonts']['roles']['headline'] == 700
        assert text_of(scr.query_one('#licence-warning', Static)) == ''
