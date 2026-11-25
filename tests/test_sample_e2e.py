"""Task 11/18: sample project end-to-end — the SHIPPED sample (samples/globe) generates,
renders for real, and passes the chroma/zone gates."""
import json
import os
import shutil
import subprocess

import pytest

from motion_pipeline import generate, project

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def sample_project(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('sample')
    d = tmp / 'projects' / 'globe-sample'
    shutil.copytree(os.path.join(ROOT, 'samples', 'globe'), d)
    # Task 18: load the sample AS SHIPPED — project.json/scheme.json come from samples/globe,
    # and timings + pages come from the real shipped path (--prepare-only), not hand-built files
    from motion_pipeline import render_cli
    assert render_cli.main(['--project', str(d), '--prepare-only']) == 0
    return str(d)


def test_sample_loads_unmodified():
    """Task 18: the SHIPPED sample (samples/globe as committed) validates unmodified."""
    d = os.path.join(ROOT, 'samples', 'globe')
    p = project.load(d)
    assert p['aspect'] == '16:9' and p['fps'] == 25 and p['graphics'] == ['globe']
    assert p['fonts']['family'] == 'Montserrat' and p['fonts']['roles'] == \
        {'headline': 700, 'label': 600, 'body': 400, 'emphasis': 700}
    assert any(z['section'] == 'Welcome' and z.get('aspect') == '16:9' for z in p['zones'])
    from motion_pipeline.scheme import load_scheme
    s = load_scheme(os.path.join(d, 'scheme.json'))
    assert s['background_dark'] == '#0b1a4c' and s['accent'] == '#ffb400'
    assert os.path.isfile(os.path.join(d, 'transcript.txt'))


def test_sample_generates_scenes_and_globe_assets(sample_project):
    src = os.path.join(sample_project, 'src')
    scenes = json.load(open(os.path.join(src, 'scenes.json')))  # Task 12: scene_<NN>_<slug>.html
    assert os.path.isfile(os.path.join(src, scenes[0]['file']))
    assert os.path.isfile(os.path.join(src, 'globe.js'))
    assert os.path.isfile(os.path.join(src, 'land-110m.js'))
    page = open(os.path.join(src, scenes[0]['file'])).read()
    assert 'GLOBE.create' in page and 'paintBg' in page


def test_zone_gate_on_sample(sample_project):
    r = subprocess.run(['python3', os.path.join(ROOT, 'tools', 'check_zone.py'),
                        '--project', sample_project], capture_output=True, text=True,
                       env={**os.environ, 'PYTHONPATH': ROOT})
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'zones OK' in r.stdout


def _hyperframes_missing():
    from motion_pipeline import render_cli
    try:
        render_cli.find_hyperframes()
        return False
    except Exception:
        return True


@pytest.mark.skipif(_hyperframes_missing(), reason='hyperframes not installed (PATH / repo node_modules / toolchain cache)')
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
    from motion_pipeline import render_cli
    env['PATH'] = (f"{ROOT}/.venv/bin:{os.path.dirname(render_cli.find_hyperframes())}:"
                   f"{ROOT}/node_modules/.bin:{env['PATH']}")
    # the 2.0-2.5 s window in FRAMES of THIS sample's fps — the old hardcoded 120-149 assumed
    # the fixture's 60 fps; the shipped sample is 25 fps, where 120-149 trims to ZERO frames
    # (empty video.mp4, mux map fails) — 2026-11-19
    fps = json.load(open(os.path.join(sample_project, 'project.json')))['fps']
    f0, f1 = round(2.0 * fps), round(2.5 * fps)
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'),
                        '--project', sample_project, '--variant', 'default', '--mode', 'test',
                        '--frames', f'{f0}-{f1}'],
                       capture_output=True, text=True, timeout=560, env=env)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
    import glob
    # Task 15: masters are .mov (VO+SFX muxed) — the old .mp4 glob hid behind the slow
    # marker until the unfiltered gate ran it (2026-11-19)
    masters = glob.glob(os.path.join(sample_project, 'renders', 'default', 'scene_*.mov'))
    assert masters, r.stdout[-1500:]
    master = masters[0]
    prof = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                           'stream=profile,pix_fmt,nb_read_frames', '-of', 'csv=p=0', master],
                          capture_output=True, text=True)
    assert 'High 4:2:2' in prof.stdout and 'yuv422p10le' in prof.stdout, prof.stdout
    # chroma gate on the steepest background strip (scan the top strip y<140px — above every
    # candidate text position (place_text_block starts at 0.15H=162) and the card title is
    # gone by 2.0 s, so this region is content-free at ANY frame; 0.8.5 L0 moved word tweens
    # to their true t.start, so words are already visible in the lower region at 2.0 s)
    import numpy as np
    # sample a frame that EXISTS in the trimmed master: the --frames window above is ~13
    # output frames at the sample's fps, so the old hardcoded n=15 read nothing (empty
    # buffer, reshape of size 0) — 2026-11-19
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', master, '-vf',
                          'select=eq(n\\,5),format=yuv422p10le', '-frames:v', '1',
                          '-f', 'rawvideo', '-'], capture_output=True)
    assert raw.stdout, 'chroma gate got no bytes — the sampled frame is past the master end'
    w, h = 1920, 1080
    buf = np.frombuffer(raw.stdout, dtype='<u2')
    cb = buf[w * h:w * h + (w // 2) * h].reshape(h, w // 2).astype(float)
    best, best_x = 0.0, 0
    for x0 in range(0, 460, 20):
        tot = float(np.abs(np.diff(cb[0:140, x0:x0 + 300].mean(axis=0))).sum())
        if tot > best:
            best, best_x = tot, x0
    strip = f'{best_x * 2},{best_x * 2 + 600},0,140'
    # the gate frame must exist in the TRIMMED master (the --frames window is ~13 frames at
    # the sample's fps — the old hardcoded 15 was past the end: "decode failed … 0 bytes").
    # Frame 0 of the trimmed output is already past the intro card (2.0 s > 1.6 s fade).
    gate_frame = '0'
    g = subprocess.run(['python3', os.path.join(ROOT, 'tools', 'check_chroma_steps.py'),
                        '--video', master, '--frame', gate_frame, '--strip', strip],
                       capture_output=True, text=True,
                       env={**os.environ, 'PYTHONPATH': ROOT})
    assert g.returncode == 0, g.stdout + g.stderr
    # render_info records the 10-bit intermediate marker
    info = json.load(open(os.path.join(sample_project, 'renders', 'default', 'render_info.json')))
    assert info['intermediate'] == 'ffv1-bgr0'
    assert info['verify'] == 'VERIFIED'
