"""Task 21 tests (plan 2026-11-16): timing freshness gate — inputs fingerprint, reuse, menu gate."""
import json
import os

import pytest

from motion_pipeline import align, project, transcript
from motion_pipeline.scheme import save_scheme

DARK = {'name': 'default', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}


def mk(d, tr_text='# S\nhello world again\n'):
    d = str(d)
    p = project.default_project('demo')
    p['fonts'] = {'family': 'Montserrat'}
    project.save(d, p)
    save_scheme(os.path.join(d, 'scheme.json'), DARK)
    (open(os.path.join(d, 'transcript.txt'), 'w')).write(tr_text)
    tr = transcript.parse(tr_text)
    json.dump(tr, open(os.path.join(d, 'transcript_model.json'), 'w'))
    align.save_timing(os.path.join(d, 'timing.json'),
                      {**align.estimate_timings(tr, wpm=140),
                       'inputs': align.inputs_fingerprint(d, p)})
    return d, p


def test_fingerprint_covers_transcript_vo_and_settings(tmp_path):
    d, p = mk(tmp_path / 'p')
    fp = align.inputs_fingerprint(d, p)
    assert len(fp) == 64
    p2 = dict(p, wpm=200)
    assert align.inputs_fingerprint(d, p2) != fp  # settings change the fingerprint


def test_fresh_then_stale_on_transcript_change(tmp_path):
    d, p = mk(tmp_path / 'p')
    assert align.timing_is_fresh(d, p)
    with open(os.path.join(d, 'transcript.txt'), 'w') as f:
        f.write('# S\nhello world again and more\n')
    assert not align.timing_is_fresh(d, p)  # transcript changed -> stale


def test_new_vo_take_makes_timing_stale(tmp_path):
    d, p = mk(tmp_path / 'p')
    os.makedirs(os.path.join(d, 'audio'))
    with open(os.path.join(d, 'audio', 'vo.wav'), 'wb') as f:
        f.write(b'RIFF')
    p2 = dict(p, vo='audio/vo.wav')
    project.save(d, p2)
    # re-stamp the timing with the vo-included fingerprint so it is fresh now
    timing = json.load(open(os.path.join(d, 'timing.json')))
    timing['inputs'] = align.inputs_fingerprint(d, p2)
    json.dump(timing, open(os.path.join(d, 'timing.json'), 'w'))
    assert align.timing_is_fresh(d, p2)
    with open(os.path.join(d, 'audio', 'vo.wav'), 'ab') as f:
        f.write(b'new take')
    assert not align.timing_is_fresh(d, p2)  # a new VO take -> stale (discriminant: vo in fingerprint)


def test_render_reuses_fresh_timing(tmp_path, monkeypatch):
    """prepare_inputs with a fresh timing.json does not call the aligner again."""
    from motion_pipeline import render_cli
    d, p = mk(tmp_path / 'p')
    calls = {'n': 0}
    real_auto, real_est = align.align_auto, align.estimate_timings

    def counting_auto(*a, **k):
        calls['n'] += 1
        return real_auto(*a, **k)

    def counting_est(*a, **k):
        calls['n'] += 1
        return real_est(*a, **k)

    monkeypatch.setattr(align, 'align_auto', counting_auto)
    monkeypatch.setattr(align, 'estimate_timings', counting_est)
    render_cli.prepare_inputs(d)
    assert calls['n'] == 0, 'fresh timing must be reused, not re-aligned'
    # make it stale -> recompute
    with open(os.path.join(d, 'transcript.txt'), 'a') as f:
        f.write('more words\n')
    render_cli.prepare_inputs(d)
    assert calls['n'] == 1


def test_motion_graphics_step_disabled_until_fresh(tmp_path):
    from motion_pipeline.tui.app import MenuApp
    d, p = mk(tmp_path / 'p')
    app = MenuApp()
    app.project_dir = d
    assert app.graphics_step_enabled() is True
    os.remove(os.path.join(d, 'timing.json'))
    assert app.graphics_step_enabled() is False  # no timing -> disabled
    app.project_dir = None
    assert app.graphics_step_enabled() is False  # no project -> disabled


def test_menu_prepare_only_argv_exits_zero(tmp_path, monkeypatch):
    """Dogfood 2026-11-18: the menu's Task 21 job builds [--project, pd, --prepare-only] with NO
    --mode; the argparse guard required --mode, so every real Save-inputs failed (exit 2) and
    the graphics step never enabled. Delivery-shaped: the exact shipped argv, run for real."""
    import subprocess
    import sys

    from projfix import ROOT, make_project

    pd = make_project(tmp_path / 'p')
    env = dict(os.environ, PYTHONPATH=ROOT)
    r = subprocess.run([sys.executable, '-P', '-m', 'motion_pipeline.render_cli',
                        '--project', pd, '--prepare-only'],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0, r.stderr
    assert 'timings saved' in r.stdout
    assert os.path.isfile(os.path.join(pd, 'timing.json'))
