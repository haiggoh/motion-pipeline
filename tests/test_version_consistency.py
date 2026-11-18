"""Version surfaces must agree (repo-owned pin, ship wiring 2026-11-18).

rtc-ship's tool-bumped surfaces are VERSION + release-manifest.json (+ the CHANGELOG top); its
surface resolver has no reader for a .py file or a PEP 621 [project] table, so pyproject.toml
and motion_pipeline/__init__.py are pinned HERE instead: an incomplete version bump fails the
suite gate instead of shipping drifted surfaces."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_version_surfaces_agree():
    versions = {
        'VERSION': open(os.path.join(ROOT, 'VERSION')).read().strip(),
        'release-manifest.json': json.load(open(os.path.join(ROOT, 'release-manifest.json')))['version'],
        'pyproject.toml': re.search(r'^version\s*=\s*"([^"]+)"',
                                    open(os.path.join(ROOT, 'pyproject.toml')).read(), re.M).group(1),
        'motion_pipeline/__init__.py': re.search(r'^__version__\s*=\s*"([^"]+)"',
                                                 open(os.path.join(ROOT, 'motion_pipeline',
                                                                   '__init__.py')).read(), re.M).group(1),
        'CHANGELOG top': re.search(r'^##\s+\[?v?([0-9][0-9.]*)\]?',
                                   open(os.path.join(ROOT, 'CHANGELOG.md')).read(), re.M).group(1),
    }
    assert all(versions.values()), versions
    assert len(set(versions.values())) == 1, versions
