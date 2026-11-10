"""Task 11: sample project end-to-end — generate + real test render + chroma/zone gates."""
import json
import os
import shutil
import subprocess

import pytest

from motion_pipeline import align, generate, project, transcript
from motion_pipeline.scheme import save_scheme

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DARK = {'name': 'default', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}


@pytest.fixture(scope='module')
def sample_project(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('sample')
    d = tmp / 'projects' / 'globe-sample'
    shutil.copytree(os.path.join(ROOT, 'samples', 'globe'), d)
    p = project.default_project('globe-sample')
    # full frame size: at small resolutions the 8-bit RGB capture floor itself shows
    # 4-code Cb steps; at 1920x1080 the gate threshold 2.0 is the measured regime
    p['graphics'] = ['globe']  # exercised in the generate test; the render test drops it below
    p['zones'] = [{'section': 'Welcome', 'rect': [int(1920 * 0.55), 80, 700, 500]}]
    p['fonts'] = {'family': 'Montserrat'}
    project.save(str(d), p)
    save_scheme(str(d / 'scheme.json'), DARK)
    tr = transcript.load(str(d / 'transcript.txt'))
    (d / 'transcript_model.json').write_text(json.dumps(tr))
    timing = align.estimate_timings(tr, wpm=140)
    align.save_timing(str(d / 'timing.json'), timing)
    generate.generate(str(d))
    return str(d)


def test_sample_generates_scenes_and_globe_assets(sample_project):
    src = os.path.join(sample_project, 'src')
    assert os.path.isfile(os.path.join(src, 'scene_Welcome.html'))
    assert os.path.isfile(os.path.join(src, 'globe.js'))
    assert os.path.isfile(os.path.join(src, 'land-110m.js'))
    page = open(os.path.join(src, 'scene_Welcome.html')).read()
    assert 'GLOBE.create' in page and 'paintBg' in page


def test_zone_gate_on_sample(sample_project):
    r = subprocess.run(['python3', os.path.join(ROOT, 'tools', 'check_zone.py'),
                        '--project', sample_project], capture_output=True, text=True,
                       env={**os.environ, 'PYTHONPATH': ROOT})
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'zones OK' in r.stdout


@pytest.mark.skipif(shutil.which('hyperframes') is None and not os.path.isdir(os.path.join(ROOT, 'node_modules')),
                    reason='hyperframes not installed')
@pytest.mark.slow
def test_real_test_render_and_chroma_gate(sample_project):
    # frames 120-149 (2.0-2.5 s): the section's unit-heading card (a full-frame flat panel,
    # fading in/out over 0-1.6 s) is gone, so the gate measures the gradient background —
    # v0.1-0.4 sampled frame 15 only because the card's CSS was a dead selector (fixed 0.5.0)
    # drop the globe for the render test (its vector strokes are graphics, not gradient;
    # the globe render path is covered by the generate test) — plain bg+text at 1080p
    import json as _json
    pj = _json.load(open(os.path.join(sample_project, 'project.json')))
    pj['graphics'] = []
    _json.dump(pj, open(os.path.join(sample_project, 'project.json'), 'w'))
    generate.generate(sample_project)
    env = dict(os.environ)
    env['PATH'] = f"{ROOT}/.venv/bin:{ROOT}/node_modules/.bin:{env['PATH']}"
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'),
                        '--project', sample_project, '--variant', 'default', '--mode', 'test',
                        '--frames', '120-149'],
                       capture_output=True, text=True, timeout=560, env=env)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
    import glob
    masters = glob.glob(os.path.join(sample_project, 'renders', 'default', 'scene_*.mp4'))
    assert masters, r.stdout[-1500:]
    master = masters[0]
    prof = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                           'stream=profile,pix_fmt,nb_read_frames', '-of', 'csv=p=0', master],
                          capture_output=True, text=True)
    assert 'High 4:2:2' in prof.stdout and 'yuv422p10le' in prof.stdout, prof.stdout
    # chroma gate on the steepest background strip of frame 15 (scan the top 2/3 of the
    # frame, left half — text block sits bottom-left; the banded/8-bit discriminant is
    # proven at page level in test_background.py::test_banded_mode_fails_chroma_gate)
    import numpy as np
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', master, '-vf',
                          'select=eq(n\\,15),format=yuv422p10le', '-frames:v', '1',
                          '-f', 'rawvideo', '-'], capture_output=True)
    w, h = 1920, 1080
    buf = np.frombuffer(raw.stdout, dtype='<u2')
    cb = buf[w * h:w * h + (w // 2) * h].reshape(h, w // 2).astype(float)
    best, best_x = 0.0, 0
    for x0 in range(0, 460, 20):
        tot = float(np.abs(np.diff(cb[0:700, x0:x0 + 300].mean(axis=0))).sum())
        if tot > best:
            best, best_x = tot, x0
    strip = f'{best_x * 2},{best_x * 2 + 600},0,700'
    g = subprocess.run(['python3', os.path.join(ROOT, 'tools', 'check_chroma_steps.py'),
                        '--video', master, '--frame', '15', '--strip', strip],
                       capture_output=True, text=True,
                       env={**os.environ, 'PYTHONPATH': ROOT})
    assert g.returncode == 0, g.stdout + g.stderr
    # render_info records the 10-bit intermediate marker
    info = json.load(open(os.path.join(sample_project, 'renders', 'default', 'render_info.json')))
    assert info['intermediate'] == 'ffv1-bgr0'
    assert info['verify'] == 'VERIFIED'
