"""Bugfix (user report 2026-11-21, motion-pipeline-dev @ fd8e580): entering '6) Add motion
graphics' while the timings job runs pops the InputsScreen; when the job then finishes,
_on_timing_done ran on the unmounted screen and crashed with NoMatches '#timing-spinner'."""
import pytest
from test_inputs_screen import mk_project, open_inputs, save

from motion_pipeline.tui.app import MenuApp


@pytest.mark.asyncio
async def test_timing_done_on_popped_screen_does_not_crash(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp(test_prepare_cmd=['bash', '-c', 'sleep 5; exit 2'])
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        await save(pilot, scr)
        await pilot.pause(0.3)
        app.pop_screen()                       # user went Back to the menu mid-job
        await pilot.pause(0.3)
        await scr.remove()                     # the screen leaves the DOM (as in the user's crash)
        await pilot.pause(0.2)
        # the job finishes late — on_finish fires on the removed screen (user's crash:
        # NoMatches '#timing-spinner' when entering step 6 mid-job). Must not raise.
        scr._on_timing_done(2)                 # raises NoMatches pre-fix -> test goes RED
