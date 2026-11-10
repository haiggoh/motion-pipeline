"""Hover/highlight like csl (0.5.0 Task 1): soft-blue TEXT on the terminal's own background,
never a filled block. Asserts the COMPUTED style of the live rows — v0.4.x asserted CSS text
and shipped a selector (`.list-item:hover`) that matched nothing."""
from textual.widgets import Label, ListView

from motion_pipeline.tui.app import MenuApp
from tui_probe import bg_is_default, fg_is_blue


async def test_list_hover_and_highlight_recolour_text_only(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['fonts']())
        await pilot.pause(0.5)
        lv = app.screen.query_one('#fonts', ListView)
        lv.focus(); lv.index = 0
        await pilot.pause()
        rows = list(lv.children)
        await pilot.hover(rows[2]); await pilot.pause()
        hi, hov, plain = rows[0], rows[2], rows[3]
        assert hov.has_class('-hovered') and hi.has_class('-highlight')  # the live classes exist
        for row, name in ((hi, 'highlight'), (hov, 'hover')):
            st = row.query_one(Label).rich_style
            assert bg_is_default(row.rich_style), f'{name} row paints a filled block: {row.rich_style}'
            assert fg_is_blue(st), f'{name} row text is not blue: {st}'
        assert hi.query_one(Label).rich_style.bold
        assert not fg_is_blue(plain.query_one(Label).rich_style)
