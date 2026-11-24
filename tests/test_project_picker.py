"""Task 3 (plan 2026-11-16): step-0 project picker, create-refuses-existing, apply format,
create from sample. Pilot tests drive the real screen; list_projects is unit-tested too."""
import os

import pytest
from textual.widgets import Checkbox, Input, Label, ListView, Select, Static
from tui_probe import choose

from motion_pipeline import config, project, projects_list
from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.project_screen import ProjectScreen


def mk(root, name, aspect='16:9', fps=60, **over):
    d = os.path.join(str(root), name)
    p = project.default_project(name, aspect=aspect, fps=fps)
    p.update(over)
    project.save(d, p)
    return d


def picker_labels(scr):
    return [str(li.query_one(Label).render()) for li in scr.query_one('#projects', ListView).children]


async def select_picker_item(pilot, scr, index):
    lv = scr.query_one('#projects', ListView)
    lv.focus()
    await pilot.pause()
    lv.index = index
    await pilot.press('enter')
    await pilot.pause()


@pytest.mark.asyncio
async def test_picker_lists_projects_newest_first(_isolated_config):
    root = _isolated_config
    old = mk(root, 'old')
    new = mk(root, 'new')
    os.utime(os.path.join(old, 'project.json'), (1000, 1000))
    os.utime(os.path.join(new, 'project.json'), (2000, 2000))
    entries = projects_list.list_projects(str(root))
    assert [e['name'] for e in entries] == ['new', 'old']
    assert all(e['error'] is None and e['aspect'] == '16:9' for e in entries)
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        scr = app.screen
        assert isinstance(scr, ProjectScreen)
        labels = picker_labels(scr)
        assert labels[0].startswith('new') and labels[1].startswith('old'), labels


@pytest.mark.asyncio
async def test_picker_shows_invalid_project_with_error(_isolated_config):
    root = _isolated_config
    bad = os.path.join(str(root), 'broken')
    os.makedirs(bad)
    with open(os.path.join(bad, 'project.json'), 'w') as f:
        f.write('{"name": "broken"}')  # missing required keys -> validate() raises
    mk(root, 'good')
    entries = projects_list.list_projects(str(root))
    b = next(e for e in entries if e['name'] == 'broken')
    assert b['error'] and 'missing key' in b['error'], b
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        scr = app.screen
        labels = picker_labels(scr)
        assert any(lab.startswith('broken') for lab in labels), labels
        idx = next(i for i, e in enumerate(scr._entries.values()) if e['name'] == 'broken')
        await select_picker_item(pilot, scr, idx)
        assert app.project_dir is None  # broken project never loads
        assert 'missing key' in str(scr.query_one('#error', Static).render())


@pytest.mark.asyncio
async def test_select_project_loads_it(_isolated_config):
    root = _isolated_config
    d = mk(root, 'acme', aspect='9:16', fps=25)
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        scr = app.screen
        await select_picker_item(pilot, scr, 0)
        assert app.project_dir == d
        assert scr.query_one('#aspect', Select).value == '9:16'
        assert scr.query_one('#fps', Select).value == 25
        assert not scr.query_one('#actions').get_option('home').disabled
        assert config.last_project() == d
        assert scr.query_one('#actions').get_option('format').disabled  # fields unchanged


@pytest.mark.asyncio
async def test_create_existing_refused(_isolated_config):
    root = _isolated_config
    d = mk(root, 'acme', fps=25)
    before = open(os.path.join(d, 'project.json')).read()
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        scr = app.screen
        scr.query_one('#name', Input).value = 'acme'
        await choose(pilot, scr, 'create')
        await pilot.pause()
        err = str(scr.query_one('#error', Static).render())
        assert 'already exists' in err and 'acme' in err, err
        assert open(os.path.join(d, 'project.json')).read() == before  # byte-identical


@pytest.mark.asyncio
async def test_apply_format_enabled_only_when_changed_and_warns_zones(_isolated_config):
    root = _isolated_config
    d = mk(root, 'acme')  # 16:9
    p = project.load(d)
    p['zones'] = [{'section': 's', 'rect': [0, 0, 10, 10], 'aspect': '16:9'}]
    project.save(d, p)
    app = MenuApp()
    app.project_dir = d
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        scr = app.screen
        menu = scr.query_one('#actions')
        assert menu.get_option('format').disabled
        scr.query_one('#aspect', Select).value = '1:1'
        await pilot.pause()
        assert not menu.get_option('format').disabled, 'changed aspect must enable Apply format'
        await choose(pilot, scr, 'format')
        await pilot.pause()
        p2 = project.load(d)
        assert p2['aspect'] == '1:1' and p2['resolution'] == [1080, 1080]
        status = str(scr.query_one('#status', Static).render())
        assert '1 zone' in status and 'inactive' in status, status
        assert menu.get_option('format').disabled  # applied -> unchanged again


@pytest.mark.asyncio
async def test_apply_format_uhd_outside_16_9_refused(_isolated_config):
    root = _isolated_config
    d = mk(root, 'acme')
    before = open(os.path.join(d, 'project.json')).read()
    app = MenuApp()
    app.project_dir = d
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        scr = app.screen
        scr.query_one('#aspect', Select).value = '9:16'
        scr.query_one('#uhd', Checkbox).value = True
        await pilot.pause()
        await choose(pilot, scr, 'format')
        await pilot.pause()
        assert 'UHD is 16:9 only' in str(scr.query_one('#error', Static).render())
        assert open(os.path.join(d, 'project.json')).read() == before


@pytest.mark.asyncio
async def test_create_from_sample_copies_globe(_isolated_config):
    root = _isolated_config
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        scr = app.screen
        scr.query_one('#name', Input).value = 'demo'
        await choose(pilot, scr, 'sample')
        await pilot.pause()
        d = os.path.join(str(root), 'demo')
        assert os.path.isfile(os.path.join(d, 'transcript.txt'))  # sample content copied
        assert os.path.isfile(os.path.join(d, 'project.json'))
        assert app.project_dir == d
        await choose(pilot, scr, 'sample')
        await pilot.pause()
        assert 'already exists' in str(scr.query_one('#error', Static).render())
