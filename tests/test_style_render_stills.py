"""Task 7b F1 (0.8.0 plan): per-style render stills — one scratch project per text style,
render frames 0-59 in test mode, extract frame 0 / 15 / 50, assert the master exists, the
landed frame differs from frame 0 (text actually appeared), non-default styles differ from
slide-up's landed frame, and the zone gate (exit 6) did not fire. Self-skips without
hyperframes on PATH (the normal gate env); run with `source tools/env.sh` sourced.

Discriminant: a style whose tween_js is stubbed to empty leaves the words at their hidden
initial CSS -> the landed frame EQUALS frame 0 -> this test goes RED.
"""
import os
import shutil
import subprocess

import pytest
from projfix import ROOT, make_project

from motion_pipeline import generate, text_styles
from motion_pipeline import project as project_mod

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(shutil.which('hyperframes') is None,
                                 reason='hyperframes not on PATH (source tools/env.sh)')]

FRAMES = (0, 120, 230)   # t=0 (words hidden), mid-scene, last frame of the 3.85 s scene
# NOTE: --frames 0-59 (the plan's test cap) shows only the card — gsap appends the word
# tweens after the card tweens, so words land later than 1 s. 0-230 at 60 fps covers the
# word landings, which is where the styles actually diverge.


def _render_style(base, name):
    pd = make_project(str(base / name / 'proj'))
    p = project_mod.load(pd)
    p['text_style'] = name
    project_mod.save(pd, p)
    generate.generate(pd)
    out = os.path.join(pd, 'renders', name)
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'),
                        '--project', pd, '--variant', 'default', '--mode', 'test',
                        '--frames', '0-230', '--out', out],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0 and r.returncode != 6, (r.returncode, r.stderr[-600:])
    masters = [f for f in os.listdir(out) if f.endswith('.mov')]
    assert masters, f'no master in {out}'
    return pd, os.path.join(out, masters[0])


def _frame(master, n, dst):
    subprocess.run(['ffmpeg', '-v', 'error', '-i', master, '-vf', f'select=eq(n\\,{n})',
                    '-frames:v', '1', '-y', dst], check=True)
    return dst


@pytest.fixture(scope='module')
def stills(tmp_path_factory):
    base = tmp_path_factory.mktemp('stills')
    out = {}
    for name in sorted(text_styles.STYLES):
        _pd, master = _render_style(base, name)
        out[name] = {n: _frame(master, n, str(base / name / f'f{n}.png')) for n in FRAMES}
    return out


@pytest.mark.parametrize('name', sorted(text_styles.STYLES))
def test_style_render_still(stills, name):
    import numpy as np
    from PIL import Image

    def a(p):
        return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)

    s = stills[name]
    f0, f120, f230 = a(s[0]), a(s[120]), a(s[230])
    assert (f0 ^ f230).mean() > 0.5, f'{name}: landed frame == frame 0 — text never appeared (tween_js empty?)'
    assert (f0 ^ f120).mean() > 0.5 or (f120 ^ f230).mean() > 0.5, f'{name}: no visible motion'
    if name != text_styles.DEFAULT:
        ref = a(stills[text_styles.DEFAULT][230])
        assert (f230 ^ ref).mean() > 1.0, f'{name}: landed frame equals slide-up — style not rendered'


def test_short_test_render_shows_words(tmp_path):
    """0.8.5 L0 T6: with positional tweens, a 60-frame test render (--frames 0-59, the
    render-test cap) must show the words — frame 45 differs from frame 0 in the text
    region. Pre-L0 this showed only the card (gsap appended the delay-carrying word
    tweens after the card tweens)."""
    import numpy as np
    from PIL import Image

    pd = make_project(str(tmp_path / 'proj'))
    generate.generate(pd)
    out = os.path.join(pd, 'renders', 'short')
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'),
                        '--project', pd, '--variant', 'default', '--mode', 'test',
                        '--frames', '0-59', '--out', out],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, (r.returncode, r.stderr[-600:])
    master = os.path.join(out, next(f for f in os.listdir(out) if f.endswith('.mov')))
    f0 = _frame(master, 0, str(tmp_path / 'f0.png'))
    f45 = _frame(master, 45, str(tmp_path / 'f45.png'))

    def a(p):
        return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)

    d0, d45 = a(f0), a(f45)
    diff = (d0 ^ d45)[400:900, 100:1800].mean()   # text block region at 16:9
    assert diff > 0.5, f'frame 45 == frame 0 in the text region (mean xor {diff}) — words not visible in a 60-frame render'
