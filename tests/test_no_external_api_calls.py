"""Guard (user rule 2026-11-21): tests must NEVER call a provider API outside the shared
rate limiter — an unthrottled test call pushes the machine over the limit when the limiter
is already maxed out. This repo's tests make no provider calls at all (the launcher tests
only parse mock inventory rows); this test fails if that ever changes.

Allowlist: files that mention provider names as FIXTURE DATA (mock roster rows) or env
names (MP_FREE_AGENTS detection) — they never open a connection. Anything reading
~/.api_keys or importing litellm/requests-to-a-provider fails.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWLIST = {  # mention provider names only as data/env, never as calls
    'tests/test_free_agents_launcher.py',
    'tests/test_graphics_screen.py',
    'tests/test_no_external_api_calls.py',  # the guard's own BANNED patterns
}
BANNED = [r'api_keys', r'litellm', r'requests\.(get|post)', r'urllib\.request', r'curl ',
          r'https?://[^\s]*nvidia', r'generativelanguage']


def test_no_external_api_calls_in_tests():
    offenders = []
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'tests')):
        if '__pycache__' in dirpath:
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
            if rel in ALLOWLIST:
                continue
            text = open(os.path.join(dirpath, f)).read()
            for pat in BANNED:
                if re.search(pat, text, re.IGNORECASE):
                    offenders.append(f'{rel}: /{pat}/')
    assert not offenders, 'tests must not call provider APIs outside the rate limiter: ' + '; '.join(offenders)
