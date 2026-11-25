"""0.8.5 L0 (plan 2026-11-23-motion-pipeline-l0-absolute-positions-plan.md): the page's OWN
tweens (card in/out, the per-word style loop, dimming) go on the registered timeline at
EXPLICIT ABSOLUTE positions — never vars `delay` (gsap appends delay-carrying tweens at the
timeline end, so append order decides where words land). RED pre-change: the emitted page
carries delay: in its own script and shapes entries wait on a fonts.ready arm.
"""
import json
import os
import re
import shutil
import subprocess

import pytest
from projfix import make_project

from motion_pipeline import generate


def _pages(pd):
    generate.generate(pd)
    src = os.path.join(pd, 'src')
    return {f: open(os.path.join(src, f)).read()
            for f in sorted(os.listdir(src)) if f.endswith('.html')}


def test_page_tweens_are_positional_no_vars_delay(tmp_path):
    pd = make_project(str(tmp_path / 'p'))
    pages = _pages(pd)
    assert pages
    for name, html in pages.items():
        own_blocks = [b for b in re.findall(r'<script>(.*?)</script>', html, re.S)
                      if 'data-ai-id' not in b]
        assert own_blocks, name
        for block in own_blocks:
            assert 'delay' not in block, (name, block[:200])
        assert re.search(r'\}, t\.start\);', html), f'{name}: word loop not positional'
        assert '}, 1.2);' in html, f'{name}: card-out not at absolute 1.2s'


def test_shapes_entry_runs_without_arming_wrapper(tmp_path):
    """T4: with positional page tweens, the shapes runner no longer waits on fonts.ready."""
    pd = make_project(str(tmp_path / 'p'))
    ag = os.path.join(pd, 'ai_graphics')
    os.makedirs(ag)
    with open(os.path.join(ag, 'manifest.json'), 'w') as f:
        json.dump({'graphics': [{'id': 'g1', 'shapes': [
            {'type': 'el', 'at': 0, 'props': {'tag': 'div'}},
            {'type': 'enter', 'at': 0, 'props': {'d': 0.3}}],
            'anchor': {'section': 'Welcome'}, 'layer': 'above'}]}, f)
    pages = _pages(pd)
    ai_blocks = [b for html in pages.values()
                 for b in re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
                 if 'data-ai-id' in b or 'MP.runShapes' in b]
    assert ai_blocks, 'no shapes script emitted'
    for block in ai_blocks:
        assert 'MP.runShapes(' in block, block[:200]
        assert 'fonts' not in block and 'armed' not in block, 'arming wrapper still present'


def test_positional_tweens_are_order_independent(tmp_path):
    """T5: with positional args, append order does not change tween start times (node probe
    with a recording fake gsap). The old vars-delay semantic IS order-dependent (documents
    the bug the change fixes)."""
    node = shutil.which('node')
    if not node:
        pytest.skip('node not on PATH')
    probe = r'''
var calls = [];
var tl = {to: function (t, vars, pos) { calls.push([vars, pos]); return tl; }};
function startOf(c) { return c[1] != null ? c[1] : (calls.length ? endSoFar + (c[0].delay || 0) : (c[0].delay || 0)); }
var endSoFar = 0;
function simulate(order, usePositional) {
  calls = []; endSoFar = 0;
  var card = {duration: 0.6, opacity: 1};
  var cardOut = {duration: 0.4, opacity: 0};
  var word = {duration: 0.35, y: '0%', opacity: 1};
  var steps = order === 'pageFirst'
    ? [[card, 0], [cardOut, 1.2], [word, 2.0]]
    : [[word, 2.0], [card, 0], [cardOut, 1.2]];
  for (var i = 0; i < steps.length; i++) {
    var vars = {}; for (var k in steps[i][0]) vars[k] = steps[i][0][k];
    if (usePositional) { tl.to(null, vars, steps[i][1]); endSoFar = Math.max(endSoFar, steps[i][1] + vars.duration); }
    else { vars.delay = steps[i][1]; var s = startOf([vars, null]); tl.to(null, vars, null); endSoFar = s + vars.duration; calls[calls.length-1][1] = s; }
  }
  return calls.map(function (c) { return c[1]; });
}
var assert = require('assert');
var posA = simulate('pageFirst', true), posB = simulate('aiFirst', true);
assert.deepStrictEqual(posA.slice().sort(function(a,b){return a-b;}), posB.slice().sort(function(a,b){return a-b;}), 'positional: same start set regardless of order');
assert.strictEqual(posA[2], 2.0, 'word lands at its absolute 2.0s');
var delayA = simulate('pageFirst', false), delayB = simulate('aiFirst', false);
assert.notDeepStrictEqual(delayA, delayB, 'vars-delay IS order-dependent (the old bug)');
assert.notStrictEqual(delayA[2], 2.0, 'word does NOT land at 2.0 with vars delay');
'''
    r = subprocess.run([node, '-e', probe], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
