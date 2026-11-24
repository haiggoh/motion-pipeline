"""Task 3 (0.8.0): placement rules for the L1 helpers, pinned on vendored-gsap semantics.

Rules: every tween goes on MP.tl at an EXPLICIT ABSOLUTE position (the 3rd+ arg) — never via
vars `delay` (gsap appends delay-carrying tweens at the timeline end, burying anything added
later) — and `repeat` is always finite (`repeat: -1` sets gsap's 10^10 duration marker, same
burying). RED on the 0.7.1 mp_lib.js: float uses repeat:-1, enter/exit/drawOn carry vars delay.
"""
import os
import re
import shutil
import subprocess

import pytest
from projfix import ROOT

MP_LIB = os.path.join(ROOT, 'motion_pipeline', 'graphics', 'mp_lib.js')


def _tween_calls(src):
    """Yield the argument lists of every MP.tl.to/fromTo call in the source."""
    for m in re.finditer(r'MP\.tl\.(?:to|fromTo)\(', src):
        i = m.end() - 1
        depth = 0
        while i < len(src):
            if src[i] == '(':
                depth += 1
            elif src[i] == ')':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[m.end():i]
        args, depth, cur = [], 0, ''
        for ch in body:
            if ch in '([{':
                depth += 1
            elif ch in ')]}':
                depth -= 1
            if ch == ',' and depth == 0:
                args.append(cur)
                cur = ''
            else:
                cur += ch
        args.append(cur)
        yield m.group(0), args


def test_no_unbounded_repeat_in_mp_lib():
    src = open(MP_LIB).read()
    assert not re.search(r'repeat\s*:\s*-1', src), 'mp_lib must not use repeat: -1 (10^10 marker)'


def test_no_delay_property_anywhere_in_mp_lib():
    """Stronger than the per-call parse: a `delay:` property anywhere in mp_lib.js would
    append that tween at the timeline end (gsap semantics) — banned outright in L1."""
    src = open(MP_LIB).read()
    assert not re.search(r'\bdelay\s*:', src), 'vars delay appends at the timeline end — banned in L1'


def test_mp_lib_exports_only_the_audited_helpers():
    """The L1 audit (docs/l1-audit.md) fixed the surface at the 7 helpers + MP.at; the only
    addition since is the Task 6 runner MP.runShapes. Pin the set so a future helper
    (esp. a project-specific one) cannot land silently."""
    src = open(MP_LIB).read()
    exported = sorted(set(re.findall(r'MP\.(\w+)\s*=', src)))
    assert exported == sorted(['el', 'enter', 'exit', 'drawOn', 'float', 'inZone', 'random',
                               'runShapes']), exported


def test_every_tween_uses_absolute_position_not_vars_delay():
    src = open(MP_LIB).read()
    calls = list(_tween_calls(src))
    assert calls, 'no MP.tl tween calls found — rule test would prove nothing'
    for head, args in calls:
        assert len(args) >= 3, f'{head}… call has no position arg: {args}'
        for a in args[:-1]:
            assert 'delay' not in a, f'{head}… must not carry vars delay (appends at timeline end): {a[:120]}'


def test_float_and_enter_behaviour_in_node():
    """Run the real mp_lib.js in node against a recording fake gsap: float gets a finite
    repeat and an absolute position; enter places its fromTo at the 3rd arg, no vars delay."""
    node = shutil.which('node')
    if not node:
        pytest.skip('node not on PATH')
    probe = (
        'var window = {MP: {tl: null, at: function (r, o) { return typeof r === "number" ? r + (o || 0) : 0; },'
        ' timings: {}, zones: [[10, 20, 300, 100]]}};\n'
        'var document = {createElement: function () { return {style: {}, innerHTML: ""}; },'
        ' getElementById: function () { return {appendChild: function () {}}; }};\n'
        'var gsap = {timeline: function () { var tl = {calls: [],'
        ' to: function () { tl.calls.push(["to"].concat([].slice.call(arguments))); return tl; },'
        ' fromTo: function () { tl.calls.push(["fromTo"].concat([].slice.call(arguments))); return tl; }};'
        ' return tl; }};\n'
        'window.MP.tl = gsap.timeline();\n'
        'var assert = require("assert");\n'
        + open(MP_LIB).read() + '\n'
        'var el = window.MP.el("div", {position: "absolute"});\n'
        'window.MP.float(el, 0, 5, {});\n'
        'var last = window.MP.tl.calls[window.MP.tl.calls.length - 1];\n'
        'assert.strictEqual(last[0], "to");\n'
        'assert.notStrictEqual(last[2].repeat, -1, "float repeat must be finite");\n'
        'assert.ok(last[2].repeat >= 1, "float repeat >= 1: " + last[2].repeat);\n'
        'assert.strictEqual(last[3], 0, "float places at absolute position at(fromRef)");\n'
        'window.MP.enter(el, 2, {});\n'
        'last = window.MP.tl.calls[window.MP.tl.calls.length - 1];\n'
        'assert.strictEqual(last[0], "fromTo");\n'
        'assert.strictEqual(last[4], 2, "enter places its fromTo at the last arg (absolute position)");\n'
        'assert.ok(!("delay" in last[2]) && !("delay" in last[3]), "no vars delay in enter");\n'
    )
    r = subprocess.run([node, '-e', probe], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
