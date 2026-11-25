"""Task 6c/6d (D1'/D2/D3/D4/D7): pagination — a chapter that cannot fit one frame splits into
pages '<chapter> 1..N', planned by motion_pipeline/paginate.plan_pages and shared by generate
and tools/check_zone.py. Byte-identity (D2): a chapter that fits is ONE page with its own
name and no new scenes.json fields. 6d: the single heading-less 'default' chapter with >= 3
pages is grouped into topic chapters (D7) recorded in scenes.json 'chapter' ('root' keeps
the transcript chapter; its zones still apply to all pages).
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter

import pytest
from docx_fixture import build_docx
from projfix import ROOT, make_project
from test_scenes import mk, scenes_json

from motion_pipeline import generate, paginate, project, text_styles


def _long_text(n_sentences=60, monster=False):
    parts = [f'Sentence number {i} has six short words here.' for i in range(n_sentences)]
    if monster:
        parts.append('A monster sentence, with many clauses, and commas, keeps going, '
                     'and going, and going, and going, and going, and going, and going, '
                     'and going, and going, and going, and going, and going, and going, '
                     'and going, and going, and going, and going, and going, and going, '
                     'and going, and going, and going, and going, and going, and going, '
                     'and going, and going, and going, and going, and going, and going.')
    return ' '.join(parts) + '\n'


def test_oversized_chapter_paginates_and_fits_at_base(tmp_path):
    """RED on 0.8.2: a heading-less ~400-word transcript raised 'does not fit one frame'.
    Now generate succeeds with N >= 2 pages, each fitting at the BASE font, no word lost or
    duplicated (page word ids concatenate to the original order)."""
    d, tr, timing = mk(tmp_path / 'p', _long_text(60))
    generate.generate(d)                      # must not raise
    scenes = scenes_json(d)
    assert len(scenes) >= 2, scenes
    assert all(s.get('chapter') == 'default' for s in scenes)
    assert [s['name'] for s in scenes] == [f'default {i + 1}' for i in range(len(scenes))]
    ids = [w['id'] for s in scenes for w in _page_words(d, s)]
    assert ids == [w['id'] for w in tr['words']], 'words lost/duplicated/reordered'
    # every page fits at the BASE font (no shrink), avoiding the chapter's zones
    style = text_styles.STYLES['slide-up']
    W, H = 1920, 1080
    font_px = int(H / 12)
    zs = [z for z in project.active_zones(project.load(d)) if z['section'] == 'default']
    for s in scenes:
        ws = _page_words(d, s)
        lines = style.layout(ws, max(8, int(W * 0.84 / (font_px * 0.52))), font_px)
        assert generate._avoids_zones(lines, W, H, font_px, int(font_px * 1.25), zs), s['name']


def _page_words(d, scene):
    tr = json.load(open(os.path.join(d, 'transcript_model.json')))
    by_id = {w['id']: w for w in tr['words']}
    first, last = scene['words']
    ids = [w['id'] for w in tr['words']]
    return [by_id[wid] for wid in ids[ids.index(first):ids.index(last) + 1]]


def test_pages_break_at_sentence_ends(tmp_path):
    """D3: greedy packing splits at whole sentences — with only short sentences, every page
    ends at a sentence end."""
    d, tr, timing = mk(tmp_path / 'p', _long_text(60))
    generate.generate(d)
    for s in scenes_json(d):
        ws = _page_words(d, s)
        assert ws[-1]['text'][-1:] in paginate.SENT_END, (s['name'], ws[-1]['text'])


def test_monster_sentence_splits_at_clause_punctuation(tmp_path):
    """D3: a single sentence too big for one page splits at a clause punctuation mark.
    (60 short sentences + a 100-word monster: ~460 words exceed even the shrunk floor, so
    the chapter paginates at the base font.)"""
    d, tr, timing = mk(tmp_path / 'p', _long_text(60, monster=True))
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(scenes) >= 3
    last_words = [_page_words(d, s)[-1]['text'] for s in scenes]
    assert any(w[-1:] in paginate.CLAUSE_PUNCT for w in last_words[:-1]), last_words


def test_fitting_chapter_stays_one_page_byte_identical_shape(tmp_path):
    """D2: a chapter that fits is one page named exactly the chapter, with NO new scenes.json
    fields (golden byte-identity)."""
    d, tr, timing = mk(tmp_path / 'p', '# Zeta\nalpha beta gamma\n\n# Alpha\ndelta epsilon zeta\n')
    generate.generate(d)
    scenes = scenes_json(d)
    assert [s['name'] for s in scenes] == ['Zeta', 'Alpha']
    for s in scenes:
        assert set(s.keys()) == {'index', 'name', 'slug', 'start', 'end', 'file'}, s


def test_unfittable_still_raises_naming_chapter(tmp_path):
    """A zone covering the whole frame: even single-word pages cannot fit -> the legacy
    error, naming the chapter."""
    d, tr, timing = mk(tmp_path / 'p', '# S\nhello world\n',
                       zones=[{'section': 'S', 'rect': [0, 0, 1920, 1080], 'aspect': '16:9'}])
    with pytest.raises(ValueError, match='section "S" does not fit one frame at 16:9'):
        generate.generate(d)


def _assert_pages_avoid_zone(d, scenes, zone_rect):
    """Every generated page's rendered text block stays clear of the zone rect."""
    zx, zy, zw, zh = zone_rect
    style = text_styles.STYLES[project.load(d).get('text_style', text_styles.DEFAULT)]
    for s in scenes:
        html = open(os.path.join(d, 'src', s['file'])).read()
        boxes = re.findall(r'class="line"[^>]*style="left:(\d+)px;top:(\d+)px;font-size:(\d+)px', html)
        assert boxes, s['name']
        ws = _page_words(d, s)
        fs = int(boxes[0][2])
        lines = style.layout(ws, max(8, int(1920 * 0.84 / (fs * 0.52))), fs)
        max_w = max(len(''.join(pc for _, pc, _ in ln)) for ln in lines)
        assert len(boxes) == len(lines), (s['name'], len(boxes), len(lines))
        x, y = int(boxes[0][0]), int(boxes[0][1])   # the block origin (first line)
        block = (x, y, int(max_w * fs * 0.52), len(lines) * int(fs * 1.25))
        assert not (block[0] < zx + zw and block[0] + block[2] > zx
                    and block[1] < zy + zh and block[1] + block[3] > zy), (s['name'], block)


def test_pages_avoid_chapter_zones(tmp_path):
    """D1' delivery-level: a chapter's zones apply to ALL its pages — every rendered text
    block of every page stays clear of the chapter zone rect."""
    zone = {'section': 'default', 'rect': [100, 700, 1700, 300], 'aspect': '16:9'}
    d, tr, timing = mk(tmp_path / 'p', _long_text(60), zones=[zone])
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(scenes) >= 2
    _assert_pages_avoid_zone(d, scenes, zone['rect'])


@pytest.mark.parametrize('style_name', ['slide-up', 'one-word-center'])
def test_check_zone_agrees_with_generate_pages(tmp_path, style_name, monkeypatch):
    """D4 end-to-end: tools/check_zone.py plans the SAME pages as generate — spy on the
    plan_pages call the gate makes and assert it used the project's style and produced
    exactly the word-id ranges in scenes.json. A gate that forced the default layout goes
    RED on the one-word-center case (different plan) or the style assertion."""
    import tools.check_zone as cz
    d, tr, timing = mk(tmp_path / 'p', _long_text(60),
                       zones=[{'section': 'default', 'rect': [100, 700, 1700, 300], 'aspect': '16:9'}])
    p = project.load(d)
    p['text_style'] = style_name
    project.save(d, p)
    generate.generate(d)
    gen_ids = [[w['id'] for w in _page_words(d, s)] for s in scenes_json(d)]
    recorded = {}
    real_plan = paginate.plan_pages

    def spy(chapter, words, style, W, H, font_px, zones, aspect, taken):
        recorded['style'] = style
        pages = real_plan(chapter, words, style, W, H, font_px, zones, aspect, taken)
        recorded['ids'] = [[w['id'] for w in pg['words']] for pg in pages]
        return pages

    monkeypatch.setattr(cz.paginate, 'plan_pages', spy)
    assert cz.main(['--project', d]) == 0
    assert recorded['style'] is text_styles.STYLES[style_name]
    assert recorded['ids'] == gen_ids


def test_plan_pages_unit_split_points():
    """Unit: sentence chunking and the D3 clause-preferred split point."""
    words = [{'id': f'w{i}', 'text': t, 'section': 'default', 'emphasized': False, 'line': 1}
             for i, t in enumerate(['One.', 'Two,', 'three.', 'Four;', 'five.'])]
    chunks = paginate._sentence_chunks(words)
    assert [[w['text'] for w in c] for c in chunks] == [['One.'], ['Two,', 'three.'],
                                                        ['Four;', 'five.']]
    # clause boundary is preferred over the word boundary nearest the middle: chunk of 6
    # words with a clause mark after word 1 (k=2) -> mid = 3, but k must be EXACTLY 2
    # (a word-first candidate order would return 3)
    chunk = [{'id': f'w{i}', 'text': f'word{i},' if i == 1 else f'word{i}', 'section': 'd',
              'emphasized': False, 'line': 1} for i in range(6)]
    style = text_styles.STYLES['slide-up']
    assert paginate._split_point(chunk, style, 1920, 1080, 90, []) == 2
    # em-dash is a clause mark too
    chunk2 = [{'id': f'w{i}', 'text': f'word{i}—' if i == 1 else f'word{i}', 'section': 'd',
               'emphasized': False, 'line': 1} for i in range(6)]
    assert paginate._split_point(chunk2, style, 1920, 1080, 90, []) == 2
    # clause mark exactly at the middle -> k == 3
    chunk3 = [{'id': f'w{i}', 'text': f'word{i},' if i == 2 else f'word{i}', 'section': 'd',
               'emphasized': False, 'line': 1} for i in range(6)]
    assert paginate._split_point(chunk3, style, 1920, 1080, 90, []) == 3
    # a chunk that fits nowhere yields None (single word cannot be placed)
    assert paginate._split_point(chunk, style, 200, 100, 90, []) is None


def test_sentence_chunks_break_at_paragraph_gap():
    """D3: a chunk also breaks at a paragraph gap (line jump >= 2)."""
    words = [{'id': 'w0', 'text': 'alpha', 'section': 'd', 'emphasized': False, 'line': 1},
             {'id': 'w1', 'text': 'beta', 'section': 'd', 'emphasized': False, 'line': 1},
             {'id': 'w2', 'text': 'gamma', 'section': 'd', 'emphasized': False, 'line': 3},
             {'id': 'w3', 'text': 'delta', 'section': 'd', 'emphasized': False, 'line': 3}]
    chunks = paginate._sentence_chunks(words)
    assert [[w['id'] for w in c] for c in chunks] == [['w0', 'w1'], ['w2', 'w3']]


TOPIC_A = ' '.join(f'Alpha briefing sentence {i} covers rockets orbits and fuel systems.'
                   for i in range(30))
TOPIC_B = ' '.join(f'Beta kitchen note {i} covers recipes baking bread and ovens.'
                   for i in range(30))


def test_topic_chapters_split_two_topics(tmp_path):
    """D7: two clearly different topics, no headings -> the paginated 'default' chapter is
    grouped into 2 topic chapters at the page boundary between them, each >= 2 pages,
    recorded in scenes.json 'chapter' with 'root' = 'default'."""
    d, tr, timing = mk(tmp_path / 'p', TOPIC_A + ' ' + TOPIC_B + '\n')
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(scenes) >= 3, len(scenes)
    assert all(s.get('root') == 'default' for s in scenes)
    counts = Counter(s['chapter'] for s in scenes)
    assert len(counts) == 2, counts
    assert all(c >= 2 for c in counts.values()), counts   # min 2 pages per chapter
    # the split is at the A/B boundary: the first page containing B-words starts topic B
    b_pages = [s for s in scenes
               if any(t in ('recipes', 'kitchens', 'baking') for w in _page_words(d, s)
                      for t in w['text'].lower().split())]
    assert b_pages and b_pages[0]['chapter'] != scenes[0]['chapter']
    # SECTIONS in the page JS maps page names, topic names AND the root chapter — and a
    # chapter/topic maps to its FIRST page's start (value, not just presence)
    html = open(os.path.join(d, 'src', scenes[0]['file'])).read()
    smap = json.loads(re.search(r'const SECTIONS = (\{.*?\});', html).group(1))
    assert scenes[0]['name'] in smap and 'default' in smap
    base = scenes[0]['start']
    for s in scenes:
        assert smap[s['name']] == round(s['start'] - base, 3), s['name']
        for key in ('chapter', 'root'):
            if s.get(key):
                first = next(x for x in scenes if x.get(key) == s[key])
                assert smap[s[key]] == round(first['start'] - base, 3), (s[key], smap[s[key]])


def test_topic_chapters_uniform_text_stays_single(tmp_path):
    """D7: uniform text -> no cohesion dip -> ONE chapter, recorded as 'default' (source
    'single'), root 'default'."""
    d, tr, timing = mk(tmp_path / 'p', _long_text(60))
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(scenes) >= 3
    assert all(s['chapter'] == 'default' and s.get('root') == 'default' for s in scenes), scenes


def test_zones_of_default_apply_to_topic_pages(tmp_path):
    """D1'+D7: a zone anchored to 'default' applies to every page of every topic chapter."""
    zone = {'section': 'default', 'rect': [100, 700, 1700, 300], 'aspect': '16:9'}
    d, tr, timing = mk(tmp_path / 'p', TOPIC_A + ' ' + TOPIC_B + '\n', zones=[zone])
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(Counter(s['chapter'] for s in scenes)) == 2
    _assert_pages_avoid_zone(d, scenes, zone['rect'])


def test_topic_chapters_unit():
    """Unit: disjoint vocabularies -> 2 groups; shared vocabulary -> 1 group."""
    def pg(text):
        return {'words': [{'id': f'w{i}', 'text': t, 'section': 'default',
                           'emphasized': False, 'line': 1}
                          for i, t in enumerate(text.split())]}
    a = [pg(f'Alpha rockets orbits fuel {i} mission control launch.') for i in range(4)]
    b = [pg(f'Beta recipes baking bread ovens kitchen {i} dinner party.') for i in range(4)]
    names = paginate.topic_chapters('default', a + b)
    assert len(set(names)) == 2 and len(names) == 8, names
    uni = [pg('Same words repeat here every single page today.') for _ in range(5)]
    assert len(set(paginate.topic_chapters('default', uni))) == 1


def test_topic_chapters_min_two_pages_per_chapter():
    """D7 min-2-pages: a single oddball page between two topic blocks must be merged into a
    neighbouring topic, never form a 1-page chapter (RED when the guard is deleted)."""
    def pg(text):
        return {'words': [{'id': f'w{i}', 'text': t, 'section': 'default',
                           'emphasized': False, 'line': 1}
                          for i, t in enumerate(text.split())]}
    a = [pg('Alpha rockets orbits fuel mission control launch.') for _ in range(2)]
    odd = [pg('Zebra xylophone quixotic jazz vibes tonight.')]
    b = [pg('Beta recipes baking bread ovens kitchen dinner.') for _ in range(3)]
    names = paginate.topic_chapters('default', a + odd + b)
    counts = Counter(names)
    assert len(counts) == 2 and all(c >= 2 for c in counts.values()), counts


def test_topic_chapters_deterministic():
    """D7: same input -> identical output (tie-breaks included)."""
    def pg(text):
        return {'words': [{'id': f'w{i}', 'text': t, 'section': 'default',
                           'emphasized': False, 'line': 1}
                          for i, t in enumerate(text.split())]}
    pages = [pg(f'Alpha rockets orbits fuel mission {i}.') for i in range(3)] + \
            [pg(f'Beta recipes baking bread ovens {i}.') for i in range(3)]
    assert paginate.topic_chapters('default', pages) == paginate.topic_chapters('default', pages)


def test_fits_only_after_shrink_stays_one_page(tmp_path):
    """D2: a chapter that fits only after the legacy shrink loop stays ONE page with the
    shrunk font (RED if the legacy loop is deleted and it paginates at base instead)."""
    d, tr, timing = mk(tmp_path / 'p', '# S\n' + 'wort ' * 120 + '\n')
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(scenes) == 1 and scenes[0]['name'] == 'S', scenes
    assert set(scenes[0].keys()) == {'index', 'name', 'slug', 'start', 'end', 'file'}
    html = open(os.path.join(d, 'src', scenes[0]['file'])).read()
    fs = int(re.search(r'class="line"[^>]*font-size:(\d+)px', html).group(1))
    assert fs < 90, fs   # shrunk below the 16:9 base font


def test_topic_chapters_only_for_headingless_default(tmp_path):
    """D7 'default only': a NAMED chapter (# Overview) with two topics and >= 3 pages is NOT
    topic-grouped — its pages keep chapter == 'Overview' (RED if the guard is deleted)."""
    d, tr, timing = mk(tmp_path / 'p', '# Overview\n' + TOPIC_A + ' ' + TOPIC_B + '\n')
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(scenes) >= 3, len(scenes)
    assert all(s.get('root') == 'Overview' and s['chapter'] == 'Overview' for s in scenes), \
        [s.get('chapter') for s in scenes]


def test_ai_graphics_anchored_to_page_and_chapter(tmp_path):
    """D1'/6e delivery: a paginated project + manifest with a graphic anchored to page
    'default 2' lands in exactly that page's HTML; one anchored to chapter 'default' lands in
    EVERY page's HTML."""
    d, tr, timing = mk(tmp_path / 'p', _long_text(60))
    ag = os.path.join(d, 'ai_graphics')
    os.makedirs(ag)
    open(os.path.join(ag, 'page.html'), 'w').write('<div id="pageg"></div>')
    open(os.path.join(ag, 'chap.html'), 'w').write('<div id="chapg"></div>')
    with open(os.path.join(ag, 'manifest.json'), 'w') as f:
        json.dump({'graphics': [
            {'id': 'pageg', 'file': 'page.html', 'anchor': {'section': 'default 2'},
             'layer': 'above'},
            {'id': 'chapg', 'file': 'chap.html', 'anchor': {'section': 'default'},
             'layer': 'above'},
        ]}, f)
    generate.generate(d)
    scenes = scenes_json(d)
    assert len(scenes) >= 2
    per_page = {}
    for s in scenes:
        html = open(os.path.join(d, 'src', s['file'])).read()
        per_page[s['name']] = ('data-ai-id="pageg"' in html, 'data-ai-id="chapg"' in html)
    assert per_page['default 2'] == (True, True)
    assert per_page['default 1'] == (False, True)
    assert all(chap for _, chap in per_page.values())   # chapter graphic on EVERY page


def test_delivery_prepare_only_docx_chapters_and_pages(tmp_path):
    """Shipped path (0.8.3 delivery test): a synthetic project whose transcript is a .docx —
    one Heading1 chapter + a 400-word body — run through the REAL CLI
    `render_cli --prepare-only` exits 0, and src/scenes.json lists > 1 page of that chapter
    (root 'Overview'), i.e. the docx chapters flow through with no manual step."""
    pd = make_project(str(tmp_path / 'proj'))
    p = project.load(pd)
    build_docx(os.path.join(pd, 'transcript.docx'),
               [{'text': 'Overview', 'style': 'Heading1'},
                {'text': _long_text(60)}])
    p['transcript'] = 'transcript.docx'
    project.save(pd, p)
    env = dict(os.environ, PYTHONPATH=ROOT)
    r = subprocess.run([sys.executable, '-m', 'motion_pipeline.render_cli',
                        '--project', pd, '--prepare-only'],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0, (r.returncode, r.stdout[-300:], r.stderr[-500:])
    scenes = scenes_json(pd)
    assert len(scenes) > 1, scenes
    assert all(s.get('root') == 'Overview' and s['chapter'] == 'Overview' for s in scenes), scenes
    assert [s['name'] for s in scenes] == [f'Overview {i + 1}' for i in range(len(scenes))]
    ch, pg, src = project.chapter_page_counts(pd)
    assert (ch, pg, src) == (1, len(scenes), 'heading'), (ch, pg, src)


def test_ai_layer_accepts_chapter_and_page_names(tmp_path):
    """D1'/6e: ai_layer validation accepts chapter AND page names (extra_names); unknown
    names still raise."""
    from motion_pipeline import ai_layer
    d = str(tmp_path / 'proj')
    os.makedirs(os.path.join(d, 'ai_graphics'))
    open(os.path.join(d, 'ai_graphics', 'g.html'), 'w').write('<div></div>')
    words = [{'id': 'w0', 'text': 'hello', 'section': 'default', 'emphasized': False}]

    def manifest(section):
        return {'graphics': [{'id': 'g1', 'file': 'g.html',
                              'anchor': {'section': section}, 'layer': 'above'}]}

    with open(os.path.join(d, 'ai_graphics', 'manifest.json'), 'w') as f:
        json.dump(manifest('default 2'), f)
    with pytest.raises(ValueError, match='unknown section'):
        ai_layer.load_manifest(d, words)                      # page name not yet known
    entries = ai_layer.load_manifest(d, words, extra_names=['default 1', 'default 2'])
    assert entries[0]['section'] == 'default 2'
    with open(os.path.join(d, 'ai_graphics', 'manifest.json'), 'w') as f:
        json.dump(manifest('nope'), f)
    with pytest.raises(ValueError, match='unknown section'):
        ai_layer.load_manifest(d, words, extra_names=['default 2'])
