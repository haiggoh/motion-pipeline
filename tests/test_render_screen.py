"""Task 5 (plan 2026-11-16): render screens — one job at a time, honest status, wrapped log,
right open-target. Uses MenuApp(test_render_cmd=[...]) fakes; no real render runs."""
import os

import pytest
from textual.widgets import RichLog, Static

from motion_pipeline import project
from motion_pipeline.tui.app import MenuApp
from tui_probe import choose


def mk(d, variants=('default',)):
    d = str(d)
    p = project.default_project('demo')
    p['variants'] = list(variants)
    project.save(d, p)
    return d


def log_text(log):
    """RichLog.lines holds rich Strip objects — get their plain text."""
    return [x.text if hasattr(x, 'text') else str(x) for x in log.lines]


@pytest.mark.asyncio
async def test_run_disabled_while_running(tmp_path):
    d = mk(tmp_path / 'proj')
    app = MenuApp(test_render_cmd=['bash', '-c', 'sleep 5'])
    app.project_dir = d
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['bgtest']())
        await pilot.pause()
        scr = app.screen
        menu = scr.query_one('#actions')
        assert not menu.get_option('run').disabled
        assert menu.get_option('cancel').disabled
        await choose(pilot, scr, 'run')
        await pilot.pause(0.3)
        assert menu.get_option('run').disabled and not menu.get_option('cancel').disabled
        w1 = scr.worker
        menu.focus()
        await pilot.press('1')  # second Run press while running: must start nothing
        await pilot.pause(0.3)
        assert scr.worker is w1, 'a second run replaced the running job'
        await choose(pilot, scr, 'cancel')
        await pilot.pause(0.5)
        assert not menu.get_option('run').disabled and menu.get_option('cancel').disabled


@pytest.mark.asyncio
async def test_failed_job_says_failed(tmp_path):
    d = mk(tmp_path / 'proj')
    app = MenuApp(test_render_cmd=['bash', '-c', 'echo boom; exit 3'])
    app.project_dir = d
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['bgtest']())
        await pilot.pause()
        scr = app.screen
        await choose(pilot, scr, 'run')
        lines = []
        for _ in range(100):  # poll with real time — under -n auto the worker thread may be slow
            await pilot.pause(0.05)
            lines = log_text(scr.query_one('#log', RichLog))
            if lines and 'exit' in lines[-1]:
                break
        assert lines and lines[-1] == 'failed (exit 3)', lines[-3:]
        status = str(scr.query_one('#status', Static).render())
        assert 'failed (exit 3)' in status, status
        assert not scr.query_one('#actions').get_option('run').disabled


@pytest.mark.asyncio
async def test_long_log_line_wraps(tmp_path):
    d = mk(tmp_path / 'proj')
    line = 'x' * 200
    app = MenuApp(test_render_cmd=['bash', '-c', f'echo {line}; exit 0'])
    app.project_dir = d
    async with app.run_test(size=(80, 30)) as pilot:
        app.push_screen(app.SCREENS['bgtest']())
        await pilot.pause()
        scr = app.screen
        await choose(pilot, scr, 'run')
        log = scr.query_one('#log', RichLog)
        for _ in range(100):
            await pilot.pause(0.05)
            if line in ''.join(log_text(log)):
                break
        assert log.wrap is True and log.markup is False
        assert log.max_scroll_x == 0, 'wrapped log must not scroll horizontally'
        content = ''.join(log_text(log))
        assert line in content  # all 200 chars present, wrapped not clipped


class _DummyPopen:
    pass


def _patch_open_only(monkeypatch, opened):
    """Record `open <dir>` calls; delegate everything else (the render job's Popen) to the real one."""
    import subprocess
    real_popen = subprocess.Popen

    def fake(*a, **k):
        if a and a[0] and a[0][0] == 'open':
            opened.append(a[0])
            return _DummyPopen()
        return real_popen(*a, **k)

    monkeypatch.setattr('subprocess.Popen', fake)


@pytest.mark.asyncio
async def test_full_render_open_targets_renders_root_or_variant(tmp_path, monkeypatch):
    opened = []
    _patch_open_only(monkeypatch, opened)
    # multiple variants -> the renders ROOT
    d = mk(tmp_path / 'proj', variants=('a', 'b'))
    app = MenuApp(full_render_cmd=['bash', '-c', 'exit 0'])
    app.project_dir = d
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['render']())
        await pilot.pause()
        scr = app.screen
        await choose(pilot, scr, 'run')
        await pilot.pause(1.5)
        await choose(pilot, scr, 'open')
        await pilot.pause()
        assert opened and opened[0] == ['open', os.path.join(d, 'renders')], opened
    # single variant -> renders/<variant>
    opened.clear()
    d2 = mk(tmp_path / 'proj2', variants=('solo',))
    app2 = MenuApp(full_render_cmd=['bash', '-c', 'exit 0'])
    app2.project_dir = d2
    async with app2.run_test(size=(100, 30)) as pilot:
        app2.push_screen(app2.SCREENS['render']())
        await pilot.pause()
        scr = app2.screen
        await choose(pilot, scr, 'run')
        await pilot.pause(1.5)
        await choose(pilot, scr, 'open')
        await pilot.pause()
        assert opened and opened[0] == ['open', os.path.join(d2, 'renders', 'solo')], opened
