"""0.5.0 Task 7: bin/motion-pipeline-dev runs the menu from THIS checkout (not the brew copy
on PATH), says which checkout + commit it runs, and fails loudly on a bad setup."""
import os
import subprocess

from motion_pipeline import __version__
from projfix import ROOT

L = os.path.join(ROOT, 'bin', 'motion-pipeline-dev')


def run(*args, env=None, exe=L):
    return subprocess.run([exe, *args], capture_output=True, text=True, env=env or dict(os.environ))


def test_help_names_launcher_checkout_and_env():
    r = run('--help')
    assert r.returncode == 0
    for needle in ('motion-pipeline-dev', ROOT.replace(os.path.expanduser('~'), '~'), 'MP_DEV_PYTHON'):
        assert needle in r.stdout, (needle, r.stdout)


def test_version_comes_from_this_checkout_with_banner():
    r = run('--version')
    assert r.returncode == 0 and r.stdout.strip() == f'motion_pipeline {__version__}', r.stdout
    assert 'motion-pipeline (DEV) — checkout' in r.stderr and '@ ' in r.stderr


def test_unknown_flag_exits_2():
    assert run('--bogus').returncode == 2


def test_works_through_a_symlink(tmp_path):
    link = tmp_path / 'mpd'
    link.symlink_to(L)
    r = run('--version', exe=str(link))
    assert r.returncode == 0 and __version__ in r.stdout and ROOT.replace(os.path.expanduser('~'), '~') in r.stderr


def test_bad_python_override_and_missing_venv(tmp_path):
    r = run('--version', env=dict(os.environ, MP_DEV_PYTHON=str(tmp_path / 'nope')))
    assert r.returncode == 2 and 'MP_DEV_PYTHON' in r.stderr
    # a copy of the launcher in a checkout without .venv
    fake = tmp_path / 'repo'
    (fake / 'bin').mkdir(parents=True)
    (fake / 'motion_pipeline').mkdir()
    (fake / 'bin' / 'motion-pipeline-dev').write_text(open(L).read())
    os.chmod(fake / 'bin' / 'motion-pipeline-dev', 0o755)
    r = run('--version', exe=str(fake / 'bin' / 'motion-pipeline-dev'))
    assert r.returncode == 3 and '.venv' in r.stderr and 'uv' in r.stderr
