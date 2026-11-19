"""Task 19 (M6): the README must describe what EXISTS. Two guard shapes, both delivery-level:
1. retired claims must be absent (each was true once, is false now);
2. every `motion-pipeline --<flag>` the README mentions must be listed by the shipped
   `python -m motion_pipeline --help` (run as a subprocess — the real entry point)."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = open(os.path.join(ROOT, 'README.md')).read()

RETIRED = [
    r'falls back to square',   # 4:5 renders natively now
    r'\d+ passed',              # hardcoded suite count ("57 passed" etc.)
    r'steps 1-6',               # the menu is steps 0-7 now
    r'steps 0-6',
]


def test_retired_claims_absent():
    for pat in RETIRED:
        assert not re.search(pat, README), f'retired claim still in README: {pat!r}'


def test_readme_flags_exist_in_help():
    r = subprocess.run([sys.executable, '-P', '-m', 'motion_pipeline', '--help'],
                       capture_output=True, text=True, cwd=ROOT,
                       env={**os.environ, 'PYTHONPATH': ROOT})
    assert r.returncode == 0, r.stderr
    flags_in_readme = set(re.findall(r'motion-pipeline (--[a-z][a-z-]*)', README))
    assert flags_in_readme, 'README mentions no CLI flags — the guard needs at least one'
    for flag in sorted(flags_in_readme):
        assert flag in r.stdout, f'README mentions {flag} but --help does not list it'
