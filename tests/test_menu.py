"""Task 5 TUI tests: all screens mount; worker progress + responsiveness + cancellation."""
import pytest
from textual.widgets import Button, RichLog, Static

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
        n = len(app.screen.query_one('#log', RichLog).lines)
        assert any('line' in str(e) for e in app.screen.query_one('#log', RichLog).lines)
        await pilot.pause(1.2)
        assert len(app.screen.query_one('#log', RichLog).lines) <= n + 1


@pytest.mark.asyncio
async def test_graphics_gate_refreshes_on_resume_and_says_why(tmp_path):
    """Task 5 (A5c): the graphics row is re-evaluated when the menu resumes (not only at
    compose), and while disabled its label carries the reason."""
    import os
    from test_timing_gate import mk
    d, p = mk(tmp_path / 'p')          # fresh timings -> gate open
    app = MenuApp()
    app.project_dir = d
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['menu']())
        await pilot.pause()
        menu = app.screen.query_one('#actions')
        opt = menu.get_option('graphics')
        assert not opt.disabled, 'fresh timings must enable the graphics step'
        assert str(opt.prompt) == '6) Add motion graphics', str(opt.prompt)
        # make timings stale, then leave and come back
        with open(os.path.join(d, 'transcript.txt'), 'w') as f:
            f.write('# S\na completely different transcript\n')
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        app.pop_screen()
        await pilot.pause()
        menu = app.screen.query_one('#actions')
        opt = menu.get_option('graphics')
        assert opt.disabled, 'stale timings must disable the graphics step'
        assert 'needs saved timings' in str(opt.prompt), str(opt.prompt)
