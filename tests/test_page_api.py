"""Task 22 tests (plan 2026-11-16): the page API — window.MP is defined in the page BEFORE any
ai_graphics script tag (ordering asserted on the generated HTML, not the source), MP.at
resolves word/section/numeric refs (the generated script block is EXECUTED in node and its
return values asserted), the --check-graphics / --render-test flags exist on the shipped
`python -m motion_pipeline` entry point and delegate, vendored DrawSVG sha matches the P&G
copy, and sfx_cues no longer crashes on aligner timing words (regression: estimate_timings
drops 'section')."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from motion_pipeline import audio_mux, generate, render_cli
from motion_pipeline.__main__ import main as mp_main
from projfix import ROOT, make_project

PY = sys.executable


def _pages(pd):
    src = os.path.join(pd, 'src')
    return {f: open(os.path.join(src, f)).read() for f in sorted(os.listdir(src))
            if f.endswith('.html')}


def _add_ai(pd, with_sfx=False, unlicensed=False, extra=None):
    """Manifest with one .js graphic anchored to the 3rd word; optional sfx cue, optional
    unreferenced extra file."""
    words = json.load(open(os.path.join(pd, 'transcript_model.json')))['words']
    w = words[2]
    ag = os.path.join(pd, 'ai_graphics')
    os.makedirs(ag, exist_ok=True)
    open(os.path.join(ag, 'pulse.js'), 'w').write('window.__pulse = 1;\n')
    entry = {'id': 'pulse', 'file': 'pulse.js', 'anchor': {'word': w['id']}, 'layer': 'below'}
    if with_sfx:
        os.makedirs(os.path.join(ag, 'sfx'), exist_ok=True)
        open(os.path.join(ag, 'sfx', 'w.wav'), 'wb').write(b'RIFF')
        entry['sfx'] = [{'file': 'sfx/w.wav', 'offset': 0.0, 'gain_db': -3.0}]
        if not unlicensed:
            open(os.path.join(ag, 'sfx', 'LICENSES.md'), 'w').write('sfx/w.wav — test — CC0\n')
        else:
            lp = os.path.join(ag, 'sfx', 'LICENSES.md')
            if os.path.isfile(lp):
                os.remove(lp)  # unlicensed even if a previous case wrote one
    if extra:
        open(os.path.join(ag, extra), 'w').write('// extra\n')
    json.dump({'graphics': [entry]}, open(os.path.join(ag, 'manifest.json'), 'w'))
    return w


def test_page_api_defined_before_ai_scripts(tmp_path):
    pd = make_project(tmp_path / 'p')
    w = _add_ai(pd)
    generate.generate(pd)
    scenes = json.load(open(os.path.join(pd, 'src', 'scenes.json')))
    scene = next(s for s in scenes if s['name'] == w['section'])
    html = _pages(pd)[scene['file']]
    assert 'src="ai_graphics/pulse.js"' in html
    # ordering ON THE GENERATED PAGE: registered timeline, then window.MP, then the AI script tag
    assert html.index('window.__timelines[') < html.index('window.MP =') \
        < html.index('src="ai_graphics/pulse.js"')
    # dogfood 2026-11-19 (sevenone adf test session) found all three of these broken:
    assert html.count('src="ai_graphics/pulse.js"') == 1, 'ai scripts emitted once per page'
    assert html.index('window.MP =') < html.index('src="mp_lib.js"'), \
        'mp_lib.js must load AFTER window.MP — its IIFE reads MP immediately (MP_LIB_NO_MP)'
    assert 'window.__timelines = window.__timelines || {}' in html, \
        'guard the runtime global before assigning — hyperframes does not predefine it'


def test_mp_at_resolves_word_section_and_number(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('node not on PATH')
    pd = make_project(tmp_path / 'p')
    generate.generate(pd)
    scenes = json.load(open(os.path.join(pd, 'src', 'scenes.json')))
    scene = scenes[0]
    html = _pages(pd)[scene['file']]
    m = re.search(r'<script>\n(// Task 22 page API.*?)</script>', html, re.S)
    assert m, 'page-API script block not found in generated page'
    words = [w for w in json.load(open(os.path.join(pd, 'transcript_model.json')))['words']
             if w['section'] == scene['name']]
    wid = words[2]['id']
    p = json.load(open(os.path.join(pd, 'project.json')))
    # run the ACTUAL generated script block in node and assert MP.at's return values
    mp_lib = open(os.path.join(ROOT, 'motion_pipeline', 'graphics', 'mp_lib.js')).read()
    probe = (
        'var window = {__timelines: {}};\n'
        'var document = {createElement: function () { return {style: {}, innerHTML: ""}; },'
        ' getElementById: function () { return {appendChild: function () {}}; }};\n'
        'var gsap = {timeline: function (opts) { var tl = {opts: opts, calls: [],'
        ' to: function () { tl.calls.push(["to"].concat([].slice.call(arguments))); return tl; },'
        ' fromTo: function () { tl.calls.push(["fromTo"].concat([].slice.call(arguments))); return tl; },'
        ' add: function () { return tl; }}; return tl; }};\n'
        + m.group(1) + '\n'
        + 'var assert = require("assert");\n'
        + f'assert.strictEqual(window.MP.at({wid!r}), window.MP.timings[{wid!r}].start, "word ref");\n'
        + f'assert.strictEqual(window.MP.at("#{scene["name"]}"), 0, "own section start is scene-relative 0");\n'
        + 'assert.strictEqual(window.MP.at(2.5, 0.5), 3.0, "numeric ref passes through + offset");\n'
        + 'assert.strictEqual(window.MP.at("#NoSuchSection"), 0, "unknown section falls back to 0");\n'
        + f'assert.strictEqual(window.MP.scene.slug, {scene["slug"]!r});\n'
        + f'assert.strictEqual(window.MP.frame.W, {p["resolution"][0]});\n'
        + f'assert.strictEqual(window.MP.frame.fps, {p["fps"]});\n'
        + 'assert.ok(window.MP.palette.background_dark, "palette exposed");\n'
        + 'assert.ok(Array.isArray(window.MP.zones) && Array.isArray(window.MP.sfx));\n'
        + 'assert.ok(window.MP.tl === window.__timelines[Object.keys(window.__timelines)[0]],\n'
        + '          "MP.tl IS the registered scene timeline");\n'
        + 'assert.deepStrictEqual(window.MP.tl.opts, {paused: true}, "scene timeline registered paused");\n'
        + mp_lib + '\n'
        + '["el","enter","exit","drawOn","float","inZone","random"].forEach(function (k) {\n'
        + '  assert.strictEqual(typeof window.MP[k], "function", "mp_lib helper " + k); });\n'
        + 'var el = window.MP.el("div", {position: "absolute"});\n'
        + f'window.MP.enter(el, {wid!r}, {{d: 0.2}});\n'
        + 'var tlc = window.MP.tl, last = tlc.calls[tlc.calls.length - 1];\n'
        + 'assert.strictEqual(last[0], "fromTo", "MP.enter adds a fromTo on MP.tl");\n'
        + f'assert.strictEqual(last[3].delay, window.MP.at({wid!r}), "enter delay = MP.at(ref)");\n'
        + 'window.DrawSVGPlugin = function () {};\n'
        + f'window.MP.drawOn({{}}, {wid!r}, {{}});\n'
        + 'last = tlc.calls[tlc.calls.length - 1];\n'
        + 'assert.strictEqual(last[3].drawSVG, "100%", "drawOn animates drawSVG 0->100% on MP.tl");\n'
        + 'window.MP.zones = [[10, 20, 300, 100]];\n'
        + 'var z = window.MP.el("div"); window.MP.inZone(z, 0);\n'
        + 'assert.strictEqual(z.style.left, "10px"); assert.strictEqual(z.style.width, "300px");\n'
        + 'var r1 = window.MP.random(42), r2 = window.MP.random(42);\n'
        + 'var a1 = r1(), a2 = r2();\n'
        + 'assert.ok(Math.abs(a1 - 0.6011037519201636) < 1e-12, "mulberry32(42) known first value (node-verified)");\n'
        + 'assert.strictEqual(a1, a2, "same seed -> identical first value");\n'
        + 'assert.strictEqual(r1(), r2(), "same seed -> identical sequence");\n'
        + 'assert.ok(Math.abs(window.MP.random(43)() - 0.9998110907617956) < 1e-12, "mulberry32(43) known first value");\n'
    )
    r = subprocess.run([node, '-e', probe], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]


def test_check_graphics_ok_unreferenced_and_unlicensed(tmp_path, capsys):
    pd = make_project(tmp_path / 'p')
    _add_ai(pd, with_sfx=True)
    assert render_cli.main(['--check-graphics', pd]) == 0               # clean project: exit 0
    out = capsys.readouterr().out
    assert 'check-graphics: OK' in out
    _add_ai(pd, with_sfx=True, extra='extra.js')                        # unreferenced file
    rc = render_cli.main(['--check-graphics', pd])
    err = capsys.readouterr().err
    assert rc == 1 and 'unreferenced file: extra.js' in err             # problems listed, exit 1
    _add_ai(pd, with_sfx=True, unlicensed=True)                         # sfx cue without LICENSES line
    rc = render_cli.main(['--check-graphics', pd])
    err = capsys.readouterr().err
    assert rc == 3 and 'LICENSES' in err                                # manifest invalid: exit 3


def test_render_test_dry_run_shows_span_duration(tmp_path, capsys):
    pd = make_project(tmp_path / 'p')
    generate.generate(pd)
    scenes = json.load(open(os.path.join(pd, 'src', 'scenes.json')))
    sec = scenes[0]['name']
    rc = render_cli.main(['--render-test', pd, '--section', sec,
                          '--from', '1.5', '--to', '4.25', '--dry-run'])
    out = capsys.readouterr().out
    assert rc == 0 and 'data-duration=2.750' in out and scenes[0]['slug'] in out
    # the exact injected composition-timeline script is part of the printed plan
    assert 'paused:true' in out and 'tweenFromTo(1.500,4.250)' in out
    assert not os.path.isdir(os.path.join(pd, 'scratch', 'ai-test', '_proj'))  # dry-run staged nothing


def test_main_help_lists_task22_flags():
    # the SHIPPED entry point, no injected wiring
    r = subprocess.run([PY, '-m', 'motion_pipeline', '--help'], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0
    assert '--check-graphics' in r.stdout and '--render-test' in r.stdout


def test_main_delegates_check_graphics(tmp_path):
    pd = make_project(tmp_path / 'p')
    _add_ai(pd)
    assert mp_main(['--check-graphics', pd]) == 0                       # __main__ -> render_cli


def test_drawsvg_vendored_sha_matches_pg():
    vend = os.path.join(ROOT, 'vendor', 'DrawSVGPlugin.min.js')
    pg = os.environ.get('MP_PG_DRAWSVG')  # reference copy path, supplied per machine — never hardcoded
    if not pg or not os.path.isfile(pg):
        pytest.skip('P&G DrawSVG reference copy not configured (set MP_PG_DRAWSVG=<path>)')

    def sha(path):
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()

    assert sha(vend) == sha(pg), 'vendored DrawSVGPlugin.min.js differs from the P&G 3.14.2 copy'


def test_notices_contains_gsap_licence():
    text = open(os.path.join(ROOT, 'NOTICES.md')).read()
    assert 'GSAP 3.14.2' in text and 'DrawSVGPlugin' in text and 'No Charge' in text


def test_sfx_cues_resolves_anchors_with_aligner_timing(tmp_path):
    """Regression (found resuming de1e6828): align.estimate_timings drops 'section' from timing
    words; sfx_cues passed those to load_manifest -> KeyError 'section'. It must take
    section-bearing words from the transcript model."""
    pd = make_project(tmp_path / 'p')
    tr = json.load(open(os.path.join(pd, 'transcript_model.json')))
    timing = json.load(open(os.path.join(pd, 'timing.json')))
    assert all('section' not in w for w in timing['words'])             # fixture precondition
    _add_ai(pd, with_sfx=True)
    cues = audio_mux.sfx_cues(pd, timing, tr)
    assert len(cues) == 1 and cues[0]['graphic'] == 'pulse'


# --- determinism lint (waypoint optional-check-graphics, user-approved 2026-11-19) --------
# ai_graphics scripts must stay deterministic: the renderer seeks frames, so rAF/setTimeout/
# Date/unseeded Math.random and the network are banned. MP.random(seed) is the seeded path.
DET_LINT = [
    (r'\brequestAnimationFrame\s*\(', 'requestAnimationFrame'),
    (r'\bsetTimeout\s*\(', 'setTimeout'),
    (r'\bsetInterval\s*\(', 'setInterval'),
    (r'\bnew\s+Date\b|\bDate\.(now|parse)\s*\(', 'Date'),
    (r'\bMath\.random\s*\(', 'unseeded Math.random (use MP.random(seed))'),
    (r'\b(fetch|XMLHttpRequest|WebSocket|sendBeacon)\b|\bimport\s*\(', 'network'),
]


def test_check_graphics_flags_nondeterministic_ai_scripts(tmp_path, capsys):
    pd = make_project(tmp_path / 'p')
    _add_ai(pd)
    ag = os.path.join(pd, 'ai_graphics')
    open(os.path.join(ag, 'pulse.js'), 'w').write(
        "setTimeout(function () {}, 10);\n"
        "var r = Math.random();\n"
        "fetch('/api/thing');\n")
    rc = render_cli.main(['--check-graphics', pd])
    err = capsys.readouterr().err
    assert rc == 1, (rc, err)
    assert 'pulse.js:1' in err and 'setTimeout' in err, err
    assert 'pulse.js:2' in err and 'Math.random' in err, err
    assert 'pulse.js:3' in err and 'network' in err, err


def test_check_graphics_determinism_lint_no_false_positives(tmp_path, capsys):
    pd = make_project(tmp_path / 'p')
    _add_ai(pd)
    ag = os.path.join(pd, 'ai_graphics')
    open(os.path.join(ag, 'pulse.js'), 'w').write(
        "var r = MP.random(42);\n"
        "MP.enter(el, 'w0', {d: 0.2});\n"
        "var d = document.createElement('div');\n")  # 'document' must not trip the Date rule
    assert render_cli.main(['--check-graphics', pd]) == 0
    assert 'check-graphics: OK' in capsys.readouterr().out
