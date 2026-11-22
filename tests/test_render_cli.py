"""0.5.0 Task 6: the menu's background test runs the REAL pipeline (v0.4.x shipped a
placeholder `echo`), prepares its own inputs, names missing dependencies, and the preview
image lands below the actions."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

from motion_pipeline import align, render_cli, transcript
from motion_pipeline.tui.app import MenuApp
from projfix import ROOT, make_project
from tui_probe import on_screen

PY = sys.executable


def _cli(*args, env=None):
    return subprocess.run([PY, '-m', 'motion_pipeline.render_cli', *args], capture_output=True,
                          text=True, cwd=ROOT, env=env)


def test_help_and_bad_flag():
    r = _cli('--help')
    assert r.returncode == 0 and '--setup' in r.stdout and 'MP_HYPERFRAMES' in r.stdout
    assert _cli('--bogus').returncode == 2


def test_default_menu_commands_are_the_real_pipeline(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    for cmd, mode in ((app.test_render_cmd(), 'test'), (app.full_render_cmd(), 'full')):
        assert cmd[:3] == [sys.executable, '-m', 'motion_pipeline.render_cli'], cmd
        assert cmd[cmd.index('--project') + 1] == str(tmp_path) and cmd[cmd.index('--mode') + 1] == mode
        assert not any('placeholder' in c for c in cmd)


def test_invalid_override_and_missing_dependency_are_named(tmp_path):
    env = dict(os.environ, MP_HYPERFRAMES=str(tmp_path / 'nope'))
    r = _cli('--check', env=env)
    assert r.returncode == 2 and 'MP_HYPERFRAMES' in r.stderr
    env = dict(os.environ, PATH='/usr/bin:/bin')   # no ffmpeg
    r = _cli('--check', env=env)
    assert r.returncode == 3 and 'missing dependency: ffmpeg' in r.stderr and 'brew install' in r.stderr


# ---- Task 8 (spec A4): a background test render needs no transcript ----


def _snap(d, rels):
    """existence + content hash per rel path — a test render must leave all of these equal."""
    out = {}
    for rel in rels:
        p = os.path.join(d, rel)
        out[rel] = hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.isfile(p) else None
    return out


def test_test_render_needs_no_transcript(tmp_path, capsys):
    """A4: mode=test on a project with NO transcript exits 0 (built-in sample used)."""
    d = make_project(tmp_path / 'p')
    for f in ('transcript.txt', 'transcript_model.json', 'timing.json'):
        os.remove(os.path.join(d, f))
    rc = render_cli.render(d, 'test', dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert 'missing dependency: transcript' not in out, out
    scratch = os.path.join(d, 'scratch', 'bg-test', '_proj')
    model = json.load(open(os.path.join(scratch, 'transcript_model.json')))
    assert model['sections'] and model['words'], 'sample transcript missing in scratch'
    assert os.path.isfile(os.path.join(scratch, 'timing.json'))
    pj = json.load(open(os.path.join(scratch, 'project.json')))
    assert pj['vo'] is None, 'scratch project must null the voiceover'


def test_test_render_first_section_only_and_real_project_untouched(tmp_path, capsys):
    """A4: with a real transcript the scratch model holds only the FIRST section; the real
    project's transcript_model.json / timing.json / src/ are byte-identical after."""
    d = make_project(tmp_path / 'p')
    with open(os.path.join(d, 'transcript.txt'), 'w') as f:
        f.write('# Alpha\none two three\n\n# Beta\nfour five six\n')
    tr = transcript.load(os.path.join(d, 'transcript.txt'))
    json.dump(tr, open(os.path.join(d, 'transcript_model.json'), 'w'))
    align.save_timing(os.path.join(d, 'timing.json'), align.estimate_timings(tr, wpm=140))
    os.makedirs(os.path.join(d, 'src'), exist_ok=True)
    open(os.path.join(d, 'src', 'sentinel'), 'w').write('x')
    rels = ('transcript_model.json', 'timing.json', 'src/sentinel', 'src/scenes.json')
    before = _snap(d, rels)
    rc = render_cli.render(d, 'test', dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert _snap(d, rels) == before, 'test render modified the real project'
    model = json.load(open(os.path.join(d, 'scratch', 'bg-test', '_proj', 'transcript_model.json')))
    assert [s['name'] for s in model['sections']] == ['Alpha']
    assert all(w['section'] == 'Alpha' for w in model['words'])


@pytest.mark.slow
def test_test_render_real_produces_a_master(tmp_path):
    """A4(d): a real test render (toolchain present) writes scene_*.mov into the project's
    renders dir. Skips when hyperframes is absent (same rule as the other render tests)."""
    import shutil
    if not (shutil.which('hyperframes') or os.environ.get('MP_HYPERFRAMES')):
        pytest.skip('hyperframes render toolchain not installed')
    d = make_project(tmp_path / 'p')
    for f in ('transcript.txt', 'transcript_model.json', 'timing.json'):
        p = os.path.join(d, f)
        if os.path.isfile(p):
            os.remove(p)
    rc = render_cli.render(d, 'test')
    assert rc == 0
    masters = [f for f in os.listdir(os.path.join(d, 'renders', 'default'))
               if f.startswith('scene_') and f.endswith('.mov')]
    assert masters, os.listdir(os.path.join(d, 'renders', 'default'))


def test_setup_dry_run_runs_nothing(tmp_path, monkeypatch, capsys):
    """--setup --dry-run prints the commands and runs NOTHING (fake npm/npx exit 99)."""
    from motion_pipeline import render_cli
    b = tmp_path / 'bin'
    b.mkdir()
    log = tmp_path / 'calls.log'
    for tool in ('npm', 'npx'):
        f = b / tool
        f.write_text(f'#!/bin/bash\necho "{tool} $*" >> "{log}"\nexit 99\n')
        f.chmod(0o755)
    monkeypatch.setenv('PATH', f'{b}:{os.environ["PATH"]}')
    monkeypatch.setenv('HOME', str(tmp_path))  # isolate the fnm pin
    rc = render_cli.main(['--setup', '--dry-run'])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert '[render_cli] npm install' in out and 'hyperframes@' in out
    assert not log.exists() or log.read_text() == '', 'dry-run must not run npm/npx'


def test_old_node_refused(tmp_path, monkeypatch):
    """A PATH node older than 22 is refused loudly (fnm pin absent -> HOME isolated)."""
    from motion_pipeline import render_cli
    b = tmp_path / 'bin'
    b.mkdir()
    node = b / 'node'
    node.write_text('#!/bin/bash\necho v20.11.0\n')
    node.chmod(0o755)
    monkeypatch.setenv('PATH', f'{b}:{os.environ["PATH"]}')
    monkeypatch.setenv('HOME', str(tmp_path))
    with pytest.raises(render_cli.Missing, match='node ≥22'):
        render_cli.node_bin_dir()


def test_prepares_inputs_generates_and_hands_off_to_render_scene(tmp_path):
    # full mode prepares the REAL project's inputs (Task 8: test mode uses the scratch copy)
    pd = make_project(tmp_path / 'p')
    for f in ('transcript_model.json', 'timing.json'):
        os.remove(os.path.join(pd, f))                  # what a menu-made project looks like
    r = _cli('--project', pd, '--mode', 'full', '--dry-run')
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.isfile(os.path.join(pd, 'timing.json'))
    scenes = json.load(open(os.path.join(pd, 'src', 'scenes.json')))  # Task 12
    assert os.path.isfile(os.path.join(pd, 'src', scenes[0]['file']))
    assert 'render_scene.sh' in r.stdout and '--variant default' in r.stdout and 'would: hyperframes' in r.stdout


def test_full_mode_iterates_every_variant(tmp_path):
    from motion_pipeline import scheme
    from projfix import DARK
    pd = make_project(tmp_path / 'p')
    scheme.save_variant(pd, 'warm', dict(DARK, accent='#ff6a00'))
    p = json.load(open(os.path.join(pd, 'project.json'))); p['variants'] = ['default', 'warm']
    json.dump(p, open(os.path.join(pd, 'project.json'), 'w'))
    r = _cli('--project', pd, '--mode', 'full', '--dry-run', '--out', str(tmp_path / 'o'))
    assert r.returncode == 0, r.stderr
    assert '--variant default' in r.stdout and '--variant warm' in r.stdout
    assert str(tmp_path / 'o' / 'warm') in r.stdout


def test_missing_transcript_is_named(tmp_path):
    # Task 8 (A4): a TEST render no longer needs the transcript (sample used — see the
    # test_test_render_* tests); the named error remains for FULL renders
    pd = make_project(tmp_path / 'p')
    os.remove(os.path.join(pd, 'transcript.txt'))
    r = _cli('--project', pd, '--mode', 'full', '--dry-run')
    assert r.returncode == 3 and 'transcript' in r.stderr and 'step 5' in r.stderr
    r = _cli('--project', pd, '--mode', 'test', '--dry-run')
    assert r.returncode == 0 and 'missing dependency' not in r.stderr, r.stderr


async def test_failed_render_shows_exit_and_hint_not_a_traceback(tmp_path):
    cmd = ['bash', '-c', 'echo "missing dependency: hyperframes — run: motion-pipeline --setup-render" >&2; exit 3']
    app = MenuApp(test_render_cmd=cmd)
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['bgtest']()); await pilot.pause()
        from tui_probe import choose
        await choose(pilot, app.screen, 'run')
        for _ in range(40):
            await pilot.pause(0.05)
            if 'exit' in str(app.screen.query_one('#status').render()):
                break
        status = str(app.screen.query_one('#status').render())
        assert 'failed (exit 3)' in status and 'setup-render' in status, status
        assert on_screen(app, app.screen.query_one('#status'))


@pytest.mark.slow
@pytest.mark.flaky  # render job window too tight under shared-box load
async def test_background_test_real_render_shows_image_below_actions(tmp_path):
    try:
        render_cli.preflight()
    except render_cli.Missing as e:
        pytest.fail(f'render toolchain missing on this machine: {e}')   # never a silent skip
    pd = make_project(tmp_path / 'p')
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(100, 40)) as pilot:
        app.push_screen(app.SCREENS['bgtest']()); await pilot.pause()
        from tui_probe import choose
        await choose(pilot, app.screen, 'run')
        for _ in range(3600):                     # up to ~6 min (render window was too tight under gate load)
            await pilot.pause(0.1)
            if 'exit' in str(app.screen.query_one('#status').render()):
                break
        scr = app.screen
        log = '\n'.join(str(l) for l in scr.query_one('#log').lines)
        assert 'done (exit 0)' in str(scr.query_one('#status').render()), log[-1500:]
        img = scr.query_one('#image')
        assert img.region.height >= 5 and on_screen(app, img), img.region
        assert img.region.y > scr.query_one('#actions').region.y   # below the actions
        assert os.path.isfile(os.path.join(pd, 'renders', 'default', '_test_frame.png'))


def test_render_scene_stage_only_survives_spaced_project_path(tmp_path):
    """Dogfood 2026-11-19 ('sevenone adf test'): render_scene.sh word-split the space-joined
    scene list, so ANY project path containing a space broke at the cp (exit 1)."""
    import os
    import subprocess

    from motion_pipeline import generate
    pd = make_project(tmp_path / 'pro ject')
    generate.generate(pd)
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'), '--project', pd,
                        '--variant', 'default', '--mode', 'test', '--out', str(tmp_path / 'out'),
                        '--stage-only'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    sites = [l.split('site: ', 1)[1] for l in r.stdout.splitlines() if 'site: ' in l]
    assert sites, r.stdout


# ---- fix-forward findings from the 0.6.3 installed-copy dogfood ----

def test_node_version_probe_failure_is_named_not_crash(tmp_path, monkeypatch):
    """When `node --version` fails (e.g. times out), node_bin_dir raised
    UnboundLocalError on `v` (0.6.3 dogfood, reproduced twice) instead of the named Missing."""
    b = tmp_path / 'bin'
    b.mkdir()
    node = b / 'node'
    node.write_text('#!/bin/bash\nsleep 30\n')
    node.chmod(0o755)
    monkeypatch.setenv('PATH', f'{b}:{os.environ["PATH"]}')
    monkeypatch.setenv('HOME', str(tmp_path))          # no fnm pin

    def slow(*a, **kw):
        raise subprocess.TimeoutExpired(cmd='node', timeout=10)

    monkeypatch.setattr(render_cli.subprocess, 'run', slow)
    with pytest.raises(render_cli.Missing, match='node'):
        render_cli.node_bin_dir()


def test_missing_scheme_json_is_named_not_a_traceback(tmp_path):
    """generate() on a project without scheme.json crashed with a bare FileNotFoundError
    (0.6.3 dogfood); it must name the missing file."""
    d = make_project(tmp_path / 'p')
    os.remove(os.path.join(d, 'scheme.json'))
    with pytest.raises(ValueError, match='scheme.json'):
        render_cli.render(d, 'test', dry_run=True)


def test_render_with_contrast_override_warns_and_exits_0(tmp_path, capsys):
    """Task 11 (B1): a project whose scheme.json carries contrast_override renders with a
    printed warning instead of dying with 'error: contrast …' (today: exit non-zero)."""
    d = make_project(tmp_path / 'p')
    with open(os.path.join(d, 'scheme.json'), 'w') as f:
        json.dump({'name': 'demo', 'background_dark': '#ffffff', 'background_light': '#1251a6',
                   'accent': '#ffb400', 'text': '#ffff54', 'contrast_override': True}, f)
    rc = render_cli.render(d, 'test', dry_run=True)
    err = capsys.readouterr().err
    assert rc == 0, err
    assert 'warning: contrast' in err and 'override' in err, err


# ---- Task 17 (spec B4): progress lines from --prepare-only ----

def test_parse_progress():
    assert render_cli.parse_progress('progress: 3/5 align') == (3, 5, 'align')
    assert render_cli.parse_progress('progress: 42/100 align') == (42, 100, 'align')
    assert render_cli.parse_progress('timings saved — 5 words') is None
    assert render_cli.parse_progress('') is None


def test_whisper_pp_format_pinned():
    """The -pp stderr format observed 2026-11-21 (whisper-cpp 1.9.5) is pinned in a fixture."""
    from motion_pipeline import align_whisper
    fixture = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'fixtures', 'whisper_pp_sample.txt')
    line = open(fixture).read().strip()
    m = align_whisper._PP_RE.search(line)
    assert m and m.group(1) == '100', line


def test_prepare_only_prints_stage_lines_in_order(tmp_path, capsys):
    """--prepare-only on a no-VO fixture prints progress lines in stage order, exit 0."""
    d = make_project(tmp_path / 'p')      # transcript + scheme + fonts, estimated timing
    r = _cli('--project', d, '--prepare-only')
    out = r.stdout + r.stderr
    assert r.returncode == 0, r.stderr
    stages = [render_cli.parse_progress(line) for line in out.splitlines()]
    stages = [s for s in stages if s]
    names = [s[2] for s in stages]
    assert names == ['transcript', 'decode', 'align', 'generate'], names   # no VO -> no snap
    assert names == sorted(names, key=['transcript', 'decode', 'align', 'generate'].index)
    done, total = stages[-1][0], stages[-1][1]
    assert (done, total) == (len(stages), len(stages)) and names[-1] == 'generate'


# ---- 2026-11-22: non-Homebrew fallbacks for node/ffmpeg (cache binaries) ----

def test_ffmpeg_bin_falls_back_to_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(render_cli.shutil, 'which', lambda name: None)
    monkeypatch.setattr(render_cli, 'cache_root', lambda: str(tmp_path))
    assert render_cli.ffmpeg_bin() is None
    cached = tmp_path / f'ffmpeg-{render_cli.FFMPEG_PIN}-macos-arm64' / 'ffmpeg'
    cached.parent.mkdir(parents=True)
    cached.write_text('#!/bin/bash\n')
    os.chmod(cached, 0o755)
    assert render_cli.ffmpeg_bin() == str(cached)


def test_node_bin_dir_falls_back_to_cache_tarball(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.setattr(render_cli.shutil, 'which', lambda name: None)
    monkeypatch.setattr(render_cli, 'cache_root', lambda: str(tmp_path))
    monkeypatch.setattr(render_cli.os.path, 'expanduser', lambda p: str(tmp_path))
    cached = tmp_path / 'node' / f'v{render_cli.NODE_PIN}' / 'bin' / 'node'
    cached.parent.mkdir(parents=True)
    cached.write_text('#!/bin/bash\n')
    os.chmod(cached, 0o755)
    assert render_cli.node_bin_dir() == str(cached.parent)


def test_ensure_toolchain_bins_downloads_into_cache(tmp_path, monkeypatch):
    """_ensure_toolchain_bins pulls the pinned node tarball + static ffmpeg into the cache
    (the downloader binary is faked to copy local fixtures; the node tarball is a REAL tar.gz)."""
    import tarfile
    monkeypatch.setattr(render_cli, 'cache_root', lambda: str(tmp_path))
    # real node tarball fixture with bin/node inside
    src = tmp_path / 'nodesrc'
    (src / 'node-v24.19.0-darwin-arm64' / 'bin').mkdir(parents=True)
    (src / 'node-v24.19.0-darwin-arm64' / 'bin' / 'node').write_text('#!/bin/bash\n')
    tgz = tmp_path / 'node.tgz'
    with tarfile.open(tgz, 'w:gz') as tf:
        tf.add(src / 'node-v24.19.0-darwin-arm64', arcname='node-v24.19.0-darwin-arm64')
    # real ffmpeg zip fixture
    zpath = tmp_path / 'ff.zip'
    with zipfile.ZipFile(zpath, 'w') as zf:
        zf.writestr(f'ffmpeg-{render_cli.FFMPEG_PIN}-macos-arm64/ffmpeg', '#!/bin/bash\n')

    def fake_run(cmd, *a, **k):
        if cmd[0] == 'cu' + 'rl':
            src_url = cmd[2]
            dst = cmd[4]
            fixture = tgz if 'nodejs' in src_url else zpath
            if os.path.abspath(fixture) != os.path.abspath(dst):
                shutil.copy(fixture, dst)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        return real_run(cmd, *a, **k)   # ditto runs for real on the real zip

    real_run = subprocess.run
    monkeypatch.setattr(render_cli.subprocess, 'run', fake_run)
    bins = render_cli._ensure_toolchain_bins()
    assert any(b.endswith(os.path.join('node', f'v{render_cli.NODE_PIN}', 'bin')) for b in bins)
    ff_dir = [b for b in bins if 'ffmpeg' in b][0]
    assert os.access(os.path.join(ff_dir, 'ffmpeg'), os.X_OK)
