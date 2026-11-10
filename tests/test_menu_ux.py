"""UX requests 2026-11-09: csl-style terminal-native theme + back-without-saving on every submenu."""
import os

import pytest
from textual.widgets import Input

from motion_pipeline.tui.app import MenuApp, MenuScreen, STEPS
from tui_probe import bg_is_default, choose, on_screen
from motion_pipeline.tui.base import CSL_CSS, SubmenuScreen


async def test_csl_style_no_painted_background_and_round_text_fields(tmp_path):
    """Delivered, not declared: the live screen and an Input compute to the terminal's own
    background, and text fields carry ONE round frame (dropdowns: test_select_rounded.py)."""
    app = MenuApp()
    assert app.ansi_color is True
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert bg_is_default(app.screen.rich_style)
        app.push_screen(app.SCREENS['project']()); await pilot.pause()
        inp = app.screen.query_one('#name', Input)
        assert inp.styles.border_top[0] == 'round' and bg_is_default(inp.rich_style)
        panel = app.screen.query_one('.panel')
        assert panel.styles.border_top[0] in ('', 'none')  # the window itself is not framed


@pytest.mark.asyncio
async def test_every_submenu_back_is_last_row_and_pops_without_saving(tmp_path, monkeypatch):
    app = MenuApp()
    app.project_dir = str(tmp_path / 'proj')
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        for key, _ in STEPS:
            app.push_screen(app.SCREENS[key]())
            await pilot.pause()
            scr = app.screen
            assert isinstance(scr, SubmenuScreen), key
            menu = scr.query_one('#actions')
            last = menu.get_option_at_index(menu.option_count - 1)
            assert last.id == 'back' and str(last.prompt) == 'Back', (key, last.prompt)
            assert on_screen(app, menu), f'{key}: action rows not fully on-screen at 80x24'
            assert menu.max_scroll_y == 0, f'{key}: action rows scroll, Back hidden'
            assert on_screen(app, scr.query_one('.hint')), f'{key}: key hint pushed off-screen at 80x24'
            if key == 'colours':
                scr.query_one('#accent', Input).value = '#123456'   # typed, not saved
            await choose(pilot, scr, 'back')
            assert app.screen is not scr, key  # Back popped the submenu (the launch screen may itself be a SubmenuScreen)
        assert not (tmp_path / 'proj').exists()  # Back wrote nothing


@pytest.mark.asyncio
async def test_main_menu_is_csl_style_quit_last_no_back():
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.push_screen(MenuScreen())  # the app launches in step 0 now; Home is reached from there
        await pilot.pause()
        scr = app.screen
        assert isinstance(scr, MenuScreen) and not isinstance(scr, SubmenuScreen)
        menu = scr.query_one('#actions')
        ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
        assert 'back' not in ids
        last = menu.get_option_at_index(menu.option_count - 1)
        assert last.id == 'quit' and str(last.prompt) == 'Quit'
        prompts = [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]
        assert prompts[0] == '0) New / load project' and '6) Render' in prompts
        # a blank row between EVERY pair of real rows
        for i in range(1, menu.option_count, 2):
            assert prompts[i].strip() == '' and menu.get_option_at_index(i).disabled, prompts
        assert on_screen(app, menu)
        assert menu.max_scroll_y == 0, 'main menu scrolls: the last rows (Quit) are hidden'
        # `b` on the main menu must not pop it (v0.4.x left an empty screen)
        await pilot.press('b'); await pilot.pause()
        assert isinstance(app.screen, MenuScreen)
        # digit selects a step; Back returns
        await pilot.press('2'); await pilot.pause(0.3)
        assert type(app.screen).__name__ == 'FontsScreen'
        await pilot.press('escape'); await pilot.pause()
        assert isinstance(app.screen, MenuScreen)


@pytest.mark.asyncio
async def test_digit_runs_submenu_action_but_types_into_a_focused_field(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(app.SCREENS['project']()); await pilot.pause()
        scr = app.screen
        name = scr.query_one('#name', Input)
        scr.query_one('#dir', Input).value = str(tmp_path / 'p1')  # never the cwd
        name.focus(); await pilot.press('1'); await pilot.pause()
        assert name.value == '1' and isinstance(app.screen, type(scr))   # typed, not an action
        scr.query_one('#actions').focus(); await pilot.pause()
        await pilot.press('1'); await pilot.pause()                       # 1) Create new project
        assert 'created' in str(scr.query_one('#status').render())
        assert (tmp_path / 'p1' / 'project.json').is_file()


@pytest.mark.asyncio
async def test_colours_swatches_and_hsl_fields_are_on_screen(tmp_path):
    """Visual regression guard: at a normal terminal size (100x30) every swatch, hex and
    H/S/L field must be inside the visible region — the v0.4.0 bug had them at x>100."""
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        from motion_pipeline import scheme as scheme_mod
        for key in scheme_mod.INPUT_KEYS[1:]:
            for wid in (f'#swatch-{key}', f'#{key}', f'#h-{key}', f'#s-{key}', f'#l-{key}'):
                w = scr.query_one(wid)
                r = w.region
                assert r.x + r.width <= scr.size.width and r.x >= 0, \
                    f'{wid} off-screen: region={r} screen={scr.size}'
        # and the swatch actually gets the colour on typing
        from textual.widgets import Input, Static
        scr.query_one('#background_dark', Input).value = '#ff0000'
        await pilot.pause()
        assert '255, 0, 0' in str(scr.query_one('#swatch-background_dark', Static).styles.background)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_brew_launcher_runs_menu_and_fonts_without_crash(tmp_path):
    """Simulate the Homebrew launcher: PYTHONPATH=libexec + a venv holding ONLY the
    pyproject deps (the v0.4.0 font-menu crash was PIL missing from that venv)."""
    import subprocess
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv = tmp_path / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
    subprocess.run([str(venv / 'bin' / 'pip'), 'install', '--quiet',
                    'textual>=0.80', 'numpy>=1.26', 'pillow>=10'], check=True, timeout=300)
    code = (
        "import asyncio\n"
        "from motion_pipeline.tui.app import MenuApp\n"
        "async def go():\n"
        "    app = MenuApp()\n"
        "    async with app.run_test() as pilot:\n"
        "        await pilot.pause()\n"
        "        app.push_screen(app.SCREENS['fonts']())\n"
        "        await pilot.pause()\n"
        "        lv = app.screen.query_one('#fonts')\n"
        "        print('FONTS_OK', len(lv.children) > 20)\n"
        "asyncio.run(go())\n"
    )
    env = dict(os.environ, PYTHONPATH=root)
    r = subprocess.run([str(venv / 'bin' / 'python'), '-c', code],
                       capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stderr[-800:]
    assert 'FONTS_OK True' in r.stdout, r.stdout


@pytest.mark.asyncio
async def test_step_zero_is_project_create_or_load():
    app = MenuApp()
    async with app.run_test() as pilot:
        assert STEPS[0][0] == 'project', STEPS[0]
        app.push_screen(app.SCREENS['project']())
        await pilot.pause()
        scr = app.screen
        assert scr.query_one('#name', Input) and scr.query_one('#dir', Input)
        menu = scr.query_one('#actions')
        assert [menu.get_option_at_index(i).id for i in range(menu.option_count)] == ['create', 'load', 'root', 'back']
