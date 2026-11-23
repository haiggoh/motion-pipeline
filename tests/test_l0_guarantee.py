"""Task 2/5 (0.8.0): L0 guarantee — every word is tweened on its VO timing in every scene,
parametrized over every text style (Task 5).

For each generated scene page: the ids in `const T = {...}` (VO-relative word timings) must
equal the set of span data-ids, and the page's tween loop must cover every `.line span` by
looking it up in T (`T[el.dataset.id]`) — a span whose id is missing from T makes `t.start`
throw and kills the whole timeline. Word styles: exactly one span per word. Letter styles:
several spans per word, all carrying data-id = word id + data-k = letter index.
"""
import json
import os
import re

import pytest

from projfix import make_project
from motion_pipeline import generate, project, text_styles

SPAN_RE = re.compile(r'<span [^>]*data-id="([^"]+)"(?: data-k="(\d+)")?')


def _t_ids(html):
    marker = 'const T = '
    i = html.index(marker) + len(marker)
    obj, _ = json.JSONDecoder().raw_decode(html[i:])
    return set(obj.keys())


@pytest.mark.parametrize('style_name', sorted(text_styles.STYLES))
def test_every_word_tweened_every_scene(tmp_path, style_name):
    pd = make_project(str(tmp_path / 'proj'))
    p = project.load(pd)
    p['text_style'] = style_name
    project.save(pd, p)
    generate.generate(pd)
    st = text_styles.STYLES[style_name]
    src = os.path.join(pd, 'src')
    pages = sorted(f for f in os.listdir(src) if f.startswith('scene_') and f.endswith('.html'))
    assert pages, 'generator produced no scene pages'
    for page in pages:
        html = open(os.path.join(src, page)).read()
        t_ids = _t_ids(html)
        spans = SPAN_RE.findall(html)
        span_ids = [s[0] for s in spans]
        assert span_ids, f'{style_name}/{page}: no word spans emitted'
        assert set(span_ids) == t_ids, (
            f'{style_name}/{page}: spans vs T mismatch — only in T: {sorted(t_ids - set(span_ids))}, '
            f'only on spans: {sorted(set(span_ids) - t_ids)}')
        if st.granularity == 'word':
            assert len(span_ids) == len(set(span_ids)), f'{style_name}/{page}: a word id got two spans'
            assert not any(s[1] for s in spans), 'word style must not emit data-k'
        else:
            assert all(s[1] for s in spans), f'{style_name}/{page}: letter spans must carry data-k'
        # the tween loop must cover the style's spans and time them from T
        sel = re.search(r"querySelectorAll\('([^']+)'", html)
        expect = '.line span' if "'.line span'" in st.tween_js() else '.line'
        assert sel and sel.group(1) == expect, f'{style_name}/{page}: loop selector {sel and sel.group(1)}'
        assert 'T[' in html and '.dataset.id' in html, f'{style_name}/{page}: loop must read T[...dataset.id]'
