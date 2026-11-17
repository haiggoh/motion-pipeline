"""Task 22 SLOW test (plan 2026-11-16) — real render, minutes; the gate runs -m 'not slow'.
A manifest graphic that fills zone 0 with a white rect at word wN must change the rendered
frame at/after wN vs before it (frame pixels compared via ffmpeg crop+luma, not a mock)."""
import glob
import json
import os
import shutil
import subprocess

import pytest

from motion_pipeline import generate
from projfix import ROOT, make_project

pytestmark = pytest.mark.slow

ZONE0 = [760, 440, 400, 200]  # x, y, w, h — inside the 1920x1080 frame, away from centred text


def _mean_luma(png, rect):
    x, y, w, h = rect
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', png, '-vf',
                        f'crop={w}:{h}:{x}:{y}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                       capture_output=True)
    assert r.returncode == 0, r.stderr[-300:]
    return sum(r.stdout) / max(1, len(r.stdout))


def test_ai_graphic_renders_at_its_word(tmp_path):
    if not (shutil.which('hyperframes') or os.environ.get('MP_HYPERFRAMES')):
        pytest.skip('hyperframes render toolchain not installed')
    pd = make_project(tmp_path / 'p')
    p = json.load(open(os.path.join(pd, 'project.json')))
    p['zones'] = [{'section': 'Welcome', 'rect': ZONE0}]
    json.dump(p, open(os.path.join(pd, 'project.json'), 'w'))
    tr = json.load(open(os.path.join(pd, 'transcript_model.json')))
    wid = next(w['id'] for w in tr['words'] if w['section'] == 'Welcome')  # first Welcome word
    ag = os.path.join(pd, 'ai_graphics')
    os.makedirs(ag)
    # white rect in zone 0, appearing exactly at the word's scene-relative start
    open(os.path.join(ag, 'rect.js'), 'w').write(
        "var r = MP.el('div', {position: 'absolute', background: '#ffffff'});\n"
        'MP.inZone(r, 0);\n'
        f"MP.tl.fromTo(r, {{opacity: 0}}, {{opacity: 1, duration: 0.1, delay: MP.at('{wid}')}});\n")
    json.dump({'graphics': [{'id': 'rect', 'file': 'rect.js', 'anchor': {'word': wid}, 'layer': 'above'}]},
              open(os.path.join(ag, 'manifest.json'), 'w'))
    generate.generate(pd)
    timing = json.load(open(os.path.join(pd, 'timing.json')))
    t_word = next(w['start'] for w in timing['words'] if w['id'] == wid)
    scenes = json.load(open(os.path.join(pd, 'src', 'scenes.json')))
    scene_start = next(s['start'] for s in scenes if s['name'] == 'Welcome')
    out = tmp_path / 'out'
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'), '--project', pd,
                        '--variant', 'default', '--mode', 'test', '--out', str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    frames = sorted(glob.glob(str(out / 'work_*' / 'frames' / 'frame_*.png')))
    assert frames, 'no frames rendered'
    fps = p['fps']
    t_rel = t_word - scene_start
    i_before = max(0, min(len(frames) - 1, int((t_rel - 0.4) * fps)))
    i_after = max(0, min(len(frames) - 1, int((t_rel + 0.4) * fps)))
    before, after = _mean_luma(frames[i_before], ZONE0), _mean_luma(frames[i_after], ZONE0)
    assert after > before + 40, f'zone-0 luma before {before:.1f} vs after {after:.1f} at {wid}'
