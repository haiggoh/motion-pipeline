"""0.5.0 Task 6: the menu's background test runs the REAL pipeline (v0.4.x shipped a
placeholder `echo`), prepares its own inputs, names missing dependencies, and the preview
image lands below the actions."""
import json
import os
import subprocess
import sys

import pytest

from motion_pipeline import render_cli
from motion_pipeline.tui.app import MenuApp
from projfix import ROOT, make_project
from tui_probe import on_screen

PY = sys.executable


def _cli(*args, env=None):
    return subprocess.run([PY, '-m', 'motion_pipeline.render_cli', *args], capture_output=True,
                          text=True, cwd=ROOT, env=env)


def test_help_and_bad_flag():
    r = _cli('--help')
    assert r.returncode == 0 and '--setup' in r.stdout and 'MP_HYPERFRAMES' in r.stdout
    assert _cli('--bogus').returncode == 2


def test_default_menu_commands_are_the_real_pipeline(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    for cmd, mode in ((app.test_render_cmd(), 'test'), (app.full_render_cmd(), 'full')):
        assert cmd[:3] == [sys.executable, '-m', 'motion_pipeline.render_cli'], cmd
        assert cmd[cmd.index('--project') + 1] == str(tmp_path) and cmd[cmd.index('--mode') + 1] == mode
        assert not any('placeholder' in c for c in cmd)


def test_invalid_override_and_missing_dependency_are_named(tmp_path):
    env = dict(os.environ, MP_HYPERFRAMES=str(tmp_path / 'nope'))
    r = _cli('--check', env=env)
    assert r.returncode == 2 and 'MP_HYPERFRAMES' in r.stderr
    env = dict(os.environ, PATH='/usr/bin:/bin')   # no ffmpeg
    r = _cli('--check', env=env)
    assert r.returncode == 3 and 'missing dependency: ffmpeg' in r.stderr and 'brew install' in r.stderr


def test_prepares_inputs_generates_and_hands_off_to_render_scene(tmp_path):
    pd = make_project(tmp_path / 'p')
    for f in ('transcript_model.json', 'timing.json'):
        os.remove(os.path.join(pd, f))                  # what a menu-made project looks like
    r = _cli('--project', pd, '--mode', 'test', '--dry-run')
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.isfile(os.path.join(pd, 'timing.json'))
    assert os.path.isfile(os.path.join(pd, 'src', 'scene_Welcome.html'))
    assert 'render_scene.sh' in r.stdout and '--variant default' in r.stdout and 'would: hyperframes' in r.stdout


def test_full_mode_iterates_every_variant(tmp_path):
    from motion_pipeline import scheme
    from projfix import DARK
    pd = make_project(tmp_path / 'p')
    scheme.save_variant(pd, 'warm', dict(DARK, accent='#ff6a00'))
    p = json.load(open(os.path.join(pd, 'project.json'))); p['variants'] = ['default', 'warm']
    json.dump(p, open(os.path.join(pd, 'project.json'), 'w'))
    r = _cli('--project', pd, '--mode', 'full', '--dry-run', '--out', str(tmp_path / 'o'))
    assert r.returncode == 0, r.stderr
    assert '--variant default' in r.stdout and '--variant warm' in r.stdout
    assert str(tmp_path / 'o' / 'warm') in r.stdout


def test_missing_transcript_is_named(tmp_path):
    pd = make_project(tmp_path / 'p')
    os.remove(os.path.join(pd, 'transcript.txt'))
    r = _cli('--project', pd, '--mode', 'test', '--dry-run')
    assert r.returncode == 3 and 'transcript' in r.stderr and 'step 5' in r.stderr


async def test_failed_render_shows_exit_and_hint_not_a_traceback(tmp_path):
    cmd = ['bash', '-c', 'echo "missing dependency: hyperframes — run: motion-pipeline --setup-render" >&2; exit 3']
    app = MenuApp(test_render_cmd=cmd)
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['bgtest']()); await pilot.pause()
        from tui_probe import choose
        await choose(pilot, app.screen, 'run')
        for _ in range(40):
            await pilot.pause(0.05)
            if 'exit' in str(app.screen.query_one('#status').render()):
                break
        status = str(app.screen.query_one('#status').render())
        assert 'failed (exit 3)' in status and 'setup-render' in status, status
        assert on_screen(app, app.screen.query_one('#status'))


@pytest.mark.slow
async def test_background_test_real_render_shows_image_below_actions(tmp_path):
    try:
        render_cli.preflight()
    except render_cli.Missing as e:
        pytest.fail(f'render toolchain missing on this machine: {e}')   # never a silent skip
    pd = make_project(tmp_path / 'p')
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(100, 40)) as pilot:
        app.push_screen(app.SCREENS['bgtest']()); await pilot.pause()
        from tui_probe import choose
        await choose(pilot, app.screen, 'run')
        for _ in range(1800):                     # up to ~3 min
            await pilot.pause(0.1)
            if 'exit' in str(app.screen.query_one('#status').render()):
                break
        scr = app.screen
        log = '\n'.join(str(l) for l in scr.query_one('#log').lines)
        assert 'done (exit 0)' in str(scr.query_one('#status').render()), log[-1500:]
        img = scr.query_one('#image')
        assert img.region.height >= 5 and on_screen(app, img), img.region
        assert img.region.y > scr.query_one('#actions').region.y   # below the actions
        assert os.path.isfile(os.path.join(pd, 'renders', 'default', '_test_frame.png'))
