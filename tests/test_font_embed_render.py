"""Task 11 SLOW tests (plan 2026-11-16): real renders proving the embedded face is used and
the font gate exits 5 on a missing face. Need the render toolchain — run only in the full
suite incl. slow (hyperframes on PATH); skipped otherwise."""
import json
import os
import shutil
import subprocess

import pytest

from motion_pipeline import generate, project
from test_generate import DARK, make_project
from motion_pipeline.scheme import save_scheme

pytestmark = pytest.mark.slow

HF = shutil.which('hyperframes')
pytestmark = [pytest.mark.slow, pytest.mark.skipif(HF is None, reason='hyperframes not installed (run motion-pipeline --setup-render)')]


def _render(d, variant='default'):
    generate.generate(d, variant)
    r = subprocess.run(['bash', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                              'tools', 'render_scene.sh'),
                        '--project', d, '--variant', variant, '--mode', 'test'],
                       capture_output=True, text=True)
    return r


def test_render_uses_embedded_font(tmp_path):
    """Montserrat vs Inter body -> the first rendered frame's text pixels differ."""
    d1, _, _ = make_project(tmp_path / 'a')
    d2, _, _ = make_project(tmp_path / 'b')
    for d, fam in ((d1, 'Montserrat'), (d2, 'Inter')):
        from motion_pipeline import project
        p = project.load(d)
        p['fonts'] = {'family': fam}
        project.save(d, p)
        save_scheme(os.path.join(d, 'scheme.json'), DARK)
    r1 = _render(d1)
    assert r1.returncode == 0, r1.stderr[-500:]
    r2 = _render(d2)
    assert r2.returncode == 0, r2.stderr[-500:]
    # frames are removed after packing; compare the masters' first frame via ffmpeg instead
    sj1 = json.load(open(os.path.join(d1, 'src', 'scenes.json')))
    sj2 = json.load(open(os.path.join(d2, 'src', 'scenes.json')))
    # masters are .mov since Task 15 (the old .mp4-only glob went stale)
    m1 = os.path.join(d1, 'renders', 'default', sj1[0]['file'].replace('.html', '.mov'))
    m2 = os.path.join(d2, 'renders', 'default', sj2[0]['file'].replace('.html', '.mov'))
    assert os.path.isfile(m1) and os.path.isfile(m2), (m1, m2)
    from PIL import Image
    import io
    # frame 0 is black (fade-in) for both — compare a still where text is visible; test-mode
    # masters cap at 60 frames, so clamp into the rendered span
    t1 = min((sj1[0]['start'] + sj1[0]['end']) / 2, 0.5)
    t2 = min((sj2[0]['start'] + sj2[0]['end']) / 2, 0.5)
    p1 = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t1:.3f}', '-i', m1,
                         '-frames:v', '1', '-f', 'image2pipe', '-'],
                        capture_output=True).stdout
    p2 = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t2:.3f}', '-i', m2,
                         '-frames:v', '1', '-f', 'image2pipe', '-'],
                        capture_output=True).stdout
    a1, a2 = Image.open(io.BytesIO(p1)), Image.open(io.BytesIO(p2))
    assert a1.tobytes() != a2.tobytes(), 'Montserrat vs Inter body must render different pixels'


def test_missing_font_fails_render_exit5(tmp_path):
    """A role face that exists on disk but is corrupt must fail the PAGE font gate (exit 5,
    MP_FONT_MISSING in the render log). Deleting src/fonts no longer works since 0.6.3's
    scratch-project test renders — they regenerate src — so break a CLIENT face instead."""
    d, _, _ = make_project(tmp_path / 'c')
    p = project.load(d)
    # point the body role at a client font that exists but is not a font
    fdir = os.path.join(d, 'fonts')
    os.makedirs(fdir, exist_ok=True)
    open(os.path.join(fdir, 'broken.ttf'), 'wb').write(b'not a font at all')
    from motion_pipeline import fonts as fonts_mod
    p['fonts'] = {'roles': {r: {'family': 'BrokenX', 'weight': 400,
                                'file': 'fonts/broken.ttf', 'index': 0}
                           for r in fonts_mod.ROLES}}
    project.save(d, p)
    r = _render(d)
    assert r.returncode == 5, (r.returncode, r.stderr[-400:])
    assert 'font gate' in r.stderr or 'MP_FONT_MISSING' in r.stderr
