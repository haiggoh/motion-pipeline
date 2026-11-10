"""Weight dropdowns in the rounded-field design (0.5.0 Task 3): ONE round frame on the visible
field (SelectCurrent), none on the Select wrapper (v0.4.x drew two), round + default-background
overlay when expanded, all on-screen at 80x24."""
from textual.widgets import Select
from textual.widgets._select import SelectCurrent, SelectOverlay

from motion_pipeline import fonts as fonts_mod
from motion_pipeline.tui.app import MenuApp
from tui_probe import bg_is_default, on_screen


async def test_weight_selects_have_one_round_frame_and_rounded_overlay(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['fonts']()); await pilot.pause(0.5)
        scr = app.screen
        for role in fonts_mod.ROLES:
            sel = scr.query_one(f'#role-{role}', Select)
            cur = sel.query_one(SelectCurrent)
            assert sel.styles.border_top[0] in ('', 'none'), f'{role}: wrapper has a frame {sel.styles.border_top}'
            assert cur.styles.border_top[0] == 'round', f'{role}: field frame {cur.styles.border_top}'
            assert bg_is_default(cur.rich_style), f'{role}: field filled {cur.rich_style}'
            assert on_screen(app, sel), f'{role} weight field off-screen at 80x24: {sel.region}'
        sel = scr.query_one('#role-headline', Select)
        sel.focus(); await pilot.pause()
        fb = sel.query_one(SelectCurrent).styles.border_top
        assert fb[0] == 'round' and fb[1].ansi == 12, f'focused field frame not bright-blue: {fb}'
        sel.expanded = True; await pilot.pause()
        ov = sel.query_one(SelectOverlay)
        assert ov.styles.border_top[0] == 'round' and bg_is_default(ov.rich_style), (ov.styles.border_top, ov.rich_style)
