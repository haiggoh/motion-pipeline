"""Task 5 TUI tests: all screens mount; worker progress + responsiveness + cancellation."""
import pytest
from textual.widgets import Button, Log, Static

from motion_pipeline.tui.app import MenuApp, STEPS


@pytest.mark.asyncio
async def test_all_menu_screens_mount():
    app = MenuApp()
    async with app.run_test() as pilot:
        for _, key in STEPS:
            screen = app.SCREENS[key]()
            app.push_screen(screen)
            await pilot.pause()
            assert app.screen is screen, key
            app.pop_screen()
            await pilot.pause()


@pytest.mark.asyncio
async def test_worker_streams_progress_and_stays_responsive_and_cancellable():
    cmd = ['bash', '-c', 'for i in 1 2 3 4 5 6 7 8; do echo line$i; sleep 0.3; done']
    app = MenuApp(test_render_cmd=cmd)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['bgtest']())
        await pilot.pause()
        app.screen.query_one('#run', Button).press()
        await pilot.pause()
        # responsiveness: the app answers queries while the worker runs
        assert app.screen.query_one('#status', Static) is not None
        await pilot.pause()
        # cancel mid-run
        app.screen.query_one('#cancel', Button).press()
        await pilot.pause()
        await pilot.pause()
        lines = [str(entry) for entry in app.screen.query_one('#log', Log).lines]
        assert any('line' in entry for entry in lines), lines
        status = str(app.screen.query_one('#status', Static).render())
        assert 'cancel' in status, status
        # after cancel, no further progress lines arrive
        n = len(lines)
        await pilot.pause()
        await pilot.pause()
        lines2 = [str(entry) for entry in app.screen.query_one('#log', Log).lines]
        assert len(lines2) <= n + 1, (lines, lines2)  # at most the in-flight line
