"""Hover/highlight like csl (0.5.0 Task 1): soft-blue TEXT on the terminal's own background,
never a filled block. Asserts the COMPUTED style of the live rows — v0.4.x asserted CSS text
and shipped a selector (`.list-item:hover`) that matched nothing."""
import os

from textual.widgets import Label, ListView

from motion_pipeline import font_index
from motion_pipeline.font_index import BUNDLED_DIR
from motion_pipeline.tui.app import MenuApp
from tui_probe import bg_is_default, fg_is_blue

_REAL_SCAN = font_index.scan


def _fast_scan(dirs=None, cache_path=None, progress=None):
    # bundled + /Library/Fonts (enough families for the hover rows); tmp cache keeps it quick
    import tempfile
    return _REAL_SCAN(dirs=[BUNDLED_DIR, '/Library/Fonts'],
                      cache_path=os.path.join(tempfile.mkdtemp(), 'c.json'))


async def test_list_hover_and_highlight_recolour_text_only(tmp_path, monkeypatch):
    monkeypatch.setattr(font_index, 'scan', _fast_scan)  # Task 9: scan runs in a worker now
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['fonts']())
        await pilot.pause()
        scr = app.screen
        for _ in range(200):  # wait for the background scan to fill the list
            await pilot.pause(0.05)
            if len(scr.query_one('#fonts', ListView).children) > 5:
                break
        lv = scr.query_one('#fonts', ListView)
        lv.focus(); lv.index = 0
        await pilot.pause()
        rows = list(lv.children)
        assert len(rows) > 5, 'font list did not fill from the scan'
        await pilot.hover(rows[2]); await pilot.pause()
        hi, hov, plain = rows[0], rows[2], rows[3]
        assert hov.has_class('-hovered') and hi.has_class('-highlight')  # the live classes exist
        for row, name in ((hi, 'highlight'), (hov, 'hover')):
            st = row.query_one(Label).rich_style
            assert bg_is_default(row.rich_style), f'{name} row paints a filled block: {row.rich_style}'
            assert fg_is_blue(st), f'{name} row text is not blue: {st}'
        assert hi.query_one(Label).rich_style.bold
        assert not fg_is_blue(plain.query_one(Label).rich_style)
