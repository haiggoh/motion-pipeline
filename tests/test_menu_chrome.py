"""Task 4 (plan 2026-11-16): nav row spacing + labels, dimmed/red feedback lines, root hint,
show_path helper. Pilot tests drive real screens."""
import os

import pytest
from textual.color import Color
from textual.widgets import Static

from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.base import show_path


@pytest.mark.asyncio
async def test_nav_row_preceded_by_a_blank_row():
    # D8 allows 1-2 blank rows; 1 is used because 2 push the action rows off-screen at 80x24
    # on the inputs/project screens (ledgered ruling). Discriminant: nav_gap=0 -> RED.
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = app.screen  # launch screen (root entry)
        menu = scr.query_one('#actions')
        ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
        nav = ids.index('home')
        assert ids[nav - 1].startswith('_navgap'), ids
        opt = menu.get_option_at_index(nav - 1)
        assert opt.disabled and str(opt.prompt).strip() == '', opt.prompt
        assert not ids[nav - 2].startswith('_navgap'), ids
        # a submenu pushed on top: same blank row before 'back'
        app.push_screen(app.SCREENS['zones']())
        await pilot.pause()
        menu = app.screen.query_one('#actions')
        ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
        nav = ids.index('back')
        assert ids[nav - 1].startswith('_navgap'), ids


@pytest.mark.asyncio
async def test_nav_labels():
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        menu = app.screen.query_one('#actions')
        last = menu.get_option_at_index(menu.option_count - 1)
        assert last.id == 'home' and str(last.prompt) == 'Continue to main menu', (last.id, last.prompt)
        app.push_screen(app.SCREENS['zones']())
        await pilot.pause()
        menu = app.screen.query_one('#actions')
        last = menu.get_option_at_index(menu.option_count - 1)
        assert last.id == 'back' and str(last.prompt) == 'Back to main menu', (last.id, last.prompt)


@pytest.mark.asyncio
async def test_feedback_dimmed_and_spaced():
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.push_screen(app.SCREENS['zones']())
        await pilot.pause()
        st = app.screen.query_one('#status', Static)
        assert st.has_class('feedback')
        assert st.styles.color == Color.parse('ansi_bright_black'), st.styles.color
        assert st.styles.margin.top == 1


@pytest.mark.asyncio
async def test_error_feedback_red():
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.push_screen(app.SCREENS['zones']())
        await pilot.pause()
        err = app.screen.query_one('#error', Static)
        assert err.has_class('feedback-error')
        assert err.styles.color == Color.parse('ansi_red'), err.styles.color
        assert err.styles.margin.top == 0  # the one empty row goes before the block, not per line


@pytest.mark.asyncio
async def test_root_launch_hint_has_no_back():
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        hint = str(app.screen.query_one('.hint', Static).render())
        assert 'b/esc back' not in hint, hint
        app.push_screen(app.SCREENS['zones']())
        await pilot.pause()
        hint = str(app.screen.query_one('.hint', Static).render())
        assert 'b/esc back' in hint, hint  # submenus DO show back


def test_show_path_abbreviates_home():
    assert show_path(os.path.expanduser('~/x/y')) == '~/x/y'
    assert show_path('/opt/other') == '/opt/other'
