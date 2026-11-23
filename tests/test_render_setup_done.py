"""B1 (0.8.0 plan): RenderScreen._on_setup_done used RichLog with no import in that method
(ruff F821 — every sibling method imports it locally). After 'Install render toolchain'
exits 0, the follow-up --check crashed with NameError instead of running. RED pre-fix."""
import pytest

from motion_pipeline.tui import app as app_mod
from motion_pipeline.tui.app import MenuApp


@pytest.mark.asyncio
async def test_setup_success_starts_check(tmp_path, monkeypatch):
    recorded = {}

    def fake_run_command(app, cmd, log, on_finish=None):
        recorded['cmd'] = list(cmd)
        return None

    monkeypatch.setattr(app_mod, 'run_command', fake_run_command)
    a = MenuApp()
    a.project_dir = str(tmp_path)
    async with a.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = app_mod.RenderScreen()
        a.push_screen(scr)
        await pilot.pause()
        scr._on_setup_done(0)          # NameError: RichLog pre-fix (B1)
        await pilot.pause()
    assert recorded.get('cmd', [])[-1] == '--check', recorded
