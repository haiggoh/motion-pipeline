"""Task 23 tests (plan 2026-11-16): the "Add motion graphics" step — it sits between inputs and
render as step 6 (render becomes 7), the instructions show live counts + the project path, the
playbook is regenerated on visit, the copy action pipes the link-form prompt to pbcopy, the
free-agents row/Selects appear ONLY when detect() succeeds, and "Check AI graphics" runs the
real --check-graphics as a job with the result in the status line."""
import json
import os

import pytest

from motion_pipeline import free_agents
from motion_pipeline.tui.app import MenuApp, MenuScreen, STEPS
from motion_pipeline.tui.graphics_screen import GraphicsScreen
from projfix import make_project
from tui_probe import choose


def test_step_list_has_graphics_before_render():
    ids = [k for k, _ in STEPS]
    assert ids == ['project', 'colours', 'fonts', 'zones', 'bgtest', 'inputs', 'graphics', 'render']


@pytest.mark.asyncio
async def test_menu_shows_graphics_as_step_6_and_hint_0_to_7(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.push_screen(MenuScreen())
        await pilot.pause()
        menu = app.screen.query_one('#actions')
        assert menu.numbers['6'] == 'graphics' and menu.numbers['7'] == 'render'  # digit -> step
        prompts = [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]
        assert any(p.startswith('6) Add motion graphics') for p in prompts) and '7) Render' in prompts
        assert '0-7' in str(app.screen.query_one('.hint').render())


@pytest.mark.asyncio
async def test_instructions_show_live_counts_and_path_and_playbook_regenerated(tmp_path, monkeypatch):
    pd = make_project(tmp_path / 'p')
    monkeypatch.setattr(free_agents, 'detect', lambda *a, **k: None)  # no free-agents row
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(GraphicsScreen())
        await pilot.pause()
        text = str(app.screen.query_one('#instructions').render())
        tr = json.load(open(os.path.join(pd, 'transcript_model.json')))
        assert f'{len(tr["words"])} words' in text and f'{len(tr["sections"])} sections' in text
        assert 'MOTION_GRAPHICS_PLAYBOOK.md' in text and pd in text
        assert os.path.isfile(os.path.join(pd, 'MOTION_GRAPHICS_PLAYBOOK.md'))  # regenerated on visit
        # free-agents absent: no 'free' row, no Selects at all
        menu = app.screen.query_one('#actions')
        ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
        assert 'free' not in ids
        assert not app.screen.query('#fa-model') and not app.screen.query('#fa-effort')


@pytest.mark.asyncio
async def test_copy_prompt_pipes_link_form_to_pbcopy(tmp_path, monkeypatch):
    pd = make_project(tmp_path / 'p')
    monkeypatch.setattr(free_agents, 'detect', lambda *a, **k: None)
    import motion_pipeline.tui.graphics_screen as gs
    captured = {}
    monkeypatch.setattr(gs, '_pbcopy', lambda text: captured.setdefault('text', text))
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(GraphicsScreen())
        await pilot.pause()
        await choose(pilot, app.screen, 'copy')
        await pilot.pause()
    text = captured['text']
    assert os.path.join(pd, 'MOTION_GRAPHICS_PLAYBOOK.md') in text
    assert 'Read' in text and 'follow it exactly' in text and 'AskUserQuestion' in text


@pytest.mark.asyncio
async def test_free_agents_row_and_selects_only_when_detected(tmp_path, monkeypatch):
    pd = make_project(tmp_path / 'p')
    monkeypatch.setattr(free_agents, 'detect', lambda *a, **k: object())
    monkeypatch.setattr(free_agents, 'models', lambda fa, env=None: [
        {'alias': 'nvidia-glm53', 'display': 'Z.ai GLM 5.3 Flash', 'tier': 'unknown',
         'key_ok': True, 'free': True}])
    from textual.widgets import Select
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(GraphicsScreen())
        await pilot.pause()
        menu = app.screen.query_one('#actions')
        ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
        assert 'free' in ids
        sel = app.screen.query_one('#fa-model', Select)
        assert sel.value == 'nvidia-glm53'  # ladder top is the default
        assert app.screen.query_one('#fa-effort', Select).value == 'high'


@pytest.mark.asyncio
async def test_check_action_runs_real_check_graphics_job(tmp_path, monkeypatch):
    pd = make_project(tmp_path / 'p')
    monkeypatch.setattr(free_agents, 'detect', lambda *a, **k: None)
    # the job runs `python -P -m motion_pipeline.render_cli` (production: brew-installed); in the
    # dev venv the package is not installed, so give the subprocess the repo root via PYTHONPATH
    from projfix import ROOT
    monkeypatch.setenv('PYTHONPATH', ROOT)
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(GraphicsScreen())
        await pilot.pause()
        await choose(pilot, app.screen, 'check')
        for _ in range(60):
            await pilot.pause(0.2)
            if 'exit' in str(app.screen.query_one('#status').render()):
                break
        status = str(app.screen.query_one('#status').render())
        assert 'check-graphics exit 0' in status, status
