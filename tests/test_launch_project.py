"""0.5.2 UX (user 2026-11-10 12:44 CET): every setting depends on a saved project, so the
app always LAUNCHES in New / load project (never Home). On that launch screen the trailing
nav row is disabled until a project is saved (create/load sets the format in the SAME step —
there is no separate 'Save format' action anymore) and is labelled 'Home', not 'Back', because
we did not come from Home. Entered from Home later, the row is 'Back' again and pops."""
import json

from textual.widgets import Input

from motion_pipeline.tui.app import MenuApp, MenuScreen
from motion_pipeline.tui.project_screen import ProjectScreen
from tui_probe import choose


def _nav_row(scr):
    menu = scr.query_one('#actions')
    last = menu.get_option_at_index(menu.option_count - 1)
    return menu, last


async def test_launch_lands_on_project_screen_not_home(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen), type(app.screen).__name__
        assert len(app.screen_stack) == 2, len(app.screen_stack)  # nothing sits behind the launch screen (QC 2026-11-10)
        menu, last = _nav_row(app.screen)
        assert last.id == 'home' and str(last.prompt) == 'Home', (last.id, last.prompt)
        assert menu.get_option('home').disabled, 'nav row must be disabled until a project is saved'
        ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
        assert ids == ['create', 'load', 'root', 'home'], ids  # no separate 'format' action


async def test_nav_row_enables_after_create_and_home_reaches_menu(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = app.screen
        assert isinstance(scr, ProjectScreen)
        menu, last = _nav_row(scr)
        assert last.id == 'home' and menu.get_option('home').disabled
        scr.query_one('#name', Input).value = 'acme'
        scr.query_one('#aspect').value = '9:16'   # format set in the SAME step as create
        await pilot.pause()
        await choose(pilot, scr, 'create')
        pj = json.loads((_isolated_config / 'acme' / 'project.json').read_text())
        assert pj['aspect'] == '9:16' and pj['resolution'] == [1080, 1920]  # same step, on disk
        menu, last = _nav_row(scr)
        assert last.id == 'home' and not menu.get_option('home').disabled, (last.id, last.prompt)
        await choose(pilot, scr, 'home')
        assert isinstance(app.screen, MenuScreen), type(app.screen).__name__


async def test_nav_row_enables_after_load_too(_isolated_config):
    # QC 2026-11-10: on_action enables the nav row after create AND load — only create was
    # covered. Mutation: enabling inside the create branch only must turn this RED.
    from motion_pipeline import project as project_mod
    pdir = _isolated_config / 'acme'
    pdir.mkdir()
    project_mod.save(str(pdir), project_mod.default_project('acme'))
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = app.screen
        assert isinstance(scr, ProjectScreen)
        menu, last = _nav_row(scr)
        assert last.id == 'home' and menu.get_option('home').disabled
        scr.query_one('#name', Input).value = 'acme'
        await pilot.pause()
        await choose(pilot, scr, 'load')
        assert app.project_dir == str(pdir), app.project_dir
        menu, last = _nav_row(scr)
        assert last.id == 'home' and not menu.get_option('home').disabled, (
            last.id, menu.get_option('home').disabled)


async def test_from_home_trailing_row_is_back_and_pops(_isolated_config, tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)  # a saved project already exists
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)  # launched into step 0
        # QC 2026-11-10: reach Home via the launch screen's own 'Home' row, then re-enter step 0
        # through the HOME MENU's wiring (choose 'project') — not push_screen directly.
        # Mutation: the menu wiring setting root_entry=True on the pushed screen -> RED here.
        await choose(pilot, app.screen, 'home')
        await pilot.pause()
        assert isinstance(app.screen, MenuScreen), type(app.screen).__name__
        await choose(pilot, app.screen, 'project')
        await pilot.pause()
        scr = app.screen
        assert isinstance(scr, ProjectScreen)
        menu, last = _nav_row(scr)
        assert last.id == 'back' and str(last.prompt) == 'Back', (last.id, last.prompt)
        assert not menu.get_option('back').disabled  # came from home: Back works
        await choose(pilot, scr, 'back')
        assert isinstance(app.screen, MenuScreen), type(app.screen).__name__


async def test_back_key_does_not_pop_the_launch_screen(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)
        await pilot.press('b')   # nothing behind the launch screen
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen), type(app.screen).__name__
        # QC 2026-11-10: esc routes through SubmenuScreen.action_back (base.py) — a SEPARATE
        # root_entry guard from the 'b' priority binding. Mutation: dropping that guard in
        # SubmenuScreen.action_back only -> esc pops here, RED.
        await pilot.press('escape')
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen), type(app.screen).__name__
        assert len(app.screen_stack) == 2, len(app.screen_stack)
