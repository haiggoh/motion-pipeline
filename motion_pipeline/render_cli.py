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
        try:
            v = subprocess.run([node, '--version'], capture_output=True, text=True,
                               timeout=10).stdout.strip()
            major = int(v.lstrip('v').split('.')[0])
        except Exception:
            major = 0
        if major >= 22:
            return os.path.dirname(node)
        raise Missing(f'node ≥22 — run: brew install node (found {v} at {node})')
    raise Missing('node ≥22 — run: brew install node (the fnm pin is used when present)')


def preflight():
    """-> (env for the renderer, report lines). Raises Missing / ValueError."""
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise Missing(f'{tool} — run: brew install ffmpeg')
    hf = find_hyperframes()
    node = node_bin_dir()
    env = dict(os.environ)
    env['PATH'] = os.pathsep.join([node, os.path.dirname(hf), env.get('PATH', '')])
    chrome = chrome_path()
    lines = [f'hyperframes: {hf}', f'node: {node}', f'ffmpeg: {shutil.which("ffmpeg")}']
    if os.path.isfile(chrome):
        env['HYPERFRAMES_BROWSER_PATH'] = chrome
        lines.append(f'chrome: {chrome}')
    else:
        lines.append('chrome: hyperframes default (pinned chrome-headless-shell not installed)')
    return env, lines


def prepare_inputs(project_dir):
    """Build transcript_model.json + timing.json from the project's transcript (+ voiceover)."""
    from . import align, project, transcript
    p = project.load(project_dir)
    tpath = os.path.join(project_dir, p.get('transcript') or 'transcript.txt')
    if not os.path.isfile(tpath):
        raise Missing(f'transcript {tpath} — set it in step 5 (Transcript + voiceover)')
    model = transcript.load(tpath)
    with open(os.path.join(project_dir, 'transcript_model.json'), 'w') as f:
        json.dump(model, f)
    vo = p.get('vo')
    if vo:
        vpath = vo if os.path.isabs(vo) else os.path.join(project_dir, vo)
        if not os.path.isfile(vpath):
            raise Missing(f'voiceover {vpath} — fix it in step 5 or clear the field')
        timing = align.align(vpath, model)
    else:
        timing = align.estimate_timings(model, wpm=p.get('wpm', 140))
    align.save_timing(os.path.join(project_dir, 'timing.json'), timing)
    return p


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


def render(project_dir, mode, variant=None, out=None, dry_run=False, full_master=None):
    from . import audio_mux, generate
    env = dict(os.environ)
    if full_master is not None:
        env['FULL_MASTER'] = '1' if full_master else '0'
    if not dry_run:
        env, lines = preflight()
        for line in lines:
            print(f'[render_cli] {line}', flush=True)
    p = prepare_inputs(project_dir)
    variants = p['variants'] if (variant == 'all' or (variant is None and mode == 'full')) \
        else [variant or 'default']
    rc = 0
    for v in variants:
        print(f'[render_cli] generate variant {v}', flush=True)
        # Task 12 test_frames mode: a test render caps every scene at 60 frames (E7)
        generate.generate(project_dir, v, max_seconds=(60 / p['fps']) if mode == 'test' else None)
        cmd = ['bash', os.path.join(PKG_ROOT, 'tools', 'render_scene.sh'), '--project', project_dir,
               '--variant', v, '--mode', mode]
        if out:
            cmd += ['--out', out if len(variants) == 1 else os.path.join(out, v)]
        if dry_run:
            cmd.append('--dry-run')
        print('[render_cli] ' + ' '.join(cmd), flush=True)
        rc = subprocess.call(cmd, env=env)
        if rc:
            return rc
        vout = (out if len(variants) == 1 else os.path.join(out, v)) if out \
            else os.path.join(project_dir, 'renders', v)
        scenes = json.load(open(os.path.join(project_dir, 'src', 'scenes.json')))
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
        if not a.project or not a.mode:
            ap.error('--project and --mode are required (or use --check / --setup)')
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
