"""UX requests 2026-11-09: csl-style terminal-native theme + back-without-saving on every submenu."""
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
    # hover works like csl: soft-blue text on hover and on highlight, never a filled block
    assert 'ListItem:hover' in CSL_CSS and 'ansi_bright_blue' in CSL_CSS
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
