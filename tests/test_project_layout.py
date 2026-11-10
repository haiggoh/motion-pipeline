"""0.5.0 Task 4d: modular project layout (user 2026-11-10 01:47 CET). Three zones, one owner
each: menu-owned files stay pristine and strictly validated; src/ is regenerated; an AI adds
graphics ONLY under ai_graphics/ (declared in ai_graphics/manifest.json, anchored to the
stable element ids) and the generator wires them into the pages. Also pins two generator
bugs found 2026-11-10: the section card's CSS (#card) matched no element, and the published
element ids (el-<word>) were never put on any element."""
import hashlib
import json
import os
import re
import subprocess

import pytest
from textual.widgets import Input

from motion_pipeline import generate, project, scheme
from motion_pipeline.tui.app import MenuApp
from projfix import DARK, ROOT, make_project
from tui_probe import choose


def _pages(pd):
    src = os.path.join(pd, 'src')
    return {f: open(os.path.join(src, f)).read() for f in sorted(os.listdir(src)) if f.endswith('.html')}


def _digest(paths):
    return {p: hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in paths}


def _tree(d):
    return sorted(os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs)


def test_every_css_selector_in_generated_pages_matches_an_element(tmp_path):
    pd = make_project(tmp_path / 'p')
    generate.generate(pd)
    for name, page in _pages(pd).items():
        style = page.split('<style>', 1)[1].split('</style>', 1)[0]
        body = page.split('<body>', 1)[1]
        for sel in set(re.findall(r'#([A-Za-z][\w-]*)\s*\{', style)):
            assert f'id="{sel}"' in body, f'{name}: CSS #{sel} matches no element (dead selector)'
        for sel in set(re.findall(r'\.([A-Za-z][\w-]*)\b[^{]*\{', style)):
            assert re.search(rf'class="[^"]*\b{sel}\b', body), f'{name}: CSS .{sel} matches no element'


def test_published_element_ids_exist_in_the_pages(tmp_path):
    pd = make_project(tmp_path / 'p')
    generate.generate(pd)
    ids = json.load(open(os.path.join(pd, 'src', 'element_ids.json')))
    allpages = '\n'.join(_pages(pd).values())
    missing = [v for v in ids.values() if f'id="{v}"' not in allpages]
    assert not missing, f'published ids not on any element: {missing[:5]}'


def _add_ai_graphics(pd):
    words = json.load(open(os.path.join(pd, 'transcript_model.json')))['words']
    w = words[2]
    ag = os.path.join(pd, 'ai_graphics')
    os.makedirs(ag)
    open(os.path.join(ag, 'spark.html'), 'w').write('<svg id="spark" width="40" height="40"></svg>\n')
    open(os.path.join(ag, 'pulse.js'), 'w').write('window.__pulse = (window.__pulse || 0) + 1;\n')
    json.dump({'graphics': [
        {'id': 'spark', 'file': 'spark.html', 'anchor': {'word': w['id']}, 'layer': 'above'},
        {'id': 'pulse', 'file': 'pulse.js', 'anchor': {'section': w['section']}, 'layer': 'below'}]},
        open(os.path.join(ag, 'manifest.json'), 'w'))
    return w


async def test_ai_graphics_wired_in_and_untouched_by_menu_edits(tmp_path):
    pd = make_project(tmp_path / 'p')
    w = _add_ai_graphics(pd)
    before = _digest(_tree(os.path.join(pd, 'ai_graphics')))
    # a menu edit + save + regenerate
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        app.screen.query_one('#accent', Input).value = '#ff6a00'; await pilot.pause()
        await choose(pilot, app.screen, 'save')
        assert 'saved' in str(app.screen.query_one('#preview').render())
    generate.generate(pd)
    assert _digest(_tree(os.path.join(pd, 'ai_graphics'))) == before   # byte-identical
    page = _pages(pd)[f'scene_{w["section"]}.html']
    assert f'data-ai-id="spark"' in page and f'data-anchor="el-{w["id"]}"' in page
    assert '<svg id="spark"' in page
    assert 'src="ai_graphics/pulse.js"' in page
    assert os.path.isfile(os.path.join(pd, 'src', 'ai_graphics', 'pulse.js'))
    others = [p for n, p in _pages(pd).items() if n != f'scene_{w["section"]}.html']
    assert others and all('data-ai-id' not in p for p in others)  # only at its anchor's section


@pytest.mark.parametrize('bad, msg', [
    ({'id': 'x', 'file': 'missing.js', 'anchor': {'section': 'Welcome'}}, "'x'.*missing.js"),
    ({'id': 'x', 'file': 'a.js', 'anchor': {'word': 'w0', 'section': 'Welcome'}}, "'x'.*exactly one"),
    ({'id': 'x', 'file': 'a.js', 'anchor': {'word': 'nope'}}, "'x'.*unknown word"),
    ({'id': 'x', 'file': 'a.js', 'anchor': {'section': 'Welcome'}, 'layer': 'top'}, "'x'.*layer"),
])
def test_invalid_manifest_fails_naming_the_entry_and_touches_no_menu_file(tmp_path, bad, msg):
    pd = make_project(tmp_path / 'p')
    ag = os.path.join(pd, 'ai_graphics'); os.makedirs(ag)
    open(os.path.join(ag, 'a.js'), 'w').write('//\n')
    json.dump({'graphics': [bad]}, open(os.path.join(ag, 'manifest.json'), 'w'))
    owned = [os.path.join(pd, f) for f in ('project.json', 'scheme.json', 'timing.json', 'transcript.txt')]
    before = _digest(owned)
    with pytest.raises(ValueError, match=msg):
        generate.generate(pd)
    assert _digest(owned) == before


async def test_foreign_key_in_project_json_is_a_named_refusal_in_the_menu(tmp_path):
    pd = make_project(tmp_path / 'p')
    pj = os.path.join(pd, 'project.json')
    p = json.load(open(pj)); p['sparkle_layer'] = {'x': 1}
    json.dump(p, open(pj, 'w'))
    raw = open(pj, 'rb').read()
    with pytest.raises(ValueError, match="sparkle_layer.*ai_graphics"):
        project.load(pd)
    app = MenuApp()
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['project']()); await pilot.pause()
        app.screen.query_one('#dir', Input).value = pd
        await choose(pilot, app.screen, 'load')
        assert 'sparkle_layer' in str(app.screen.query_one('#error').render())
        assert app.project_dir != pd
    assert open(pj, 'rb').read() == raw   # never rewritten / keys never dropped


def test_agents_md_written_and_names_the_three_zones(tmp_path):
    pd = str(tmp_path / 'p'); os.makedirs(pd)
    project.save(pd, project.default_project('p'))
    text = open(os.path.join(pd, 'AGENTS.md')).read()
    for needle in ('ai_graphics/', 'manifest.json', 'element_ids.json', 'src/', 'project.json',
                   'scheme.json', 'variants/', 'timing.json', 'never'):
        assert needle in text, needle


def test_render_staging_copies_ai_graphics_into_the_site(tmp_path):
    pd = make_project(tmp_path / 'p')
    _add_ai_graphics(pd)
    generate.generate(pd)
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'), '--project', pd,
                        '--variant', 'default', '--mode', 'test', '--out', str(tmp_path / 'out'),
                        '--stage-only'], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    sites = [l.split('site: ', 1)[1] for l in r.stdout.splitlines() if 'site: ' in l]
    assert sites, r.stdout
    assert any(os.path.isfile(os.path.join(s, 'ai_graphics', 'pulse.js')) for s in sites), sites
