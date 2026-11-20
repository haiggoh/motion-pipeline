"""Task 2 (spec A3): the job log (RichLog#log) must not paint a background —
no grey block on the background-test and render screens. csl look: ansi_default
everywhere, and :focus must not add a tint (RichLog's own DEFAULT_CSS ships
`background: $surface` + `&:focus { background-tint: $foreground 5% }`, which the
csl CSS did not override because it only styled `Log`).
"""
import pytest
from textual.widgets import RichLog

from motion_pipeline.tui.app import MenuApp


def _is_ansi_default(color) -> bool:
    # textual Color: ansi == -1 marks the terminal default colour
    return color is not None and color.ansi == -1


@pytest.mark.asyncio
async def test_joblog_has_no_painted_background_or_focus_tint(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        for key in ('bgtest', 'render'):
            app.push_screen(app.SCREENS[key]())
            await pilot.pause()
            log = app.screen.query_one('#log', RichLog)
            bg = log.styles.background
            assert _is_ansi_default(bg), f'{key}: RichLog paints background {bg!r}'
            log.focus()
            await pilot.pause()
            bg = log.styles.background
            assert _is_ansi_default(bg), f'{key} :focus paints background {bg!r}'
            tint = log.styles.background_tint
            # ansi_default tint is a no-op even at alpha 1.0: Color.tint(ansi_default)
            # returns the terminal default (verified: blend -> Color(0,0,0,ansi=-1)),
            # and textual drops the 0% on ANSI colours — so assert the colour, not alpha.
            assert tint is not None and tint.ansi == -1, \
                f'{key} :focus paints a tint {tint!r}'
            app.pop_screen()
            await pilot.pause()
