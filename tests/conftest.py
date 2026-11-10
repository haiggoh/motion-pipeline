"""Session tripwire: tests must never write into the repo's own projects/ folder (2026-11-10:
a menu test created projects/1/ via a cwd-relative default). Fails the session if the set of
files under projects/ changed. Each xdist worker checks its own session."""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.path.join(ROOT, 'projects')


def _snapshot():
    out = set()
    for d, _, files in os.walk(PROJECTS):
        out.update(os.path.relpath(os.path.join(d, f), ROOT) for f in files)
    if os.path.isdir(PROJECTS):
        out.add('projects/')
    return out


@pytest.fixture(autouse=True, scope='session')
def _projects_tripwire():
    before = _snapshot()
    yield
    after = _snapshot()
    assert after == before, f'tests wrote into the repo projects/ folder: {sorted(after ^ before)}'
