"""Task 6 (0.8.0, Q2): the declarative `shapes:` manifest block + MP.runShapes runner.

A manifest entry carries EITHER `file` (today's .html/.js, unchanged) OR `shapes`:
[{"type", "at", "props"?, "anchor"?}] where type is an L1 helper name. Unknown type is
refused naming it (no silent default). generate.py emits MP.runShapes(...) for shapes
entries; .js entries still load exactly as before (dogfood-style backward compat).
"""
import json
import os
import shutil
import subprocess

import pytest

from projfix import ROOT, make_project
from motion_pipeline import ai_layer, generate


def _project(tmp_path, manifest=None):
    pd = make_project(str(tmp_path / 'proj'))
    ag = os.path.join(pd, 'ai_graphics')
    os.makedirs(ag, exist_ok=True)
    if manifest is not None:
        json.dump(manifest, open(os.path.join(ag, 'manifest.json'), 'w'))
    return pd


def _words(pd):
    return json.load(open(os.path.join(pd, 'transcript_model.json')))['words']


def test_file_entry_loads_unchanged(tmp_path):
    pd0 = _project(tmp_path)
    wid = _words(pd0)[0]['id']
    open(os.path.join(pd0, 'ai_graphics', 'pulse.js'), 'w').write('// dogfood-style script\n')
    json.dump({'graphics': [{'id': 'pulse', 'file': 'pulse.js', 'anchor': {'word': wid}}]},
              open(os.path.join(pd0, 'ai_graphics', 'manifest.json'), 'w'))
    got = ai_layer.load_manifest(pd0, _words(pd0))
    assert len(got) == 1 and got[0]['file'] == 'pulse.js' and 'shapes' not in got[0]
    assert wid  # word anchor resolved (validated inside load_manifest)


def test_shapes_entry_loads_and_normalises(tmp_path):
    pd = _project(tmp_path)
    wid = _words(pd)[0]['id']
    sec = _words(pd)[0]['section']
    json.dump({'graphics': [{'id': 'wshapes', 'anchor': {'word': wid}, 'layer': 'above',
                             'shapes': [{'type': 'el', 'at': wid,
                                         'props': {'tag': 'div', 'style': {'width': '10px'}}},
                                        {'type': 'enter', 'at': wid, 'props': {'d': 0.4}},
                                        {'type': 'exit', 'at': f'#{sec}', 'props': {}}]}]},
              open(os.path.join(pd, 'ai_graphics', 'manifest.json'), 'w'))
    got = ai_layer.load_manifest(pd, _words(pd))
    assert len(got) == 1 and got[0]['shapes'][0]['type'] == 'el'
    assert 'file' not in got[0] and got[0]['section'] == sec


def test_unknown_shape_type_refused_naming_it(tmp_path):
    pd = _project(tmp_path)
    wid = _words(pd)[0]['id']
    json.dump({'graphics': [{'id': 'w', 'anchor': {'word': wid},
                             'shapes': [{'type': 'explode', 'at': wid}]}]},
              open(os.path.join(pd, 'ai_graphics', 'manifest.json'), 'w'))
    with pytest.raises(ValueError) as ei:
        ai_layer.load_manifest(pd, _words(pd))
    assert 'explode' in str(ei.value) and 'enter' in str(ei.value), str(ei.value)


def test_file_and_shapes_are_exclusive(tmp_path):
    pd = _project(tmp_path)
    wid = _words(pd)[0]['id']
    open(os.path.join(pd, 'ai_graphics', 'pulse.js'), 'w').write('// x\n')
    json.dump({'graphics': [{'id': 'w', 'file': 'pulse.js', 'anchor': {'word': wid},
                             'shapes': [{'type': 'el', 'at': wid}]}]},
              open(os.path.join(pd, 'ai_graphics', 'manifest.json'), 'w'))
    with pytest.raises(ValueError) as ei:
        ai_layer.load_manifest(pd, _words(pd))
    assert 'exactly one' in str(ei.value) or 'both' in str(ei.value), str(ei.value)


def test_generate_emits_runshapes_for_shapes_entry(tmp_path):
    pd = _project(tmp_path)
    wid = _words(pd)[0]['id']
    sec = _words(pd)[0]['section']
    json.dump({'graphics': [{'id': 'wshapes', 'anchor': {'word': wid}, 'layer': 'above',
                             'shapes': [{'type': 'el', 'at': wid, 'props': {'tag': 'div'}},
                                        {'type': 'enter', 'at': wid, 'props': {}},
                                        {'type': 'exit', 'at': f'#{sec}', 'props': {}}]}]},
              open(os.path.join(pd, 'ai_graphics', 'manifest.json'), 'w'))
    generate.generate(pd)
    src = os.path.join(pd, 'src')
    pages = ''.join(open(os.path.join(src, f)).read() for f in sorted(os.listdir(src))
                    if f.startswith('scene_') and f.endswith('.html'))
    assert 'MP.runShapes(' in pages, 'shapes entry must run via MP.runShapes'
    assert 'wshapes' in pages
    assert pages.index('src="mp_lib.js"') < pages.index('MP.runShapes(')


def test_runshapes_runner_in_node(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('node not on PATH')
    probe = (
        'var window = {MP: {tl: null, at: function (r, o) { return typeof r === "number" ? r + (o || 0) : 0; },'
        ' timings: {}, zones: [[10, 20, 300, 100]]}};\n'
        'var document = {createElement: function (t) { return {tag: t, style: {}, innerHTML: "", appendChild: function () {}}; },'
        ' getElementById: function () { return {appendChild: function () {}}; }};\n'
        'var gsap = {timeline: function () { var tl = {calls: [],'
        ' to: function () { tl.calls.push(["to"].concat([].slice.call(arguments))); return tl; },'
        ' fromTo: function () { tl.calls.push(["fromTo"].concat([].slice.call(arguments))); return tl; }};'
        ' return tl; }};\n'
        'window.MP.tl = gsap.timeline();\n'
        'var assert = require("assert");\n'
        + open(os.path.join(ROOT, 'motion_pipeline', 'graphics', 'mp_lib.js')).read() + '\n'
        'var layer = {appendChild: function (e) {}};\n'
        'var made = window.MP.runShapes([\n'
        '  {type: "el", at: 0, props: {tag: "div", style: {width: "10px"}}},\n'
        '  {type: "enter", at: 0, props: {d: 0.4}},\n'
        '  {type: "float", at: 0, props: {to: 5, amp: 8}},\n'
        '  {type: "exit", at: 5, props: {}},\n'
        '  {type: "explode", at: 0, props: {}}\n'
        '], {layer: layer});\n'
        'assert.strictEqual(made.length, 1, "one element made");\n'
        'var calls = window.MP.tl.calls;\n'
        'assert.strictEqual(calls.length, 3, "enter + float + exit = 3 tweens, unknown type skipped: " + calls.length);\n'
        'assert.strictEqual(calls[0][0], "fromTo", "enter");\n'
        'assert.strictEqual(calls[0][4], 0, "enter at absolute position 0");\n'
        'assert.strictEqual(calls[2][0], "to", "exit");\n'
        'assert.strictEqual(calls[2][3], 5, "exit at absolute position 5");\n'
    )
    r = subprocess.run([node, '-e', probe], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
