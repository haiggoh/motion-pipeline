"""Task 8 tests: generator output — word-id anchoring, emphasis, section cards,
per-aspect bounds, zone routing, DE hyphenation, element ids, ai_graphics isolation."""
import json
import os
import re

import pytest

from motion_pipeline import align, generate, project, transcript
from motion_pipeline.scheme import save_scheme

DARK = {'name': 'default', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}
TR_TEXT = '# Intro\nThe *quick* brown fox jumps over.\n\n# Main\nDie lange Silbentrennung funktioniert.\n'


def make_project(tmp_path, aspect='16:9', fps=60, res=None, zones=None, name='gen'):
    d = tmp_path / 'projects' / name
    d.mkdir(parents=True)
    p = project.default_project(name, aspect=aspect, fps=fps)
    if res:
        p['resolution'] = res
    if zones is not None:
        p['zones'] = zones
    p['fonts'] = {'family': 'Montserrat'}
    project.save(str(d), p)
    save_scheme(str(d / 'scheme.json'), DARK)
    tr = transcript.parse(TR_TEXT)
    (d / 'transcript_model.json').write_text(json.dumps(tr))
    timing = align.estimate_timings(tr, wpm=140)
    align.save_timing(str(d / 'timing.json'), timing)
    (d / 'ai_graphics').mkdir(exist_ok=True)
    (d / 'ai_graphics' / 'marker.txt').write_text('ai-owned\n')
    return str(d), tr, timing


@pytest.fixture
def d(tmp_path):
    return make_project(tmp_path)


def read_scene(d, section):
    return (open(os.path.join(d, 'src', f'scene_{section}.html')).read())


def test_every_word_id_and_section_in_output(d):
    d, tr, timing = d
    generate.generate(d)
    intro = read_scene(d, 'Intro')
    for w in [w for w in tr['words'] if w['section'] == 'Intro']:
        assert f'data-id="{w["id"]}"' in intro
        assert f'"{w["id"]}":' in intro  # timing anchored by id
    assert 'card-Intro' in intro
    main = read_scene(d, 'Main')
    assert 'card-Main' in main
    ids = json.load(open(os.path.join(d, 'src', 'element_ids.json')))
    assert set(ids) >= {w['id'] for w in tr['words']} | {'Intro', 'Main'}


def test_reveal_onset_equals_word_start(d):
    d, tr, timing = d
    generate.generate(d)
    intro = read_scene(d, 'Intro')
    tmap = {w['id']: w for w in timing['words']}
    emb = json.loads(re.search(r'const T = (\{.*?\});', intro, re.S).group(1))
    for wid, t in emb.items():
        assert t['start'] == tmap[wid]['start']
        assert t['end'] == tmap[wid]['end']
    assert 'delay: t.start' in intro


def test_emphasis_words_heavier(d):
    d, tr, timing = d
    generate.generate(d)
    intro = read_scene(d, 'Intro')
    assert re.search(r'data-id="w1" class="emph"', intro)  # *quick*


def test_per_aspect_bounds_and_zone_routing(tmp_path):
    for aspect, res in project.ASPECTS.items():
        zones = [{'section': 'Intro', 'rect': [int(res[0] * 0.05), int(res[1] * 0.5),
                                               int(res[0] * 0.9), int(res[1] * 0.45)]}]
        d, tr, timing = make_project(tmp_path / aspect.replace(':', '-'), aspect=aspect, zones=zones)
        generate.generate(d)
        intro = read_scene(d, 'Intro')
        # every .line box must be inside the frame and outside the zone rect
        for m in re.finditer(r'class="line" style="left:(\d+)px;top:(\d+)px;font-size:(\d+)px', intro):
            x, y, fs = int(m.group(1)), int(m.group(2)), int(m.group(3))
            assert 0 <= x < res[0] and 0 <= y < res[1], (aspect, x, y)
            block = (x, y, int(res[0] * 0.84), fs * 1.25)
            zx, zy, zw, zh = zones[0]['rect']
            assert not (block[0] < zx + zw and block[0] + block[2] > zx and
                        block[1] < zy + zh and block[1] + block[3] > zy), (aspect, block, zones[0]['rect'])


def test_uhd_and_25fps_project_settings(tmp_path):
    d, tr, timing = make_project(tmp_path / 'uhd', aspect='16:9', fps=25, res=[3840, 2160])
    generate.generate(d)
    assert os.path.isfile(os.path.join(d, 'src', 'scene_Intro.html'))


def test_german_hyphenation(d):
    d, tr, timing = d
    from motion_pipeline.generate import hyphenate
    parts = hyphenate('Silbentrennung', 8)
    assert parts[0].endswith('-') and len(parts[0]) <= 8
    assert ''.join(parts).replace('-', '') == 'Silbentrennung'


def test_regenerate_leaves_ai_graphics_untouched(d):
    d, tr, timing = d
    generate.generate(d)
    before = (open(os.path.join(d, 'ai_graphics', 'marker.txt')).read())
    generate.generate(d)
    after = (open(os.path.join(d, 'ai_graphics', 'marker.txt')).read())
    assert before == after == 'ai-owned\n'
