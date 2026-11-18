"""The release asset contract (ship wiring, QC 2026-11-18): dist/mp-<version>.tar.gz is built
with `git archive` (deterministic — the tap formula pins its sha256, so two builds MUST be
byte-identical) and must contain EVERY tracked file (a .gitattributes export-ignore that
silently drops a shipped file must go RED here, not at brew-install time)."""
import hashlib
import os
import subprocess
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = 'mp-head/'


def _build(out):
    subprocess.run(['git', 'archive', f'--prefix={PREFIX}', '-o', str(out), 'HEAD'],
                   check=True, cwd=ROOT)
    return hashlib.sha256(open(out, 'rb').read()).hexdigest()


def test_release_tarball_deterministic_and_complete(tmp_path):
    h1 = _build(tmp_path / 'a.tar.gz')
    h2 = _build(tmp_path / 'b.tar.gz')
    assert h1 == h2, 'git archive is not byte-stable across builds'
    with tarfile.open(tmp_path / 'a.tar.gz') as tf:
        names = {m.name[len(PREFIX):] for m in tf.getmembers()}
    tracked = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
    missing = [f for f in tracked if f not in names]
    assert not missing, f'tracked files missing from the release tarball: {missing[:8]}'
