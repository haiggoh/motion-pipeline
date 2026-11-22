USAGE = """render_cli — the ONE render entry the menu (background test + full render) and users call.

usage: python -m motion_pipeline.render_cli --project DIR --mode test|full [--variant NAME|all]
                                            [--out DIR] [--dry-run]
       python -m motion_pipeline.render_cli --check            report the render toolchain, exit 0/3
       python -m motion_pipeline.render_cli --setup [--dry-run] install it (user cache, never the package)

Steps for a render: preflight the toolchain -> build the transcript model + timing from the
project's transcript (aligned to the voiceover when one is attached, else estimated) ->
generate the scene pages for each variant -> tools/render_scene.sh (same code path for test
and full). --variant default: test -> 'default', full -> every variant in project.json.

Toolchain (hyperframes + node), resolved in order:
  MP_HYPERFRAMES      path to the hyperframes binary (set but missing -> exit 2, named)
  <package>/node_modules/.bin/hyperframes   (a dev checkout after `npm install`)
  $MP_TOOLCHAIN_DIR or ~/.cache/motion-pipeline/toolchain  (what --setup installs; outside the
                      package, so `brew upgrade` never wipes it)
  MP_CHROME_DIR       chrome-headless-shell root (default ~/.cache/motion-pipeline/chrome);
                      used when present, else hyperframes' own browser resolution.
Exit: 0 ok · 2 bad args / invalid override · 3 missing dependency or project input · else the
renderer's own exit code.
"""
__doc__ = USAGE
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE_PIN = '24.19.0'
CHROME_PIN = '156.0.8078.4'
CHROME_SUBPATH = (f'chrome-headless-shell/mac_arm-{CHROME_PIN}/chrome-headless-shell-mac-arm64/'
                  'chrome-headless-shell')


class Missing(Exception):
    pass


def hf_pin():
    with open(os.path.join(PKG_ROOT, 'tools', 'versions.lock.json')) as f:
        return json.load(f)['hyperframes']


def toolchain_dir():
    d = os.environ.get('MP_TOOLCHAIN_DIR')
    return d or os.path.join(os.path.expanduser('~'), '.cache', 'motion-pipeline', 'toolchain')


def cache_root():
    """The app-wide user cache (~/.cache/motion-pipeline); node/ffmpeg fallback binaries live
    under it. Env MP_CACHE_DIR overrides (set-but-missing fails loudly)."""
    d = os.environ.get('MP_CACHE_DIR')
    if d:
        if not os.path.isdir(d):
            raise ValueError(f'MP_CACHE_DIR is set but is not a directory: {d}')
        return d
    return os.path.join(os.path.expanduser('~'), '.cache', 'motion-pipeline')


def chrome_root():
    return os.environ.get('MP_CHROME_DIR') or os.path.join(os.path.expanduser('~'), '.cache',
                                                           'motion-pipeline', 'chrome')


def chrome_path():
    return os.path.join(chrome_root(), CHROME_SUBPATH)


def find_hyperframes():
    env = os.environ.get('MP_HYPERFRAMES')
    if env:
        if not os.access(env, os.X_OK):
            raise ValueError(f'MP_HYPERFRAMES is set but is not an executable: {env}')
        return env
    for base in (PKG_ROOT, toolchain_dir()):
        p = os.path.join(base, 'node_modules', '.bin', 'hyperframes')
        if os.access(p, os.X_OK):
            return p
    raise Missing('hyperframes — run: motion-pipeline --setup-render  '
                  f'(installs hyperframes@{hf_pin()} into {toolchain_dir()})')


def node_bin_dir():
    """fnm pin first; else a PATH node with major >= 22 (Task 14); else Missing naming it."""
    fnm = os.path.join(os.path.expanduser('~'), '.local', 'share', 'fnm', 'node-versions',
                       f'v{NODE_PIN}', 'installation', 'bin')
    if os.access(os.path.join(fnm, 'node'), os.X_OK):
        return fnm
    node = shutil.which('node')
    if node:
        v = None
        try:
            v = subprocess.run([node, '--version'], capture_output=True, text=True,
                               timeout=10).stdout.strip()
            major = int(v.lstrip('v').split('.')[0])
        except Exception:
            major = 0
        if major >= 22:
            return os.path.dirname(node)
        if v is None:
            # the probe itself failed (timeout/crash) — never an UnboundLocalError here
            # (0.6.3 dogfood: intermittent >10s node startups crashed the render)
            raise Missing(f'node at {node} did not report a version — run: brew install node')
        raise Missing(f'node ≥22 — run: brew install node (found {v} at {node})')
    # 2026-11-22 fallback for non-Homebrew installs: the pinned node tarball in the app cache
    cached = os.path.join(cache_root(), 'node', f'v{NODE_PIN}', 'bin')
    if os.access(os.path.join(cached, 'node'), os.X_OK):
        return cached
    raise Missing('node ≥22 — run: brew install node, or `motion-pipeline --setup-render` '
                  '(installs the pinned node tarball into the app cache)')


NODE_TARBALL_URL = 'https://nodejs.org/dist/v{NODE_PIN}/node-v{NODE_PIN}-darwin-arm64.tar.gz'
FFMPEG_STATIC_URL = 'https://evermeet.cx/ffmpeg/ffmpeg-{FFMPEG_PIN}-macos-arm64.zip'
FFMPEG_PIN = '7.1'   # pinned static build (evermeet.cx); verified downloadable 2026-11-22


def ffmpeg_bin():
    """ffmpeg from PATH (brew or otherwise) or the static cache build (non-Homebrew fallback)."""
    found = shutil.which('ffmpeg')
    if found:
        return found
    cached = os.path.join(cache_root(), f'ffmpeg-{FFMPEG_PIN}-macos-arm64', 'ffmpeg')
    if os.access(cached, os.X_OK):
        return cached
    return None


def _ensure_toolchain_bins():
    """Download the pinned node tarball and the static ffmpeg build into the app cache
    (non-Homebrew fallbacks). Returns the dirs to put on PATH, or raises Missing."""
    import tarfile
    root = cache_root()
    node_dir = os.path.join(root, 'node', f'v{NODE_PIN}')
    node_ok = os.access(os.path.join(node_dir, 'bin', 'node'), os.X_OK)
    ff_dir = os.path.join(root, f'ffmpeg-{FFMPEG_PIN}-macos-arm64')
    ff_ok = os.access(os.path.join(ff_dir, 'ffmpeg'), os.X_OK)
    if node_ok and ff_ok:
        return [os.path.join(node_dir, 'bin'), ff_dir]
    os.makedirs(root, exist_ok=True)
    if not node_ok:
        url = NODE_TARBALL_URL.format(NODE_PIN=NODE_PIN)
        r = subprocess.run(['curl', '-fsSL', url, '-o', os.path.join(root, 'node.tgz')],
                           capture_output=True, timeout=600)
        if r.returncode != 0:
            raise Missing(f'node tarball download failed — run: brew install node ({r.stderr.decode()[-150:]})')
        with tarfile.open(os.path.join(root, 'node.tgz')) as tf:
            tf.extractall(os.path.join(root, 'node'), filter='data')
    if not ff_ok:
        url = FFMPEG_STATIC_URL.format(FFMPEG_PIN=FFMPEG_PIN)
        r = subprocess.run(['curl', '-fsSL', url, '-o', os.path.join(root, 'ffmpeg.zip')],
                           capture_output=True, timeout=600)
        if r.returncode != 0:
            raise Missing(f'ffmpeg static build download failed — run: brew install ffmpeg ({r.stderr.decode()[-150:]})')
        r = subprocess.run(['ditto', '-x', '-k', os.path.join(root, 'ffmpeg.zip'), root],
                           capture_output=True, timeout=300)
        if r.returncode != 0:
            raise Missing(f'cannot unzip the ffmpeg static build: {r.stderr.decode()[-150:]}')
        os.chmod(os.path.join(ff_dir, 'ffmpeg'), 0o755)   # zips don't carry the exec bit
    return [os.path.join(node_dir, 'bin'), ff_dir]


def preflight():
    """-> (env for the renderer, report lines). Raises Missing / ValueError."""
    ff = ffmpeg_bin()
    if not ff:
        raise Missing('ffmpeg — run: brew install ffmpeg, or `motion-pipeline --setup-render` '
                      '(installs a static build into the app cache)')
    for tool in ('ffprobe',):
        if not shutil.which(tool):
            # ffprobe ships with the same package as ffmpeg; PATH one wins, else cache copy
            cached_ffprobe = os.path.join(os.path.dirname(ff), 'ffprobe')
            if not os.access(cached_ffprobe, os.X_OK):
                raise Missing(f'{tool} — run: brew install ffmpeg, or `motion-pipeline --setup-render`')
    hf = find_hyperframes()
    node = node_bin_dir()
    env = dict(os.environ)
    env['PATH'] = os.pathsep.join([node, os.path.dirname(hf), os.path.dirname(ff),
                                   env.get('PATH', '')])
    chrome = chrome_path()
    lines = [f'hyperframes: {hf}', f'node: {node}', f'ffmpeg: {ff}']
    if os.path.isfile(chrome):
        env['HYPERFRAMES_BROWSER_PATH'] = chrome
        lines.append(f'chrome: {chrome}')
    else:
        lines.append('chrome: hyperframes default (pinned chrome-headless-shell not installed)')
    return env, lines


PROGRESS_STAGES = ('transcript', 'decode', 'align', 'snap', 'generate')
_PROGRESS_RE = re.compile(r'^progress: (\d+)/(\d+) (\w+)$')


def parse_progress(line):
    """'progress: <done>/<total> <stage>' -> (done, total, stage); None for any other line."""
    m = _PROGRESS_RE.match(line.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(3)


class Progress:
    """Emits 'progress: <i>/<total> <stage>' lines (flush=True) for the stages that will run
    this run (total fixed per run: snap only for the whisper engine)."""

    def __init__(self, stages):
        self.stages = list(stages)
        self.i = 0

    def __call__(self, stage):
        self.i += 1
        print(f'progress: {self.i}/{len(self.stages)} {stage}', flush=True)


def prepare_inputs(project_dir, progress=None):
    """Build transcript_model.json + timing.json from the project's transcript (+ voiceover).
    Task 21: when timing.json is fresh (inputs fingerprint matches), re-aligning is skipped.
    Task 17 (B4): emits progress stage lines via the optional progress callback."""
    from . import align, project, transcript
    p = project.load(project_dir)
    tpath = os.path.join(project_dir, p.get('transcript') or 'transcript.txt')
    if not os.path.isfile(tpath):
        raise Missing(f'transcript {tpath} — set it in step 5 (Transcript + voiceover)')
    if progress:
        progress('transcript')
    model = transcript.load(tpath)
    with open(os.path.join(project_dir, 'transcript_model.json'), 'w') as f:
        json.dump(model, f)
    if align.timing_is_fresh(project_dir, p):
        timing = json.load(open(os.path.join(project_dir, 'timing.json')))
        print('timing.json is current', flush=True)
    else:
        vo = p.get('vo')
        if progress:
            progress('decode')
        if vo:
            vpath = vo if os.path.isabs(vo) else os.path.join(project_dir, vo)
            if not os.path.isfile(vpath):
                raise Missing(f'voiceover {vpath} — fix it in step 5 or clear the field')
            timing = align.align_auto(vpath, model, p, progress=progress)  # whisper when installed
        else:
            if progress:
                progress('align')     # estimated timing: no real decode, but the stage exists
            timing = align.estimate_timings(model, wpm=p.get('wpm', 140))
        timing['inputs'] = align.inputs_fingerprint(project_dir, p)  # Task 21
        align.save_timing(os.path.join(project_dir, 'timing.json'), timing)
    return p


def check_graphics(project_dir):
    """Task 22: validate the AI manifest (+ SFX + licences) and that every referenced file is used.
    exit 0 ok / 1 problems listed / 3 project error."""
    from . import ai_layer
    from . import project as pm
    try:
        pm.load(project_dir)
        timing = json.load(open(os.path.join(project_dir, 'timing.json'))) \
            if os.path.isfile(os.path.join(project_dir, 'timing.json')) else {'words': []}
        model = json.load(open(os.path.join(project_dir, 'transcript_model.json'))) \
            if os.path.isfile(os.path.join(project_dir, 'transcript_model.json')) \
            else {'sections': [], 'words': timing.get('words', [])}
        entries = ai_layer.load_manifest(project_dir, model['words'])
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f'check-graphics: project error: {e}', file=sys.stderr)
        return 3
    # every ai_graphics file must be referenced by a manifest entry
    gdir = os.path.join(project_dir, ai_layer.DIR)
    referenced = {g['file'] for g in entries}
    problems = []
    # determinism lint (waypoint optional-check-graphics, user-approved 2026-11-19): the
    # renderer seeks frames, so AI scripts must not use rAF/timers/Date/unseeded random or
    # the network. MP.random(seed) is the seeded path and must NOT trip the Math.random rule.
    import re as _re
    det_rules = [
        (_re.compile(r'\brequestAnimationFrame\s*\('), 'requestAnimationFrame'),
        (_re.compile(r'\bsetTimeout\s*\('), 'setTimeout'),
        (_re.compile(r'\bsetInterval\s*\('), 'setInterval'),
        (_re.compile(r'\bnew\s+Date\b|\bDate\.(now|parse)\s*\('), 'Date'),
        (_re.compile(r'\bMath\.random\s*\('), 'unseeded Math.random (use MP.random(seed))'),
        (_re.compile(r'\b(fetch|XMLHttpRequest|WebSocket|sendBeacon)\b|\bimport\s*\('), 'network'),
    ]
    if os.path.isdir(gdir):
        for root, _dirs, files in os.walk(gdir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), gdir)
                if rel.startswith('sfx/') or rel == 'manifest.json':
                    continue
                if rel not in referenced:
                    problems.append(f'unreferenced file: {rel}')
                if rel.endswith(('.js', '.html')):
                    with open(os.path.join(root, f), encoding='utf-8') as fh:
                        for ln, line in enumerate(fh, 1):
                            for pat, label in det_rules:
                                if pat.search(line):
                                    problems.append(f'{rel}:{ln}: nondeterministic — {label}')
                                    break
    # sfx field/licence checks already run inside load_manifest
    if problems:
        for pr in problems:
            print(f'check-graphics: {pr}', file=sys.stderr)
        return 1
    print(f'check-graphics: OK — {len(entries)} graphic(s) declared, all files referenced')
    return 0


def render_test(project_dir, section=None, from_s=None, to_s=None, draft=False, dry_run=False):
    """Task 22: render one scene span of the AI-test path into <project>/scratch/ai-test/.
    Patches the page's data-duration to E-S and registers MP.tl.tweenFromTo(S, E); no gates,
    no masters touched. Prints the plan (always) and runs render_scene.sh unless --dry-run."""
    from . import generate, project
    project.load(project_dir)  # validates the project, refuses foreign keys
    generate.generate(project_dir, 'default')
    scenes = json.load(open(os.path.join(project_dir, 'src', 'scenes.json')))
    scene = next((s for s in scenes if s['name'] == section), scenes[0] if scenes else None)
    if scene is None:
        print(f'render-test: no scenes in src/scenes.json', file=sys.stderr)
        return 3
    S = from_s if from_s is not None else scene['start']
    E = to_s if to_s is not None else scene['end']
    if E <= S:
        print(f'render-test: empty span {S}-{E}', file=sys.stderr)
        return 2
    page_path = os.path.join(project_dir, 'src', scene['file'])
    html = open(page_path).read()
    dur = f'{E - S:.3f}'
    html = re.sub(r'data-duration="[\d.]+"', f'data-duration="{dur}"', html, count=1)
    inject = (f'<script>window.__test_span=[{S:.3f},{E:.3f}];'
              f'window.__timelines[Object.keys(window.__timelines)[0]]'
              f'=gsap.timeline({{paused:true}}).add(window.MP.tl.tweenFromTo({S:.3f},{E:.3f}));</script>')
    if '</head>' in html:
        html = html.replace('</head>', inject + '</head>', 1)
    out_dir = os.path.join(project_dir, 'scratch', 'ai-test')
    print(f'render-test: {scene["slug"]} {S:.3f}-{E:.3f} data-duration={dur} -> {out_dir}')
    if dry_run:
        print('render-test: inject ' + inject)  # exact bytes that would be injected
        return 0  # plan only — stage and render nothing
    os.makedirs(out_dir, exist_ok=True)
    tmp_proj = os.path.join(out_dir, '_proj')
    if os.path.isdir(tmp_proj):
        import shutil as _sh
        _sh.rmtree(tmp_proj)
    os.makedirs(os.path.join(tmp_proj, 'src'), exist_ok=True)
    import shutil as _sh
    _sh.copy(os.path.join(project_dir, 'project.json'), os.path.join(tmp_proj, 'project.json'))
    _sh.copytree(os.path.join(project_dir, 'src'), os.path.join(tmp_proj, 'src'), dirs_exist_ok=True)
    open(os.path.join(tmp_proj, 'src', scene['file']), 'w').write(html)
    open(os.path.join(tmp_proj, 'src', 'scenes.json'), 'w').write(json.dumps(
        [dict(scene, start=S, end=E)]))
    for f in ('transcript_model.json', 'timing.json'):
        src = os.path.join(project_dir, f)
        if os.path.isfile(src):
            _sh.copy(src, os.path.join(tmp_proj, f))
    cmd = ['bash', os.path.join(PKG_ROOT, 'tools', 'render_scene.sh'), '--project', tmp_proj,
           '--variant', 'default', '--mode', 'test', '--out', os.path.join(out_dir, f'{scene["slug"]}_{S:.1f}-{E:.1f}.mov')]
    if draft:
        cmd.append('--banded')  # placeholder for draft quality; real draft flag handled by toolchain
    # helper scripts need this interpreter's deps (numpy/PIL) — same MP_PYTHON contract as
    # render(); AND the toolchain PATH from preflight, or render_scene.sh exits 3 with
    # "hyperframes not on PATH" when run standalone via --render-test (dogfood 2026-11-21)
    try:
        pf_env, _ = preflight()
    except Missing:
        pf_env = dict(os.environ)
    rc = subprocess.call(cmd, env={**pf_env, 'MP_PYTHON': sys.executable})
    return rc


def remux(project_dir, variant=None, out=None):
    """--mode remux (Task 15): re-mux every scene .mov with the CURRENT VO/SFX, reading the video
    stream from the existing .mov (bit-exact copy). Refuses when spans changed or a .mov is
    missing (exit 3); a video-hash mismatch leaves the original untouched (exit 7)."""
    from . import audio_mux
    from . import project as pm
    p = pm.load(project_dir)
    variant = variant or 'default'
    out = out or os.path.join(project_dir, 'renders', variant)
    scenes = json.load(open(os.path.join(project_dir, 'src', 'scenes.json')))
    info_path = os.path.join(out, 'render_info.json')
    if os.path.isfile(info_path):
        old = json.load(open(info_path)).get('scenes')
        now = [{'file': s['file'], 'start': s['start'], 'end': s['end']} for s in scenes]
        if old != now:
            print('remux refused: scene spans changed since the render — re-render needed (exit 3)',
                  file=sys.stderr)
            return 3
    vo = p.get('vo')
    if vo and not os.path.isabs(vo):
        vo = os.path.join(project_dir, vo)
    timing = json.load(open(os.path.join(project_dir, 'timing.json')))
    model = json.load(open(os.path.join(project_dir, 'transcript_model.json')))
    cues = audio_mux.sfx_cues(project_dir, timing, model)
    for s in scenes:
        mov = os.path.join(out, s['file'][:-5] + '.mov')
        if not os.path.isfile(mov):
            print(f'remux refused: {mov} missing — re-render needed (exit 3)', file=sys.stderr)
            return 3
        tmp = mov + '.tmp'
        if not audio_mux.remux_scene(mov, tmp, s['start'], s['end'], vo, cues):
            os.remove(tmp)
            print(f'remux: video-stream hash mismatch for {mov} — original kept untouched (exit 7)',
                  file=sys.stderr)
            return 7
        os.replace(tmp, mov)
    movs = [os.path.join(out, s['file'][:-5] + '.mov') for s in scenes]
    audio_mux.preview(movs, os.path.join(out, f'{variant}_preview.mp4'))
    audio_mux.write_timeline(os.path.join(out, 'timeline.json'), scenes, p['fps'])
    _write_sequence(project_dir, p, out, variant)  # remux rewrites the sequence too
    if p.get('full_master'):
        ok, frames = audio_mux.join([dict(s, file=m) for s, m in zip(scenes, movs, strict=True)],
                                    os.path.join(out, f'{variant}_full.mov'), vo, cues)
        want = sum(round((s['end'] - s['start']) * p['fps']) for s in scenes)
        if not ok or frames != want:
            print(f'[render_cli] joined master SKIPPED: concat frames {frames} != {want} '
                  '(re-encode is forbidden, D2)', file=sys.stderr)
    return 0


def prepare_test_project(project_dir):
    """Task 8 (spec A4): build the scratch project for a background TEST render at
    <project>/scratch/bg-test/_proj, rebuilt on every call. Copies project.json (with
    vo: null — a voiceover never applies to the sample), scheme.json, variants/, fonts/
    (whatever exists) and writes transcript_model.json + timing.json: the real transcript's
    FIRST section when readable, else the built-in sample; timings are estimated at the
    project's wpm either way (a test render is about the look). The real project's own
    transcript_model.json / timing.json / src/ are never touched."""
    import shutil

    from . import align, project, sample_text, transcript
    p = project.load(project_dir)
    scratch = os.path.join(project_dir, 'scratch', 'bg-test', '_proj')
    if os.path.isdir(scratch):
        shutil.rmtree(scratch)
    os.makedirs(scratch)
    p2 = dict(p)
    p2['vo'] = None
    p2['transcript'] = None   # review finding: nothing in the test path may re-read the real transcript
    with open(os.path.join(scratch, 'project.json'), 'w') as f:
        json.dump(p2, f, indent=2)
        f.write('\n')
    src = os.path.join(project_dir, 'scheme.json')
    if os.path.isfile(src):
        shutil.copy(src, os.path.join(scratch, 'scheme.json'))
    for d in ('variants', 'fonts'):
        src = os.path.join(project_dir, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(scratch, d))
    # transcript: the real first section when readable, else the built-in sample
    tpath = os.path.join(project_dir, p.get('transcript') or 'transcript.txt')
    model = None
    if os.path.isfile(tpath):
        try:
            model = transcript.load(tpath)
        except (ValueError, OSError, json.JSONDecodeError):
            model = None
    if model and model.get('sections'):
        first = model['sections'][0]['name']
        model = {'sections': [s for s in model['sections'] if s['name'] == first][:1],
                 'words': [w for w in model['words'] if w.get('section') == first]}
    else:
        zones = [z for z in (p.get('zones') or []) if z.get('aspect', p['aspect']) == p['aspect']]
        model = transcript.parse(sample_text.sample_markup(zones[0].get('section') if zones else None))
    with open(os.path.join(scratch, 'transcript_model.json'), 'w') as f:
        json.dump(model, f)
    timing = align.estimate_timings(model, wpm=p.get('wpm', 140))
    align.save_timing(os.path.join(scratch, 'timing.json'), timing)
    return scratch


def render(project_dir, mode, variant=None, out=None, dry_run=False, full_master=None):
    from . import audio_mux, generate, project
    env = dict(os.environ)
    if full_master is not None:
        env['FULL_MASTER'] = '1' if full_master else '0'
    if not dry_run:
        env, lines = preflight()
        for line in lines:
            print(f'[render_cli] {line}', flush=True)
    # render_scene.sh's helper scripts (chroma gate, zone gate, audio mux) need THIS
    # interpreter's deps (numpy, PIL) — bare `python3` is the system one and has neither.
    # Set AFTER preflight(): it rebinds env, and a setdefault before that rebind is lost
    # (found 2026-11-19: the menu path still died on ModuleNotFoundError numpy).
    env.setdefault('MP_PYTHON', sys.executable)
    if mode == 'test':
        # Task 8 (A4): a test render runs on the SCRATCH project and needs no transcript;
        # the real project's inputs/model/src stay byte-identical
        p = project.load(project_dir)
        work = prepare_test_project(project_dir)
    else:
        p = prepare_inputs(project_dir)
        work = project_dir
    variants = p['variants'] if (variant == 'all' or (variant is None and mode == 'full')) \
        else [variant or 'default']
    rc = 0
    for v in variants:
        print(f'[render_cli] generate variant {v}', flush=True)
        # Task 12 test_frames mode: a test render caps every scene at 60 frames (E7)
        generate.generate(work, v, max_seconds=(60 / p['fps']) if mode == 'test' else None)
        vout = (out if len(variants) == 1 else os.path.join(out, v)) if out \
            else os.path.join(project_dir, 'renders', v)
        cmd = ['bash', os.path.join(PKG_ROOT, 'tools', 'render_scene.sh'), '--project', work,
               '--variant', v, '--mode', mode, '--out', vout]
        if dry_run:
            cmd.append('--dry-run')
        print('[render_cli] ' + ' '.join(cmd), flush=True)
        rc = subprocess.call(cmd, env=env)
        if rc:
            return rc
        scenes = json.load(open(os.path.join(work, 'src', 'scenes.json')))
        audio_mux.write_timeline(os.path.join(vout, 'timeline.json'), scenes, p['fps'])
        _write_sequence(project_dir, p, vout, v)  # Task 15c: Premiere-importable FCP 7 XML
    return rc


def _write_sequence(project_dir, p, vout, variant):
    """Write <variant>_sequence.xml (FCP 7 XML) next to timeline.json (Task 15c)."""
    from . import premiere_xml
    tl_path = os.path.join(vout, 'timeline.json')
    if not os.path.isfile(tl_path):
        return
    scenes = json.load(open(tl_path))
    for s in scenes:
        s['file'] = os.path.join(vout, s['file'])  # absolute paths (Premiere relinks if moved)
    full = os.path.join(vout, f'{variant}_full.mov')
    premiere_xml.write_sequence(os.path.join(vout, f'{variant}_sequence.xml'),
                                f"{p['name']} – {variant}", scenes, p['fps'],
                                p['resolution'][0], p['resolution'][1],
                                full_master=full if (p.get('full_master') and os.path.isfile(full))
                                else None)


def setup(dry_run=False):
    tc = toolchain_dir()
    if not dry_run:
        try:
            bins = _ensure_toolchain_bins()   # 2026-11-22: node + ffmpeg fallbacks for non-brew
            print(f'[render_cli] fallback bins in app cache: {bins}', flush=True)
        except Missing as e:
            print(f'[render_cli] fallback binaries unavailable ({e}) — continuing with PATH tools',
                  flush=True)
    cmds = [['npm', 'install', '--prefix', tc, f'hyperframes@{hf_pin()}'],
            ['npx', '--yes', '@puppeteer/browsers', 'install', f'chrome-headless-shell@{CHROME_PIN}',
             '--path', chrome_root()]]
    for c in cmds:
        print('[render_cli] ' + ' '.join(c), flush=True)
        if not dry_run:
            node = node_bin_dir()
            env = dict(os.environ, PATH=os.pathsep.join([node, os.environ.get('PATH', '')]))
            os.makedirs(tc, exist_ok=True)
            rc = subprocess.call(c, env=env)
            if rc:
                return rc
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='motion_pipeline.render_cli', description=USAGE.split('\n')[0],
                                 epilog=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project')
    ap.add_argument('--mode', choices=('test', 'full', 'remux'))
    ap.add_argument('--variant')
    ap.add_argument('--out')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--setup', action='store_true')
    ap.add_argument('--prepare-only', action='store_true',
                   help='transcript model + timing + generate the default variant, no render')
    ap.add_argument('--check-graphics', metavar='DIR',
                   help='validate ai_graphics manifest + SFX + licences; exit 0 ok / 1 problems / 3 project error')
    ap.add_argument('--render-test', metavar='DIR')
    ap.add_argument('--section', help='with --render-test: render only this section')
    ap.add_argument('--from', dest='from_s', type=float, help='with --render-test: span start (s)')
    ap.add_argument('--to', dest='to_s', type=float, help='with --render-test: span end (s)')
    ap.add_argument('--draft', action='store_true', help='with --render-test: draft quality')
    ap.add_argument('--full-master', dest='full_master', action='store_true', default=None,
                   help='override the joined-master opt-in for this run')
    ap.add_argument('--no-full-master', dest='full_master', action='store_false')
    a = ap.parse_args(argv)
    try:
        if a.check:
            _, lines = preflight()
            print('\n'.join(lines))
            return 0
        if a.setup:
            return setup(a.dry_run)
        if a.check_graphics:
            return check_graphics(os.path.abspath(a.check_graphics))
        if a.render_test:
            return render_test(os.path.abspath(a.render_test), a.section, a.from_s, a.to_s, a.draft,
                               a.dry_run)
        if a.prepare_only:
            from . import align_whisper, generate
            from . import project as _pm
            pd = os.path.abspath(a.project)
            _p = _pm.load(pd)
            whisper = bool(_p.get('vo')) and bool(align_whisper.find_engine()) \
                and _p.get('aligner', 'auto') in ('whisper', 'auto')
            stages = PROGRESS_STAGES if whisper else [s for s in PROGRESS_STAGES if s != 'snap']
            prog = Progress(stages)
            prepare_inputs(pd, progress=prog)  # transcript model + timing (writes them)
            prog('generate')
            generate.generate(pd, 'default')
            import json as _json
            timing = _json.load(open(os.path.join(os.path.abspath(a.project), 'timing.json')))
            model = _json.load(open(os.path.join(os.path.abspath(a.project), 'transcript_model.json')))
            print(f'timings saved — {len(model["words"])} words, {len(model["sections"])} sections, '
                  f'engine {timing["method"]}', flush=True)
            return 0
        if not a.project or not a.mode:
            ap.error('--project and --mode are required (or use --check / --check-graphics / --render-test / --prepare-only / --setup)')
        if a.mode == 'remux':
            return remux(os.path.abspath(a.project), a.variant, a.out)
        return render(os.path.abspath(a.project), a.mode, a.variant, a.out, a.dry_run,
                      full_master=a.full_master)
    except Missing as e:
        print(f'missing dependency: {e}', file=sys.stderr)
        return 3
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
