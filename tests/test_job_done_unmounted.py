"""B2 (0.8.0 plan): jobs.run_command runs on an APP worker (tui/jobs.py:32), so on_finish
outlives the screen. 0.7.1 guarded _on_timing_done; the render callbacks and the fonts scan
callback were still unguarded — NoMatches on the removed screen (same crash class the user
hit via step 6 mid-job). Modelled on tests/test_timing_done_unmounted.py. RED pre-fix."""
import pytest

from motion_pipeline.tui.app import MenuApp


@pytest.mark.asyncio
async def test_render_callbacks_on_removed_screen_do_not_crash(tmp_path):
    a = MenuApp()
    a.project_dir = str(tmp_path)
    async with a.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = a.SCREENS['render']()
        a.push_screen(scr)
        await pilot.pause()
        a.pop_screen()
        await pilot.pause()
        await scr.remove()
        await pilot.pause()
        scr._on_setup_done(0)          # NoMatches pre-fix (and B1's NameError)
        scr._on_check_done(0)
        scr.on_render_done(0)


@pytest.mark.asyncio
async def test_bgtest_render_done_on_removed_screen_does_not_crash(tmp_path):
    a = MenuApp()
    a.project_dir = str(tmp_path)
    async with a.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = a.SCREENS['bgtest']()
        a.push_screen(scr)
        await pilot.pause()
        a.pop_screen()
        await pilot.pause()
        await scr.remove()
        await pilot.pause()
        scr.on_render_done(0)          # NoMatches '#image' pre-fix


@pytest.mark.asyncio
async def test_fonts_scan_done_on_removed_screen_does_not_crash(tmp_path):
    a = MenuApp()
    a.project_dir = str(tmp_path)
    async with a.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = a.SCREENS['fonts']()
        a.push_screen(scr)
        await pilot.pause()
        a.pop_screen()
        await pilot.pause()
        await scr.remove()
        await pilot.pause()
        scr._on_scan_done([])          # NoMatches '#font-search' pre-fix (thread callback)
