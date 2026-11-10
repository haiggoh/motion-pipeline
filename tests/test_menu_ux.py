"""UX requests 2026-11-09: csl-style terminal-native theme + back-without-saving on every submenu."""
import os

import pytest
from textual.widgets import Input

from motion_pipeline.tui.app import MenuApp, STEPS
from motion_pipeline.tui.base import CSL_CSS, SubmenuScreen


def test_csl_style_no_painted_background_and_round_panels():
    # the terminal's own background shows through: every surface is ansi_default
    assert 'background: ansi_default' in CSL_CSS
    assert 'background: $surface' not in CSL_CSS and 'background: grey' not in CSL_CSS.lower()
    # rounded frames on the TEXT FIELDS (inputs + dropdown selects), not the window
    assert 'Input, Select' in CSL_CSS and 'border: round ansi_bright_black' in CSL_CSS
    assert '.panel {' in CSL_CSS and 'border' not in CSL_CSS.split('.panel {')[1].split('}')[0]
    # hover/highlight: proven by COMPUTED style in tests/test_hover_csl.py (the CSS-text
    # assertion that used to live here passed on a selector that matched nothing)
    # home menu: one empty line between items
    assert '#menu-list > ListItem { margin: 0 0 1 0; }' in CSL_CSS
    app = MenuApp()
    assert app.ansi_color is True
    assert 'ansi_default' in app.CSS


@pytest.mark.asyncio
async def test_every_submenu_has_back_binding_and_pops_without_saving(tmp_path, monkeypatch):
    monkeypatch.setattr('motion_pipeline.tui.colours_screen.PROJECTS', str(tmp_path))
    monkeypatch.setattr('motion_pipeline.tui.fonts_screen.PROJECTS', str(tmp_path))
    app = MenuApp()
    async with app.run_test() as pilot:
        for _, key in STEPS:
            screen = app.SCREENS[key]()
            assert isinstance(screen, SubmenuScreen), key
            assert any(b.key == 'b' for b in screen.BINDINGS), key
            app.push_screen(screen)
            await pilot.pause()
            # type something but DON'T save, then use the visible Back action
            if key == 'colours':
                app.screen.query_one('#name', Input).value = 'should-not-save'
            await pilot.pause()
            from textual.widgets import Button
            assert app.screen.query('#back'), f'{key} has no back button'
            app.screen.query_one('#back', Button).press()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, type(app.SCREENS['menu']())), key
        # nothing was saved by going back
        assert not (tmp_path / 'should-not-save').exists()


@pytest.mark.asyncio
async def test_menu_screens_have_panel_and_visible_back_button():
    app = MenuApp()
    async with app.run_test() as pilot:
        for _, key in STEPS:
            app.push_screen(app.SCREENS[key]())
            await pilot.pause()
            assert app.screen.query('.panel'), f'{key} has no .panel'
            # the back button lives INSIDE the panel (top), so it is visible without scrolling
            panel = app.screen.query_one('.panel')
            back = app.screen.query_one('#back')
            assert back in panel.children, f'{key}: back button not inside the panel'
            app.pop_screen()
            await pilot.pause()


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
        assert STEPS[0][1] == 'project', STEPS[0]
        app.push_screen(app.SCREENS['project']())
        await pilot.pause()
        scr = app.screen
        from textual.widgets import Button, Input
        assert scr.query_one('#name', Input) and scr.query_one('#dir', Input)
        assert scr.query_one('#create', Button) and scr.query_one('#load', Button)
