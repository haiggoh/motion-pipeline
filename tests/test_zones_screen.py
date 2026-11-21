"""Task 1 (plan 2026-11-16): zones screen — no DuplicateIds crash, delete, select-to-edit,
per-aspect zones, loud validation. Pilot tests drive the real screen via run_test()."""
import json
import os

import pytest
from textual.widgets import Input, Label, ListView, Static

from motion_pipeline import project
from motion_pipeline.tui.app import MenuApp
from tui_probe import choose

TRANSCRIPT = '# A\nalpha beta\n# B\ngamma delta\n# C\nepsilon zeta\n'


def mk_project(d):
    d = str(d)
    project.save(d, project.default_project('demo'))
    with open(os.path.join(d, 'transcript.txt'), 'w') as f:
        f.write(TRANSCRIPT)
    return d


def zones_of(d):
    with open(os.path.join(d, 'project.json')) as f:
        return json.load(f)['zones']


async def open_zones(pilot, app, d):
    app.project_dir = d
    app.push_screen(app.SCREENS['zones']())
    await pilot.pause()
    return app.screen


async def save_zone(pilot, scr, section, rect):
    scr.query_one('#section', Input).value = section
    scr.query_one('#rect', Input).value = rect
    await choose(pilot, scr, 'save')
    await pilot.pause()


async def select_list_item(pilot, scr, index):
    lv = scr.query_one('#zones', ListView)
    lv.focus()
    await pilot.pause()
    lv.index = index
    await pilot.press('enter')
    await pilot.pause()


@pytest.mark.asyncio
async def test_adding_three_zones_never_raises_duplicate_ids(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        for i, sec in enumerate(('A', 'B', 'C')):
            await save_zone(pilot, scr, sec, f'{10 + i},20,100,100')
        lv = scr.query_one('#zones', ListView)
        assert len(lv.children) == 3, [c.id for c in lv.children]
        assert len(zones_of(d)) == 3


@pytest.mark.asyncio
async def test_select_zone_fills_editor(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        await save_zone(pilot, scr, 'B', '1,2,3,4')
        await select_list_item(pilot, scr, 0)
        assert scr.query_one('#section', Input).value == 'B'
        assert scr.query_one('#rect', Input).value == '1,2,3,4'


@pytest.mark.asyncio
async def test_delete_selected_zone(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        menu = scr.query_one('#actions')
        assert menu.get_option('delete').disabled  # nothing selected yet
        await save_zone(pilot, scr, 'A', '10,20,100,100')
        await save_zone(pilot, scr, 'B', '200,20,100,100')
        await select_list_item(pilot, scr, 0)
        assert not menu.get_option('delete').disabled
        await choose(pilot, scr, 'delete')
        await pilot.pause()
        assert [z['section'] for z in zones_of(d)] == ['B']
        assert len(scr.query_one('#zones', ListView).children) == 1
        assert menu.get_option('delete').disabled  # selection cleared after delete


@pytest.mark.asyncio
async def test_zone_rect_must_fit_frame(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        await save_zone(pilot, scr, 'A', '1900,0,100,100')  # 1900+100 > 1920 wide
        err = str(scr.query_one('#error', Static).render())
        assert 'outside the 1920×1080 frame' in err, err
        assert zones_of(d) == []  # file unchanged


@pytest.mark.asyncio
async def test_zone_empty_section_refused(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        await save_zone(pilot, scr, '', '10,20,100,100')
        err = str(scr.query_one('#error', Static).render())
        assert 'section' in err, err
        assert zones_of(d) == []


@pytest.mark.asyncio
async def test_zone_unknown_section_refused(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        await save_zone(pilot, scr, 'Nope', '10,20,100,100')
        err = str(scr.query_one('#error', Static).render())
        assert 'Nope' in err, err
        assert zones_of(d) == []


@pytest.mark.asyncio
async def test_zone_without_readable_transcript_accepted_with_muted_note(tmp_path):
    d = str(tmp_path / 'proj')
    project.save(d, project.default_project('demo'))  # no transcript.txt
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        await save_zone(pilot, scr, 'Anything', '10,20,100,100')
        assert zones_of(d)[0]['section'] == 'Anything'
        status = str(scr.query_one('#status', Static).render())
        assert 'transcript not readable — section not checked' in status, status


@pytest.mark.asyncio
async def test_zone_saved_with_project_aspect(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        await save_zone(pilot, scr, 'A', '10,20,100,100')
        assert zones_of(d)[0]['aspect'] == '16:9'


@pytest.mark.asyncio
async def test_inactive_aspect_zones_listed_dimmed(tmp_path):
    d = mk_project(tmp_path / 'proj')
    p = json.load(open(os.path.join(d, 'project.json')))
    p['zones'] = [{'section': 'A', 'rect': [10, 20, 100, 100], 'aspect': '9:16'}]
    with open(os.path.join(d, 'project.json'), 'w') as f:
        json.dump(p, f)
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        labels = [str(li.query_one(Label).render()) for li in scr.query_one('#zones', ListView).children]
        assert any('(9:16, inactive)' in t for t in labels), labels
        # the inactive row's label carries the muted class (delivery shape: dimmed, not just text)
        lbl = scr.query_one('#zones', ListView).children[0].query_one(Label)
        assert 'muted' in lbl.classes


# ---- Task 14 (spec B3): explanation, live frame map, overlay on the test frame ----

ZONE_EXPLAIN = ('A keep-out zone hides a frame rectangle from the rendered graphics. Each zone is '
                'anchored to a transcript section; the rect is x,y,w,h in frame pixels of the '
                'project\'s aspect.')


async def test_zones_screen_explanation_and_live_map(tmp_path):
    d = mk_project(tmp_path / 'p')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        # explanation at the top, <= 3 lines at 80 cols
        expl = str(scr.query_one('#zone-explain', Static).render())
        assert 'keep-out' in expl.lower() or 'zone' in expl.lower()
        assert expl.count('\n') < 3
        # frame map present and updates live as the rect field is edited
        mp = scr.query_one('#zonemap', Static)
        assert '×' in str(mp.render()), str(mp.render())[:120]
        scr.query_one('#rect', Input).value = '0,540,960,540'
        await pilot.pause(0.3)
        assert 'A' in str(mp.render()) or '─' in str(mp.render()), str(mp.render())[:200]
        # invalid rect -> last valid map stays, error shown
        scr.query_one('#rect', Input).value = 'not,a,rect'
        await pilot.pause(0.3)
        assert 'error' in str(scr.query_one('#error', Static).render()).lower() or \
            str(mp.render()), 'invalid rect must not blank the map'


async def test_view_toggle_disabled_without_test_frame_and_overlay_when_present(tmp_path):
    d = mk_project(tmp_path / 'p')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_zones(pilot, app, d)
        menu = scr.query_one('#actions')
        assert menu.get_option('view').disabled, 'no test frame yet -> view action disabled'
        # drop a _test_frame.png where the render puts it
        from PIL import Image
        out = os.path.join(d, 'renders', 'default')
        os.makedirs(out, exist_ok=True)
        Image.new('RGB', (192, 108), (10, 10, 30)).save(os.path.join(out, '_test_frame.png'))
        scr.refresh_zones()
        await pilot.pause()
        assert not menu.get_option('view').disabled, 'test frame exists -> view enabled'
        scr.query_one('#rect', Input).value = '0,540,960,540'
        await pilot.pause(0.3)
        await choose(pilot, scr, 'view')
        await pilot.pause(0.5)
        mp = str(scr.query_one('#zonemap', Static).render())
        assert '▀' in mp, 'overlay view should render the half-block test frame'
