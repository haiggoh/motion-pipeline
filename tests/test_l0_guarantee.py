"""Task 2 (0.8.0 plan): L0 guarantee — every word is tweened on its VO timing in every scene.

For each generated scene page: the ids in `const T = {...}` (VO-relative word timings) must
equal the set of span data-ids, each word exactly one span, and the page's tween loop must
cover every `.line span` by looking it up in T (`T[el.dataset.id]`) — a span whose id is
missing from T makes `t.start` throw and kills the whole timeline. Task 5 parametrizes
this over every text style.
"""
import json
import os
import re

from projfix import make_project
from motion_pipeline import generate

SPAN_RE = re.compile(r'<span [^>]*data-id="([^"]+)"')


def _t_ids(html):
    marker = 'const T = '
    i = html.index(marker) + len(marker)
    obj, _ = json.JSONDecoder().raw_decode(html[i:])
    return set(obj.keys())


def test_every_word_tweened_every_scene(tmp_path):
    pd = make_project(str(tmp_path / 'proj'))
    generate.generate(pd)
    src = os.path.join(pd, 'src')
    pages = sorted(f for f in os.listdir(src) if f.startswith('scene_') and f.endswith('.html'))
    assert pages, 'generator produced no scene pages'
    for page in pages:
        html = open(os.path.join(src, page)).read()
        t_ids = _t_ids(html)
        span_ids = SPAN_RE.findall(html)
        assert span_ids, f'{page}: no word spans emitted'
        assert len(span_ids) == len(set(span_ids)), f'{page}: a word id got more than one span'
        assert set(span_ids) == t_ids, (
            f'{page}: spans vs T mismatch — only in T: {sorted(t_ids - set(span_ids))}, '
            f'only on spans: {sorted(set(span_ids) - t_ids)}')
        # the tween loop must cover every .line span and time it from T
        assert "document.querySelectorAll('.line span')" in html, page
        assert 'T[el.dataset.id]' in html, page
