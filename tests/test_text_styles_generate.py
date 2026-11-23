"""Task 5 (0.8.0): generate.py consumes TextStyle — default byte-identical (golden), per-style
span granularity, typewriter determinism, and the zone gate reads the style's layout.

RED before the wiring: the zone test (one-word-center block vs a left zone -> check_zone must
exit 1; with the default layout it exits 0) and the typewriter data-k spans are absent.
"""
import glob
import json
import os
import subprocess

import pytest

from projfix import ROOT, make_project
from motion_pipeline import generate, project as project_mod, text_styles

VENV_PY = os.path.join(ROOT, '.venv', 'bin', 'python')
GOLDEN = os.path.join(ROOT, 'tests', 'fixtures', 'golden_slide_up')


def _gen(sub, style_name=None, zones=None):
    pd = make_project(str(sub / 'proj'))
    p = project_mod.load(pd)
    if style_name:
        p['text_style'] = style_name
    if zones is not None:
        p['zones'] = zones
    project_mod.save(pd, p)
    generate.generate(pd)
    src = os.path.join(pd, 'src')
    return pd, {os.path.basename(f): open(f).read()
                for f in sorted(glob.glob(os.path.join(src, 'scene_*.html')))}


def _t_ids(html):
    i = html.index('const T = ') + len('const T = ')
    obj, _ = json.JSONDecoder().raw_decode(html[i:])
    return set(obj.keys())


SPAN_ID = __import__('re').compile(r'<span [^>]*data-id="([^"]+)"')
SPAN_K = __import__('re').compile(r'data-k="(\d+)"')


def test_default_style_pages_byte_identical_to_golden(tmp_path):
    """Review focus 1: a default project renders exactly the 0.7.x page (golden fixture)."""
    _, pages = _gen(tmp_path)
    golden = {f: open(os.path.join(GOLDEN, f)).read()
              for f in os.listdir(GOLDEN) if f.startswith('scene_')}
    assert set(pages) == set(golden), (sorted(pages), sorted(golden))
    for name in pages:
        assert pages[name] == golden[name], f'{name}: default style output drifted from golden'


@pytest.mark.parametrize('name', sorted(text_styles.STYLES))
def test_every_style_spans_match_granularity(tmp_path, name):
    """Every word id in T is spanned; word styles exactly once, letter styles with data-k."""
    st = text_styles.STYLES[name]
    _, pages = _gen(tmp_path / name, style_name=name)
    assert pages, 'no scene pages generated'
    for page, html in pages.items():
        t_ids = _t_ids(html)
        span_ids = SPAN_ID.findall(html)
        assert span_ids and set(span_ids) == t_ids, (
            f'{name}/{page}: spans vs T mismatch: only-in-T={sorted(t_ids - set(span_ids))} '
            f'only-in-spans={sorted(set(span_ids) - t_ids)}')
        if st.granularity == 'word':
            assert len(span_ids) == len(set(span_ids)), f'{name}/{page}: word id spanned twice'
            assert 'data-k=' not in html
        else:
            ks = SPAN_K.findall(html)
            assert ks and len(ks) == len(span_ids), f'{name}/{page}: letter spans need data-k'


def test_typewriter_deterministic_with_fixed_seed(tmp_path):
    _, p1 = _gen(tmp_path / 'a', style_name='typewriter')
    _, p2 = _gen(tmp_path / 'b', style_name='typewriter')
    assert p1 == p2, 'typewriter pages must be byte-identical across generations (fixed seed)'
    assert any('MP.random(' in html for html in p1.values()), 'seeded PRNG expected in tween JS'


def _proj(sub, style_name, zones):
    """Build a saved project (no generate — check_zone recomputes the layout itself)."""
    pd = make_project(str(sub / 'proj'))
    p = project_mod.load(pd)
    p['text_style'] = style_name
    p['zones'] = zones
    project_mod.save(pd, p)
    return pd


def test_zone_gate_uses_style_layout(tmp_path):
    """One-word-center puts every word on its own line -> a tall narrow block at the left;
    a left-side zone overlaps it -> check_zone must exit 1. With the default layout the same
    zone is avoidable (the wide block moves up) -> exit 0 (the mutation goes RED)."""
    zone = {'section': 'Welcome', 'rect': [100, 500, 600, 400]}
    pd = _proj(tmp_path, 'one-word-center', [zone])
    r = subprocess.run([VENV_PY, os.path.join(ROOT, 'tools', 'check_zone.py'),
                        '--project', pd], capture_output=True, text=True)
    assert r.returncode == 1 and 'OFFENDER' in r.stdout, (r.returncode, r.stdout, r.stderr[-400:])
    # same project, default style: the wide block moves above the zone -> all clear
    pd2 = _proj(tmp_path / 'd', 'slide-up', [zone])
    r2 = subprocess.run([VENV_PY, os.path.join(ROOT, 'tools', 'check_zone.py'),
                         '--project', pd2], capture_output=True, text=True)
    assert r2.returncode == 0, (r2.returncode, r2.stdout, r2.stderr[-400:])
