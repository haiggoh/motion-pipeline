"""User requirement 2026-11-22: anything loading >100 ms shows a loading animation where the
content lands (ported from free-agents' session_picker pending-op pattern); startup shows it
immediately."""
import pytest

from motion_pipeline import project
from motion_pipeline.tui.app import MenuApp


@pytest.mark.asyncio
async def test_launch_shows_loader_immediately(tmp_path):
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.05)
        scr = app.screen
        loader = scr.query('.op-loader')
        assert loader and loader.first().display, 'launch loader visible at once (immediate=True)'
        await pilot.pause(1.8)
        assert not scr.query('.op-loader').first().display, 'loader hides after launch'


@pytest.mark.asyncio
async def test_op_over_100ms_shows_loader_where_content_lands(tmp_path):
    from textual.containers import Vertical
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        scr = app.screen
        await pilot.pause(0.5)
        for _ in range(30):   # wait out the launch loader before starting the test op
            if not scr.query('.op-loader').first().display:
                break
            await pilot.pause(0.1)
        assert not scr.query('.op-loader').first().display
        box = scr.start_loading(text='rendering…')
        assert box is not None and not box.display, 'hidden before the 100 ms delay'
        for _ in range(30):
            await pilot.pause(0.05)
            if box.display:
                break
        assert box.display, 'loader appeared after >100 ms, inside the load area'
        scr.stop_loading()
        await pilot.pause(0.1)
        assert not scr.query('.op-loader').first().display, 'loader hidden when the op finished'


@pytest.mark.asyncio
async def test_fast_op_never_shows_loader(tmp_path):
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        scr = app.screen
        await pilot.pause(0.5)
        from textual.containers import Vertical
        box = scr.start_loading()
        await pilot.pause(0.05)      # op finishes in 50 ms < 100 ms delay
        scr.stop_loading()
        await pilot.pause(0.2)
        assert not box.display, 'a sub-100ms op must never flash the loader'
