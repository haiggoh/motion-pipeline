"""0.8.1 spec (2026-11-23-ux-fixes-spec.md) UI assertions:
- voiceover label names the accepted file types (not bare "(optional)")
- aligner defaults to the whisper-with-fallback entry and "classical" got a descriptive label
- the graphics screen's "Start free AI session" button carries a ROUND border like the
  dropdowns (computed style, not CSS text)
- the free-session effort default is 'max'
"""
import pytest
from projfix import make_project

from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.paths import VO_EXTS


@pytest.mark.asyncio
async def test_inputs_screen_vo_label_names_file_types_and_aligner_default(tmp_path):
    from motion_pipeline.tui.app import InputsScreen
    pd = make_project(str(tmp_path / 'proj'))
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = InputsScreen()
        app.push_screen(scr)
        await pilot.pause()
        from textual.widgets import Label, Select
        labels = [str(lab.render()) for lab in scr.query(Label)]
        vo_label = next(x for x in labels if 'voiceover' in x)
        assert 'optional' not in vo_label, vo_label
        for ext in ('.wav', '.ogg', '.mp4'):
            assert ext in vo_label, (ext, vo_label)
        assert all(e in vo_label for e in VO_EXTS), vo_label
        al = scr.query_one('#aligner', Select)
        assert al.value == 'auto', al.value                       # whisper-with-fallback default
        labels_txt = ' '.join(str(p) for p, _v in al._options)
        assert 'Whisper' in labels_txt and 'lassical' not in labels_txt, labels_txt


@pytest.mark.asyncio
async def test_graphics_launch_button_rounded_like_dropdowns_and_max_effort_default(tmp_path):
    from motion_pipeline.tui.graphics_screen import GraphicsScreen
    pd = make_project(str(tmp_path / 'proj'))
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = GraphicsScreen()
        app.push_screen(scr)
        await pilot.pause()
        if not scr.query('#fa-launch'):
            pytest.skip('free-agents not detected in this env')
        from textual.widgets import Button, Select
        from textual.widgets._select import SelectCurrent
        btn = scr.query_one('#fa-launch', Button)
        assert btn.styles.border_top[0] == 'round', btn.styles.border_top
        sel = scr.query_one('#fa-model', Select)
        assert sel.query_one(SelectCurrent).styles.border_top[0] == 'round'  # dropdown reference frame
        eff = scr.query_one('#fa-effort', Select)
        assert eff.value == 'max', eff.value
