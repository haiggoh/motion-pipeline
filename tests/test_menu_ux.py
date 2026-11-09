"""UX requests 2026-11-09: csl-style terminal-native theme + back-without-saving on every submenu."""
import pytest
from textual.widgets import Input

from motion_pipeline.tui.app import MenuApp, STEPS
from motion_pipeline.tui.base import CSL_CSS, SubmenuScreen


def test_csl_style_no_painted_background_and_round_panels():
    # the terminal's own background shows through: every surface is ansi_default
    assert 'background: ansi_default' in CSL_CSS
    assert 'background: $surface' not in CSL_CSS and 'background: grey' not in CSL_CSS.lower()
    # csl's rounded text panel borders
    assert 'border: round ansi_bright_black' in CSL_CSS
    assert '.panel' in CSL_CSS
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
async def test_menu_screens_have_panel():
    app = MenuApp()
    async with app.run_test() as pilot:
        for _, key in STEPS:
            app.push_screen(app.SCREENS[key]())
            await pilot.pause()
            assert app.screen.query('.panel'), f'{key} has no .panel'
            app.pop_screen()
            await pilot.pause()
