"""Feature tests 2026-11-09: custom in/out paths, clickable output link, inline test image."""
import json
import os
import subprocess

import pytest
from textual.widgets import Button, Input, Static

from tui_probe import choose
from motion_pipeline.tui.app import MenuApp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_render_scene_accepts_custom_out():
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'), '--help'],
                       capture_output=True, text=True)
    assert '--out DIR' in r.stdout
    # dry-run with a custom --out names it in the plan
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'p')
        os.makedirs(os.path.join(p, 'src'))
        open(os.path.join(p, 'project.json'), 'w').write(json.dumps(
            {'name': 'p', 'aspect': '16:9', 'resolution': [1920, 1080], 'fps': 60,
             'variants': ['default'], 'zones': [], 'fonts': {}, 'transcript': 't', 'vo': None}))
        open(os.path.join(p, 'src', 'scene_A.html'), 'w').write('<html></html>')
        out = os.path.join(td, 'custom-out')
        r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'),
                            '--project', p, '--variant', 'default', '--mode', 'test',
                            '--out', out, '--dry-run'], capture_output=True, text=True)
        assert r.returncode == 0 and out in r.stdout, r.stdout + r.stderr


@pytest.mark.asyncio
async def test_render_screen_has_outdir_link_and_open_button(tmp_path, monkeypatch):
    monkeypatch.setattr('motion_pipeline.tui.colours_screen.PROJECTS', str(tmp_path))
    app = MenuApp()
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['render']())
        await pilot.pause()
        screen = app.screen
        outdir = screen.query_one('#outdir', Input)
        assert outdir.placeholder  # custom output path field present
        assert screen.query_one('#actions').get_option('open').disabled  # enabled after a render
        assert screen.query_one('#link', Static)
        # simulate a finished render into a custom dir
        custom = tmp_path / 'my-renders'
        custom.mkdir()
        outdir.value = str(custom)
        screen.on_render_done(0)
        await pilot.pause()
        assert str(custom) in str(screen.query_one('#link', Static).content)  # path visible
        assert screen.link_url == f'file://{custom}'  # OSC-8 hyperlink target
        assert not screen.query_one('#actions').get_option('open').disabled


@pytest.mark.asyncio
async def test_bgtest_shows_inline_image_and_link(tmp_path, monkeypatch):
    monkeypatch.setattr('motion_pipeline.tui.colours_screen.PROJECTS', str(tmp_path))
    app = MenuApp()
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['bgtest']())
        await pilot.pause()
        screen = app.screen
        assert screen.query_one('#outdir', Input)
        assert screen.query_one('#image', Static)
        # fixture: a tiny master + let on_render_done extract frame 0
        out = tmp_path / 'out'
        out.mkdir()
        screen.query_one('#outdir', Input).value = str(out)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=blue:s=320x180:d=1:r=30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        str(out / 'scene_Test.mp4')], check=True)
        screen.on_render_done(0)
        await pilot.pause()
        img = screen.query_one('#image', Static).render()
        assert img is not None and str(img) != '', 'no inline image rendered'
        assert str(out) in str(screen.query_one('#link', Static).content)
        assert screen.link_url == f'file://{out}'


def test_jobs_on_finish_fires(tmp_path):
    import asyncio
    from motion_pipeline.tui.app import MenuApp
    from motion_pipeline.tui.jobs import run_command
    from textual.widgets import Log

    async def go():
        app = MenuApp()
        async with app.run_test() as pilot:
            app.push_screen(app.SCREENS['render']())
            await pilot.pause()
            log = app.screen.query_one('#log', Log)
            got = []
            run_command(app, ['bash', '-c', 'echo hi; exit 3'], log,
                        on_finish=lambda rc: got.append(rc))
            await pilot.pause()
            for _ in range(50):
                await pilot.pause()
                if got:
                    break
            assert got == [3], got
    asyncio.run(go())
