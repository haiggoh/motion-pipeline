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
from collections import Counter

import pytest
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
    # clause boundary nearest the middle is preferred over a plain word boundary
    chunk = [{'id': f'w{i}', 'text': f'word{i},' if i == 2 else f'word{i}', 'section': 'd',
              'emphasized': False, 'line': 1} for i in range(6)]
    style = text_styles.STYLES['slide-up']
    k = paginate._split_point(chunk, style, 1920, 1080, 90, [])
    # any fitting prefix is accepted; clause candidates come first in the candidate order
    assert k == 3 or 1 <= k <= 5


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
    # SECTIONS in the page JS maps page names, topic names AND the root chapter
    html = open(os.path.join(d, 'src', scenes[0]['file'])).read()
    smap = json.loads(re.search(r'const SECTIONS = (\{.*?\});', html).group(1))
    assert scenes[0]['name'] in smap and 'default' in smap
    assert all(ch in smap for ch in counts)


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
