"""0.5.0 Task 7: bin/motion-pipeline-dev runs the menu from THIS checkout (not the brew copy
on PATH), says which checkout + commit it runs, and fails loudly on a bad setup."""
import os
import subprocess

from projfix import ROOT

from motion_pipeline import __version__

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


def test_dev_launcher_ignores_cwd_package(tmp_path):
    """E11: a cwd containing a fake motion_pipeline package must NOT shadow this checkout —
    the launcher execs python with -P (sys.path[0] = cwd is dropped)."""
    fake_cwd = tmp_path / 'cwd'
    (fake_cwd / 'motion_pipeline').mkdir(parents=True)
    (fake_cwd / 'motion_pipeline' / '__init__.py').write_text(
        "raise RuntimeError('cwd package shadowed the real one')\n")
    r = subprocess.run([L, '--version'], capture_output=True, text=True, cwd=str(fake_cwd))
    assert r.returncode == 0 and __version__ in r.stdout, (r.returncode, r.stdout, r.stderr)
