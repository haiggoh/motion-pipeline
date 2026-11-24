"""Task 1 (0.8.0 plan): stage package graphics + vendor plugins into every render site.

The generated page loads <script src="gsap.min.js">, DrawSVGPlugin.min.js and mp_lib.js,
but render_scene.sh staged only vendor/gsap.min.js + src/*.js — so DrawSVGPlugin.min.js and
mp_lib.js 404'd in every render (the plan's dated finding). RED before the fix: the staged
site is missing both files; a project src file named like a package file wins silently.
"""
import os
import re
import subprocess

from projfix import ROOT, make_project

from motion_pipeline import generate

VENV_BIN = os.path.join(ROOT, '.venv', 'bin')

SCRIPT_SRC = re.compile(r'<script src="([^"]+)"')


def _stage(project_dir, out_dir):
    env = dict(os.environ)
    env['PATH'] = VENV_BIN + ':' + env['PATH']
    r = subprocess.run(['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'),
                        '--project', project_dir, '--variant', 'default', '--mode', 'test',
                        '--out', str(out_dir), '--stage-only'],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    sites = [line.split('site: ', 1)[1] for line in r.stdout.splitlines() if 'site: ' in line]
    assert sites, r.stdout
    return sites[0], r


def _make_project(tmp_path, name='proj'):
    pd = make_project(str(tmp_path / name))
    generate.generate(pd)
    return pd


def test_staged_site_resolves_every_script_src(tmp_path):
    """Every <script src> in the staged page must exist in the staged site."""
    pd = _make_project(tmp_path)
    site, _ = _stage(pd, tmp_path / 'out')
    page = open(os.path.join(site, 'index.html')).read()
    srcs = SCRIPT_SRC.findall(page)
    # the page really loads the package files — otherwise this test proves nothing
    assert 'DrawSVGPlugin.min.js' in srcs and 'mp_lib.js' in srcs, srcs
    missing = [s for s in srcs if not os.path.isfile(os.path.join(site, s))]
    assert not missing, f'staged site is missing script files: {missing} (site={site})'


def test_staged_page_api_order(tmp_path):
    """On the STAGED site (not just the generated src), window.MP precedes src="mp_lib.js"."""
    pd = _make_project(tmp_path)
    site, _ = _stage(pd, tmp_path / 'out')
    page = open(os.path.join(site, 'index.html')).read()
    i_mp = page.index('window.MP =')
    i_lib = page.index('src="mp_lib.js"')
    assert i_mp < i_lib, 'window.MP must be defined before mp_lib.js loads (its IIFE reads it)'


def test_package_file_overrides_project_copy_loudly(tmp_path):
    """Review focus 3: a project src file named like a package file loses, with a stderr line."""
    pd = _make_project(tmp_path)
    pkg = os.path.join(ROOT, 'motion_pipeline', 'graphics', 'mp_lib.js')
    fake = os.path.join(pd, 'src', 'mp_lib.js')
    with open(fake, 'w') as f:
        f.write('// project copy — must lose to the package file\n')
    site, r = _stage(pd, tmp_path / 'out')
    with open(os.path.join(site, 'mp_lib.js')) as f:
        staged = f.read()
    with open(pkg) as f:
        package = f.read()
    assert staged == package, 'package mp_lib.js must override the project src copy'
    assert 'staging: package mp_lib.js overrides project src/mp_lib.js' in r.stderr, r.stderr[-400:]
