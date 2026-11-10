"""0.5.0 Task 4e: the project screen sets the video format — aspect, fps, UHD — for NEW
projects (step 0 create) and for the CURRENT project (Save format), fills the fields on
load, refuses UHD outside 16:9, warns about pixel-coordinate keep-out zones, and Back
writes nothing. Asserts what lands ON DISK and what the user SEES, never source text."""
import json

from textual.widgets import Checkbox, Input, Select, Static

from motion_pipeline import project as project_mod
from motion_pipeline.tui.app import MenuApp
from tui_probe import choose, on_screen


async def _open_project_screen(pilot, app):
    app.push_screen(app.SCREENS['project']())
    await pilot.pause()
    return app.screen


async def test_create_uses_aspect_fps_and_uhd_fields(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_project_screen(pilot, app)
        # defaults, per the README's format list
        assert scr.query_one('#aspect', Select).value == '16:9'
        assert scr.query_one('#fps', Select).value == 60
        assert scr.query_one('#uhd', Checkbox).value is False
        scr.query_one('#name', Input).value = 'vertical'
        scr.query_one('#aspect', Select).value = '9:16'
        scr.query_one('#fps', Select).value = 25
        await pilot.pause()
        await choose(pilot, scr, 'create')
        pj = json.loads((_isolated_config / 'vertical' / 'project.json').read_text())
        assert pj['aspect'] == '9:16'
        assert pj['resolution'] == [1080, 1920]
        assert pj['fps'] == 25


async def test_create_16_9_with_uhd_writes_uhd_resolution(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_project_screen(pilot, app)
        scr.query_one('#name', Input).value = 'big'
        scr.query_one('#uhd', Checkbox).value = True
        await pilot.pause()
        await choose(pilot, scr, 'create')
        pj = json.loads((_isolated_config / 'big' / 'project.json').read_text())
        assert pj['aspect'] == '16:9' and pj['resolution'] == [3840, 2160]


async def test_create_uhd_outside_16_9_errors_and_writes_nothing(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_project_screen(pilot, app)
        scr.query_one('#name', Input).value = 'square'
        scr.query_one('#aspect', Select).value = '1:1'
        scr.query_one('#uhd', Checkbox).value = True
        await pilot.pause()
        await choose(pilot, scr, 'create')
        assert 'UHD' in str(scr.query_one('#error', Static).render())
        assert not (_isolated_config / 'square').exists()  # nothing is written


async def test_load_fills_aspect_fps_uhd_from_project_json(_isolated_config):
    proj = _isolated_config / 'legacy'
    project_mod.save(str(proj), project_mod.default_project('legacy', aspect='4:5', fps=30))
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_project_screen(pilot, app)
        scr.query_one('#dir', Input).value = str(proj)
        await pilot.pause()
        await choose(pilot, scr, 'load')
        assert scr.query_one('#aspect', Select).value == '4:5'
        assert scr.query_one('#fps', Select).value == 30
        assert scr.query_one('#uhd', Checkbox).value is False


async def test_save_format_updates_current_project_and_warns_about_zones(_isolated_config):
    proj = _isolated_config / 'zoned'
    p = project_mod.default_project('zoned')
    p['zones'] = [{'section': 'logo', 'rect': [10, 10, 100, 100]}]
    project_mod.save(str(proj), p)
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_project_screen(pilot, app)
        scr.query_one('#dir', Input).value = str(proj)
        await choose(pilot, scr, 'load')
        scr.query_one('#aspect', Select).value = '9:16'
        scr.query_one('#fps', Select).value = 25
        await pilot.pause()
        await choose(pilot, scr, 'format')
        pj = json.loads((proj / 'project.json').read_text())
        assert pj['aspect'] == '9:16' and pj['resolution'] == [1080, 1920] and pj['fps'] == 25
        assert pj['zones'] == [{'section': 'logo', 'rect': [10, 10, 100, 100]}]
        status = str(scr.query_one('#status', Static).render())
        assert 'zones' in status and 'step 3' in status


async def test_back_writes_nothing_after_editing_format_fields(_isolated_config):
    proj = _isolated_config / 'keep'
    project_mod.save(str(proj), project_mod.default_project('keep'))
    before = (proj / 'project.json').read_bytes()
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_project_screen(pilot, app)
        scr.query_one('#dir', Input).value = str(proj)
        await choose(pilot, scr, 'load')
        scr.query_one('#aspect', Select).value = '9:16'
        scr.query_one('#fps', Select).value = 25
        scr.query_one('#uhd', Checkbox).value = True
        await pilot.pause()
        await choose(pilot, scr, 'back')
    assert (proj / 'project.json').read_bytes() == before


async def test_every_format_field_on_screen_at_80x24():
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_project_screen(pilot, app)
        for wid in ('#aspect', '#fps', '#uhd'):
            assert on_screen(app, scr.query_one(wid)), f'{wid} off-screen at 80x24'
        for w in scr.query(Input):
            assert on_screen(app, w), f'{w!r} off-screen at 80x24'
        assert on_screen(app, scr.query_one('#actions'))
        assert on_screen(app, scr.query_one('.hint'))
