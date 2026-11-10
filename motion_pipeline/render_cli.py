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
    fnm = os.path.join(os.path.expanduser('~'), '.local', 'share', 'fnm', 'node-versions',
                       f'v{NODE_PIN}', 'installation', 'bin')
    if os.access(os.path.join(fnm, 'node'), os.X_OK):
        return fnm
    node = shutil.which('node')
    if node:
        return os.path.dirname(node)
    raise Missing(f'node — run: brew install fnm && fnm install {NODE_PIN}')


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
        timing = align.estimate_timings(model, wpm=140)
    align.save_timing(os.path.join(project_dir, 'timing.json'), timing)
    return p


def render(project_dir, mode, variant=None, out=None, dry_run=False):
    from . import generate
    env = dict(os.environ)
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
        generate.generate(project_dir, v)
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
    return rc


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
    ap.add_argument('--mode', choices=('test', 'full'))
    ap.add_argument('--variant')
    ap.add_argument('--out')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--setup', action='store_true')
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
        return render(os.path.abspath(a.project), a.mode, a.variant, a.out, a.dry_run)
    except Missing as e:
        print(f'missing dependency: {e}', file=sys.stderr)
        return 3
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
