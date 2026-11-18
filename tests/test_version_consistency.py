"""Version surfaces must agree (repo-owned pin, ship wiring 2026-11-18).

rtc-ship's tool-bumped surfaces are VERSION + release-manifest.json (+ the CHANGELOG top); its
surface resolver has no reader for a .py file or a PEP 621 [project] table, so pyproject.toml
and motion_pipeline/__init__.py are pinned HERE instead: an incomplete version bump fails the
suite gate instead of shipping drifted surfaces. Parsed, not first-match-grepped (QC
2026-11-18): pyproject via tomllib, exactly one __version__ assignment, CHANGELOG top = the
first `## ` heading, VERSION must be x.y.z."""
import json
import os
import re
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_version_surfaces_agree():
    versions = {
        'VERSION': open(os.path.join(ROOT, 'VERSION')).read().strip(),
        'release-manifest.json': json.load(open(os.path.join(ROOT, 'release-manifest.json')))['version'],
        'pyproject.toml': tomllib.load(open(os.path.join(ROOT, 'pyproject.toml'), 'rb'))['project']['version'],
        'motion_pipeline/__init__.py': _init_version(),
        'CHANGELOG top': re.search(r'^##[ \t]+\[?v?([0-9]+\.[0-9]+\.[0-9]+)\]?',
                                   open(os.path.join(ROOT, 'CHANGELOG.md')).read(), re.M).group(1),
    }
    assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', versions['VERSION']), versions
    assert all(versions.values()), versions
    assert len(set(versions.values())) == 1, versions


def _init_version():
    src = open(os.path.join(ROOT, 'motion_pipeline', '__init__.py')).read()
    ms = re.findall(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    assert len(ms) == 1, f'want exactly one __version__ assignment, got {ms}'
    return ms[0]
