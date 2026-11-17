"""Task 12 tests (plan 2026-11-16): scene model — spans, order, slugs, escaping, timeline
registration, dimming, hyphenation piece ids, fit, scenes.json, native-resolution dry-run."""
import json
import os
import re
import subprocess

import pytest

from motion_pipeline import align, generate, project, transcript
from motion_pipeline.scheme import save_scheme

DARK = {'name': 'default', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}


def mk(d, tr_text, aspect='16:9', fps=25, res=None, zones=None):
    d = str(d)
    p = project.default_project('gen', aspect=aspect, fps=fps)
    if res:
        p['resolution'] = res
    if zones is not None:
        p['zones'] = zones
    p['fonts'] = {'family': 'Montserrat'}
    project.save(d, p)
    save_scheme(os.path.join(d, 'scheme.json'), DARK)
    tr = transcript.parse(tr_text)
    with open(os.path.join(d, 'transcript_model.json'), 'w') as f:
        json.dump(tr, f)
    timing = align.estimate_timings(tr, wpm=140)
    align.save_timing(os.path.join(d, 'timing.json'), timing)
    return d, tr, timing


def pages(d):
    src = os.path.join(d, 'src')
    return {f: open(os.path.join(src, f)).read() for f in sorted(os.listdir(src))
            if f.endswith('.html')}


def scenes_json(d):
    return json.load(open(os.path.join(d, 'src', 'scenes.json')))


TR2 = '# Zeta\nalpha beta gamma\n\n# Alpha\ndelta epsilon zeta\n'


def test_scene_timing_is_section_relative(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', TR2)
    generate.generate(d)
    scenes = scenes_json(d)
    assert [s['name'] for s in scenes] == ['Zeta', 'Alpha']
    s1 = scenes[1]
    html = pages(d)['scene_01_alpha.html']
    emb = json.loads(re.search(r'const T = (\{.*?\});', html, re.S).group(1))
    first_word = tr['words'][[w['section'] for w in tr['words']].index('Alpha')]['id']
    assert abs(emb[first_word]['start']) < 1 / 25, '2nd scene first word starts at ~0 (scene-relative)'
    root = re.search(r'data-duration="([\d.]+)"', html).group(1)
    assert abs(float(root) - (s1['end'] - s1['start'])) < 1e-3


def test_scenes_json_in_transcript_order(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', TR2)
    generate.generate(d)
    files = [s['file'] for s in scenes_json(d)]
    assert files == ['scene_00_zeta.html', 'scene_01_alpha.html'], files  # glob order = order


def test_section_names_are_escaped_and_slugged(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', '# Über uns & mehr\na/b "q" words\n')
    generate.generate(d)
    files = [s['file'] for s in scenes_json(d)]
    assert files == ['scene_00_uber-uns-mehr.html'], files
    html = pages(d)[files[0]]
    assert 'Über uns &amp; mehr' in html  # escaped in the card
    assert 'a/b' in html and '&quot;q&quot;' in html  # words html-escaped
    assert 'data-composition-id="uber-uns-mehr"' in html  # ids only from slugs


def test_words_before_first_heading_kept(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', 'leading words here\n# Real\nbody words\n')
    generate.generate(d)
    scenes = scenes_json(d)
    assert scenes[0]['name'] == 'Intro', scenes
    assert any(w['section'] == 'Intro' for w in tr['words'])
    assert os.path.isfile(os.path.join(d, 'src', scenes[0]['file']))


def test_duplicate_section_name_refused():
    with pytest.raises(ValueError, match='duplicate section name "Dup" on line 3 \\(first on line 1\\)'):
        transcript.parse('# Dup\na b\n# Dup\nc d\n')


def test_timeline_registered_under_composition_id(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', TR2)
    generate.generate(d)
    html = pages(d)['scene_00_zeta.html']
    assert 'window.__timelines' in html and "window.__timelines['zeta']" in html
    assert 'gsap.timeline({paused: true})' in html
    assert 'data-composition-id="zeta"' in html


def test_lines_dim_when_next_line_starts(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', '# S\n' + ' '.join(f'w{i}' for i in range(60)) + '\n')
    generate.generate(d)
    html = pages(d)['scene_00_s.html']
    assert "tl.to(document.querySelectorAll('.line[data-line=\"0\"] span')" in html
    from motion_pipeline.scheme import resolve_variant, derive_palette
    pal = derive_palette(resolve_variant(d, 'default'))
    # Task 22 page API dumps every palette key into the page, so the dim colour is asserted
    # against the palette VALUE (the old "'secondary' not in html" guard is superseded)
    assert 'duration: 0.3' in html and f"color: '{pal['secondary_text']}'" in html


def test_hyphenated_pieces_unique_ids(tmp_path):
    long_word = 'Donaudampfschifffahrtsgesellschaftskapitänsmütze' * 3
    d, tr, timing = mk(tmp_path / 'p', f'# S\n{long_word} kurz\n')
    generate.generate(d)
    html = pages(d)['scene_00_s.html']
    ids = re.findall(r'<span id="(el-[^"]+)"', html)
    assert len(ids) == len(set(ids)), ids  # every piece id unique
    word_id = tr['words'][0]['id']
    eids = json.load(open(os.path.join(d, 'src', 'element_ids.json')))
    assert eids[word_id] == f'el-{word_id}'  # word id maps to the FIRST piece
    assert any(pid.startswith(f'el-{word_id}-') for pid in ids)


def test_long_section_shrinks_to_fit(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', '# S\n' + 'wort ' * 120 + '\n')
    generate.generate(d)  # must not raise; font shrinks
    html = pages(d)['scene_00_s.html']
    m = re.search(r'<div class="line"[^>]*font-size:(\d+)px', html)  # the line div, not the card CSS
    base = int(1080 / 12)  # 16:9 default font_px
    assert m and int(m.group(1)) < base, 'font shrunk to fit'


def test_unfittable_section_fails_naming_it(tmp_path):
    # a zone covering the whole frame leaves no candidate position
    d, tr, timing = mk(tmp_path / 'p', '# S\nhello world\n',
                       zones=[{'section': 'S', 'rect': [0, 0, 1920, 1080], 'aspect': '16:9'}])
    with pytest.raises(ValueError, match='does not fit one frame at 16:9'):
        generate.generate(d)


def test_4_5_renders_native_dry_run(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', TR2, aspect='4:5')
    generate.generate(d)
    r = subprocess.run(['bash', 'tools/render_scene.sh', '--project', d, '--variant', 'default',
                        '--mode', 'test', '--dry-run'],
                       capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert r.returncode == 0, r.stderr[-400:]
    assert '--resolution' not in r.stdout, 'P4: no --resolution passed (4:5 renders native, E5)'
    assert 'scene_00_zeta.html' in r.stdout  # scenes.json drives the list


def test_max_seconds_caps_scene_duration(tmp_path):
    d, tr, timing = mk(tmp_path / 'p', TR2)
    generate.generate(d, max_seconds=1.0)
    for s in scenes_json(d):
        assert s['end'] - s['start'] <= 1.0 + 1e-9, s
