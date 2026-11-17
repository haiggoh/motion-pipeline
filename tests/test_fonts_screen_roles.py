"""Task 9 role tests (plan 2026-11-16): prefill, per-role pick, named weights, save-gate,
P5 browsing copies nothing, loader in the list area."""
import os
import threading
from types import SimpleNamespace

import pytest
from textual.widgets import ListView, LoadingIndicator, Select, Static

from motion_pipeline import font_index, project
from motion_pipeline.font_index import BUNDLED_DIR
from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.fonts_screen import FontsScreen
from tui_probe import choose

HELV = '/System/Library/Fonts/Helvetica.ttc'
_REAL_SCAN = font_index.scan  # captured BEFORE any monkeypatch (else the fake recurses)


def client_dir(tmp_path):
    d = tmp_path / 'client-fonts'
    d.mkdir()
    if os.path.exists(HELV):
        os.symlink(HELV, d / 'ClientX.ttc')  # family 'Helvetica' via content, not name
    return d


def fake_scan(tmp_path, monkeypatch, extra=()):
    def fake(dirs=None, cache_path=None, progress=None):
        return _REAL_SCAN(dirs=[BUNDLED_DIR, *extra],
                          cache_path=str(tmp_path / 'font-cache.json'))
    monkeypatch.setattr(font_index, 'scan', fake)


async def wait_scan(pilot, scr, timeout=10.0):
    for _ in range(int(timeout / 0.05)):
        await pilot.pause(0.05)
        if scr._all:
            return
    raise AssertionError('font scan never finished')


def pick(scr, family):
    seq = next(s for f, s in scr._shown if f == family)
    scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))


@pytest.mark.asyncio
async def test_screen_prefills_saved_roles(tmp_path, monkeypatch):
    fake_scan(tmp_path, monkeypatch)
    p = project.default_project('demo')
    p['fonts'] = {'roles': {'headline': {'family': 'Montserrat', 'weight': 700,
                                          'file': 'motion_pipeline/fonts/Montserrat/Montserrat-Bold.ttf', 'index': 0},
                            'label': {'family': 'Montserrat', 'weight': 600,
                                      'file': 'motion_pipeline/fonts/Montserrat/Montserrat-SemiBold.ttf', 'index': 0},
                            'body': {'family': 'Inter', 'weight': 400,
                                     'file': 'motion_pipeline/fonts/Inter/Inter-Regular.otf', 'index': 0},
                            'emphasis': {'family': 'Inter', 'weight': 700,
                                         'file': 'motion_pipeline/fonts/Inter/Inter-Bold.otf', 'index': 0}}}
    project.save(str(tmp_path), p)
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        assert 'Montserrat' in str(scr.query_one('#role-headline-family', Static).render())
        assert scr.query_one('#role-headline-weight', Select).value == 700
        assert 'Inter' in str(scr.query_one('#role-body-family', Static).render())
        assert scr.query_one('#role-body-weight', Select).value == 400


@pytest.mark.asyncio
async def test_pick_family_for_headline_only(tmp_path, monkeypatch):
    if not os.path.exists(HELV):
        pytest.skip('Helvetica.ttc not present')
    fake_scan(tmp_path, monkeypatch, extra=[str(client_dir(tmp_path))])
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        scr.query_one('#edit-role', Select).value = 'headline'
        pick(scr, 'Helvetica')
        await pilot.pause()
        assert 'Helvetica' in str(scr.query_one('#role-headline-family', Static).render())
        assert str(scr.query_one('#role-body-family', Static).render()) == '(none)'  # untouched


@pytest.mark.asyncio
async def test_weight_select_shows_names_of_that_family(tmp_path, monkeypatch):
    fake_scan(tmp_path, monkeypatch)
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        pick(scr, 'Montserrat')
        await pilot.pause()
        sel = scr.query_one('#role-headline-weight', Select)
        labels = [str(prompt) for prompt, _value in sel._options]  # Select._options = (prompt, value)
        assert 'SemiBold (600)' in labels and 'Bold (700)' in labels, labels


@pytest.mark.asyncio
async def test_save_invalid_config_writes_nothing(tmp_path, monkeypatch):
    fake_scan(tmp_path, monkeypatch)
    project.save(str(tmp_path), project.default_project('demo'))
    before = (tmp_path / 'project.json').read_bytes()
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        scr.query_one('#edit-role', Select).value = 'all'
        pick(scr, 'Montserrat')
        scr._all['Montserrat'] = []  # gate must fail: no faces left for the selected family
        await pilot.pause()
        await choose(pilot, scr, 'save')
        await pilot.pause(0.5)
        assert 'error' in str(scr.query_one('#error', Static).render()).lower() or \
            str(scr.query_one('#error', Static).render()).startswith('error')
        assert (tmp_path / 'project.json').read_bytes() == before  # byte-identical


@pytest.mark.asyncio
async def test_browsing_copies_nothing(tmp_path, monkeypatch):
    if not os.path.exists(HELV):
        pytest.skip('Helvetica.ttc not present')
    fake_scan(tmp_path, monkeypatch, extra=[str(client_dir(tmp_path))])
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        pick(scr, 'Helvetica')  # a system/client family
        await pilot.pause()
        assert not (tmp_path / 'fonts').exists() or not os.listdir(tmp_path / 'fonts')  # P5
        assert 'LICENCE WARNING' in str(scr.query_one('#licence-warning', Static).render())


@pytest.mark.asyncio
async def test_loader_shown_in_list_area_during_scan(tmp_path, monkeypatch):
    ev = threading.Event()

    def blocking_scan(dirs=None, cache_path=None, progress=None):
        ev.wait(10)
        return _REAL_SCAN(dirs=[BUNDLED_DIR], cache_path=str(tmp_path / 'c.json'))

    monkeypatch.setattr(font_index, 'scan', blocking_scan)
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause(0.5)
        scr = app.screen
        loader = scr.query_one('#scan-loader', LoadingIndicator)
        fl = scr.query_one('#fontlist')
        assert loader in fl.children or any(loader in w.children for w in fl.walk_children()), 'loader not in #fontlist'
        assert loader.display is not False and 'scanning fonts' in str(scr.query_one('#scan-status', Static).render())
        ev.set()
        await wait_scan(pilot, scr)
        await pilot.pause()
        assert scr.query_one('#scan-loader').display is False
        assert len(scr.query_one('#fonts', ListView).children) >= 2
