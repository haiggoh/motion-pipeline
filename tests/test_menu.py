"""Task 5 TUI tests: all screens mount; worker progress + responsiveness + cancellation."""
import pytest
from textual.widgets import Button, Log, Static

from tui_probe import choose
from motion_pipeline.tui.app import MenuApp, STEPS


@pytest.mark.asyncio
async def test_all_menu_screens_mount():
    app = MenuApp()
    async with app.run_test() as pilot:
        for key, _ in STEPS:
            screen = app.SCREENS[key]()
            app.push_screen(screen)
            await pilot.pause()
            assert app.screen is screen, key
            app.pop_screen()
            await pilot.pause()


@pytest.mark.asyncio
async def test_worker_streams_progress_and_stays_responsive_and_cancellable(tmp_path):
    """Cancel must STOP the render process (v0.1-0.4: worker.cancel() on a thread worker left
    the subprocess running), not just stop the log."""
    import asyncio
    import os
    pidfile = tmp_path / 'pid'
    cmd = ['bash', '-c', f'echo $$ > {pidfile}; for i in $(seq 1 40); do echo line$i; sleep 0.1; done']
    app = MenuApp(test_render_cmd=cmd)
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['bgtest']())
        await pilot.pause()
        await choose(pilot, app.screen, 'run')
        for _ in range(30):
            await pilot.pause(0.05)
            if pidfile.exists() and pidfile.read_text().strip():
                break
        pid = int(pidfile.read_text())
        await pilot.pause(0.3)
        assert app.screen.query_one('#status', Static) is not None   # responsive meanwhile
        await choose(pilot, app.screen, 'cancel')
        await pilot.pause(0.5)
        status = str(app.screen.query_one('#status', Static).render())
        assert 'cancel' in status, status
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)                                       # the process is gone (and reaped)
        n = len(app.screen.query_one('#log', Log).lines)
        assert any('line' in str(e) for e in app.screen.query_one('#log', Log).lines)
        await pilot.pause(1.2)
        assert len(app.screen.query_one('#log', Log).lines) <= n + 1
