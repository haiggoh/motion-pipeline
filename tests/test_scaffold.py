"""Scaffold tests: the CLI --help contract and .gitignore coverage (Task 1)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args):
    return subprocess.run([sys.executable, '-m', 'motion_pipeline', *args],
                          capture_output=True, text=True, cwd=ROOT, timeout=30)


def test_help_exit_0():
    r = run_cli('--help')
    assert r.returncode == 0, r.stderr
    assert 'usage' in r.stdout.lower()


def test_unknown_flag_exit_2_with_usage_on_stderr():
    r = run_cli('--bogus')
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert 'usage' in r.stderr.lower()


def test_gitignore_covers_project_fonts_renders_scratch_venv():
    with open(os.path.join(ROOT, '.gitignore')) as f:
        lines = {line.strip() for line in f if line.strip() and not line.startswith('#')}
    for pat in ('projects/*/fonts/', 'renders/', 'scratch/', '.venv/'):
        assert pat in lines, f'.gitignore missing {pat!r}'
