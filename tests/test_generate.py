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
    # Task 12: scene files are scene_<NN>_<slug>.html — resolve via scenes.json
    scenes = json.load(open(os.path.join(d, 'src', 'scenes.json')))
    name = next(s['file'] for s in scenes if s['name'] == section)
    return open(os.path.join(d, 'src', name)).read()


def test_page_declares_font_face_per_role(d):
    """Task 11: every role's face is embedded via an mp-<role> @font-face alias + loaded in the page."""
    d, tr, timing = d
    generate.generate(d)
    html = read_scene(d, 'Intro')
    for role in ('headline', 'label', 'body', 'emphasis'):
        assert f"font-family:'mp-{role}'" in html, role
        assert f"src:url('fonts/{role}-" in html, role
    assert "document.fonts.load" in html and 'MP_FONT_MISSING' in html  # the page-side gate
    assert "font-family:'mp-body'" in html  # alias used, not the raw family name (P6)


def test_fonts_copied_into_src(d):
    """Task 11: each role's face file lands in src/fonts/<role>-<basename>."""
    d, tr, timing = d
    generate.generate(d)
    fonts_dir = os.path.join(d, 'src', 'fonts')
    names = os.listdir(fonts_dir)
    for role in ('headline', 'label', 'body', 'emphasis'):
        assert any(n.startswith(role + '-') for n in names), (role, names)


def test_every_word_id_and_section_in_output(d):
    d, tr, timing = d
    generate.generate(d)
    intro = read_scene(d, 'Intro')
    for w in [w for w in tr['words'] if w['section'] == 'Intro']:
        assert f'data-id="{w["id"]}"' in intro
        assert f'"{w["id"]}":' in intro  # timing anchored by id
    assert 'card-intro' in intro  # Task 12: card ids come from slugs
    main = read_scene(d, 'Main')
    assert 'card-main' in main  # Task 12: card ids come from slugs
    ids = json.load(open(os.path.join(d, 'src', 'element_ids.json')))
    assert set(ids) >= {w['id'] for w in tr['words']} | {'Intro', 'Main'}


def test_reveal_onset_equals_word_start(d):
    d, tr, timing = d
    generate.generate(d)
    intro = read_scene(d, 'Intro')
    tmap = {w['id']: w for w in timing['words']}
    emb = json.loads(re.search(r'const T = (\{.*?\});', intro, re.DOTALL).group(1))
    for wid, t in emb.items():
        assert t['start'] == tmap[wid]['start']
        assert t['end'] == tmap[wid]['end']
    assert '}, t.start);' in intro  # 0.8.5 L0: word tweens at explicit absolute positions


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
    scenes = json.load(open(os.path.join(d, 'src', 'scenes.json')))
    assert os.path.isfile(os.path.join(d, 'src', scenes[0]['file']))


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


def test_generate_without_fonts_falls_back_to_bundled_default(tmp_path, capsys):
    """2026-11-22 user report: a project with fonts:{} must render, not error. The gate stays
    strict for Save; the render path falls back to a bundled family with a printed note."""
    import shutil as _sh

    from projfix import DARK

    from motion_pipeline import project
    from motion_pipeline.scheme import save_scheme
    d = str(tmp_path / 'p')
    _sh.copytree('samples/globe', d, dirs_exist_ok=True)
    p = project.default_project('demo')
    p['fonts'] = {}                      # no fonts configured — the user's case
    project.save(d, p)
    save_scheme(os.path.join(d, 'scheme.json'), DARK)
    from motion_pipeline import align, transcript
    tr = transcript.load(os.path.join(d, 'transcript.txt'))
    open(os.path.join(d, 'transcript_model.json'), 'w').write(json.dumps(tr))
    align.save_timing(os.path.join(d, 'timing.json'), align.estimate_timings(tr, wpm=140))
    from motion_pipeline import generate
    generate.generate(d)                 # must not raise
    out = capsys.readouterr().out
    assert 'no fonts config' in out and 'Montserrat' in out, out
    assert os.path.isdir(os.path.join(d, 'src', 'fonts'))
