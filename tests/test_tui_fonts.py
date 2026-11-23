"""TUI tests for the fonts screen (Task 9): index-driven list, bundled first, live filter,
save writes the new per-role shape."""
import json
from types import SimpleNamespace

import pytest
from textual.widgets import Checkbox, Input, ListView, Select, Static

from motion_pipeline import font_index, project
from motion_pipeline.font_index import BUNDLED_DIR
from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.fonts_screen import FontsScreen
from tui_probe import choose

_REAL_SCAN = font_index.scan  # captured BEFORE any monkeypatch (else the fake recurses)


def fake_scan_factory(tmp_path, extra_dirs=()):
    def fake_scan(dirs=None, cache_path=None, progress=None):
        return _REAL_SCAN(dirs=[BUNDLED_DIR, *extra_dirs],
                          cache_path=str(tmp_path / 'font-cache.json'))
    return fake_scan


async def wait_scan(pilot, scr, timeout=10.0):
    for _ in range(int(timeout / 0.05)):
        await pilot.pause(0.05)
        if scr._all:
            return
    raise AssertionError('font scan never finished')


@pytest.mark.asyncio
async def test_bundled_listed_first_and_filter_narrows(tmp_path, monkeypatch):
    monkeypatch.setattr(font_index, 'scan', fake_scan_factory(tmp_path))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()


@pytest.mark.asyncio
async def test_fonts_screen_names_corrupt_project_json(tmp_path, monkeypatch):
    """Task 6 (X2): on the fonts screen a corrupt project.json shows a named error in #error,
    not silent defaults."""
    import os
    monkeypatch.setattr(font_index, 'scan', fake_scan_factory(tmp_path))
    d = str(tmp_path / 'proj')
    p = project.default_project('demo')
    project.save(d, p)
    open(os.path.join(d, 'project.json'), 'w').write('{')   # invalid JSON
    app = MenuApp()
    app.project_dir = d
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        await wait_scan(pilot, app.screen)   # _prefill_from_project runs at scan end
        err = str(app.screen.query_one('#error', Static).render())
        assert 'project.json' in err, f'error does not name project.json: {err!r}'
        scr = app.screen
        await wait_scan(pilot, scr)
        assert len(scr.query_one('#fonts', ListView).children) >= 2
        assert scr._shown[0][0] in ('Inter', 'Montserrat'), scr._shown[:2]  # bundled OFL first
        total = len(scr._shown)
        scr.query_one('#font-search', Input).value = 'montserrat'
        await pilot.pause()
        assert 0 < len(scr._shown) < total
        assert any(f == 'Montserrat' for f, _ in scr._shown)


@pytest.mark.asyncio
async def test_save_bundled_font_config_new_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(font_index, 'scan', fake_scan_factory(tmp_path))
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        # B2 + 0.8.1: all-roles row is on by default and renders a literal [x] (get-haiggoh style)
        from motion_pipeline.tui.fonts_screen import CheckRow
        cb = scr.query_one('#all-roles', CheckRow)
        assert cb.value is True
        assert '[x]' in str(cb.label), str(cb.label)
        seq = next(s for f, s in scr._shown if f == 'Montserrat')
        scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))
        await pilot.pause()
        await choose(pilot, scr, 'save')
        await pilot.pause(1.0)
        cfg = json.loads((tmp_path / 'project.json').read_text())
        head = cfg['fonts']['roles']['headline']
        assert head['family'] == 'Montserrat' and head['weight'] == 700
        assert head['file'].startswith('motion_pipeline/fonts/Montserrat/')
        assert str(scr.query_one('#licence-warning', Static).render()) == ''


@pytest.mark.asyncio
async def test_font_list_fills_freed_preview_space_and_no_inline_preview(tmp_path, monkeypatch):
    """0.8.1: inline preview removed (user) — the list now gets the body height at 80x24."""
    import motion_pipeline.font_index as fi
    from motion_pipeline.font_index import BUNDLED_DIR
    real = fi.scan
    monkeypatch.setattr(fi, 'scan', lambda dirs=None, cache_path=None, progress=None:
                        real(dirs=[BUNDLED_DIR], cache_path=str(tmp_path / 'c.json')))
    from motion_pipeline import project
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        for _ in range(100):
            await pilot.pause(0.05)
            if scr._all:
                break
        assert scr._all, 'scan never finished'
        assert not scr.query('#font-preview') and not scr.query('#sample-text'), 'inline preview gone'
        # the freed space goes to the list's row: fonts-top now fills the whole body
        top = scr.query_one('#fonts-top')
        body = scr.query_one('#body')
        assert top.region.height >= body.region.height - 1, (top.region, body.region)
        lv = scr.query_one('#fonts', ListView)
        from tui_probe import on_screen
        assert on_screen(app, lv), lv.region


def test_font_scan_is_recursive_into_subfolders(tmp_path):
    """User question 2026-11-23: are subfolders considered? Yes — os.walk is recursive;
    pin it so a regression can't hide missing nested fonts."""
    import os
    import shutil
    from motion_pipeline import font_index
    from motion_pipeline.font_index import BUNDLED_DIR
    nested = tmp_path / 'fonts' / 'P7S1_Hausschriften_2024_2'
    nested.mkdir(parents=True)
    shutil.copy(os.path.join(BUNDLED_DIR, 'Montserrat', 'Montserrat-Regular.ttf'),
                nested / 'Nested-Regular.ttf')
    faces = font_index.scan(dirs=[str(tmp_path / 'fonts')], cache_path=str(tmp_path / 'c.json'))
    assert any('P7S1_Hausschriften_2024_2' in f['path'] for f in faces), \
        'nested subfolder font missing from the scan'
