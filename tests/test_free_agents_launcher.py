"""Task 23 tests (plan 2026-11-16): free-agents detection ladder (env -> highest numeric cache
-> PATH resolver; bad env fails loudly), the live-resolved model ladder with recorded
inventory fixtures, and the osascript launch command — the AppleScript string round-trips
through shlex.split to the exact argv, prompt in link form, effort explicit, FA_PRE_TRUST=1."""
import json
import os
import shlex

import pytest

from motion_pipeline import free_agents

INV = [
    ['nvidia-mistral-large4', 'nvidia', 'Mistral Large 4 (Le Chonk)', 'unknown', '0', '1', '0', 'mistralai/mistral-large-4-1t-a52b'],
    ['nvidia-glm53', 'nvidia', 'Z.ai GLM 5.3 Flash', 'unknown', '0', '1', '0', 'z-ai/glm-5.3-flash'],
    ['nvidia-gemini38', 'gemini', 'Gemini 3.8 Flash', 'unknown', '0', '1', '0', 'gemini-3.8-flash'],
    ['trial-model', 'nvidia', 'Trial Model', 'trial', '0', '1', '0', 'x/trial'],
    ['no-key-model', 'nvidia', 'No Key Model', 'unknown', '0', '0', '0', 'x/nokey'],
    ['broken-model', 'nvidia', 'Broken Model', 'unknown', '0', '1', '1', 'x/broken'],
]


def _mk_fa_root(root, inventory_rows=None, prefs=None, session_prefs=None):
    root = str(root)
    os.makedirs(os.path.join(root, '.claude-plugin'), exist_ok=True)
    open(os.path.join(root, '.claude-plugin', 'plugin.json'), 'w').write('{}')
    bindir = os.path.join(root, 'bin')
    os.makedirs(bindir, exist_ok=True)
    open(os.path.join(bindir, 'launch-remote-window.sh'), 'w').write('#!/bin/sh\n')
    inv = os.path.join(bindir, 'remote-session.sh')
    with open(inv, 'w') as f:
        f.write('#!/bin/sh\nif [ "$1" = "--inventory" ]; then\n')
        for r in (inventory_rows or []):
            f.write('printf \'%s\\n\' ' + shlex.quote('\t'.join(r)) + '\n')
        f.write('fi\n')
    os.chmod(inv, 0o755)
    cfg = os.path.join(root, 'config')
    os.makedirs(cfg, exist_ok=True)
    if prefs is not None:
        json.dump(prefs, open(os.path.join(cfg, 'dispatch-preferences.json'), 'w'))
    if session_prefs is not None:
        json.dump(session_prefs, open(os.path.join(cfg, 'session-preferences.json'), 'w'))
    return root


def _fa(tmp_path, prefs=None, session_prefs=None, name='fa'):
    root = _mk_fa_root(tmp_path / name, inventory_rows=INV, prefs=prefs, session_prefs=session_prefs)
    return free_agents.detect(env={'MP_FREE_AGENTS': root}, home=str(tmp_path / 'h'), path='')


def test_detect_prefers_env_then_highest_numeric_cache(tmp_path):
    env_root = _mk_fa_root(tmp_path / 'env-root')
    fa = free_agents.detect(env={'MP_FREE_AGENTS': env_root}, home=str(tmp_path / 'empty'), path='')
    assert fa.root == env_root
    home = tmp_path / 'home'
    for ver in ('0.6.0', '0.59.3'):
        _mk_fa_root(home / '.claude/plugins/cache/market/free-agents' / ver)
    # version-TUPLE sort: (0,59,3) > (0,6,0) — never lexical
    fa = free_agents.detect(env={}, home=str(home), path='')
    assert fa.root.endswith(os.path.join('free-agents', '0.59.3')), fa.root
    # a cache dir without plugin.json is stale/corrupt and skipped (version via variable:
    # a literal versioned cache path in a committed file trips the hardcoded-path guard)
    stale_ver = '0.99.0'
    os.makedirs(home / '.claude/plugins/cache/market/free-agents' / stale_ver / 'bin')
    fa = free_agents.detect(env={}, home=str(home), path='')
    assert stale_ver not in fa.root


def test_bad_free_agents_env_fails_loudly(tmp_path):
    with pytest.raises(ValueError, match='MP_FREE_AGENTS'):
        free_agents.detect(env={'MP_FREE_AGENTS': str(tmp_path / 'nope')}, home=str(tmp_path), path='')


def test_detect_path_resolver_fallthrough(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    root = _mk_fa_root(tmp_path / 'resolved-root')
    rs = bindir / 'free-agents-resolve.sh'
    rs.write_text(f'#!/bin/sh\necho {root}\n')
    rs.chmod(0o755)
    fa = free_agents.detect(env={}, home=str(home), path=str(bindir))
    assert fa.root == root
    assert free_agents.detect(env={}, home=str(home), path=str(tmp_path / 'nowhere')) is None


def test_models_filter_then_inventory_order(tmp_path):
    fa = _fa(tmp_path)
    ms = free_agents.models(fa, env={})
    # trial rows, key_ok=0 and broken/retired rows are filtered out; rest keeps inventory order
    assert [m['alias'] for m in ms] == ['nvidia-mistral-large4', 'nvidia-glm53', 'nvidia-gemini38']
    assert all(m['key_ok'] and m['free'] for m in ms)


def test_models_ladder_session_config_then_dispatch_prefs_then_inventory(tmp_path):
    prefs = {'order': [{'id': 'nvidia-glm53'}, {'id': 'nvidia-mistral-large4'}, {'id': 'nvidia-gemini38'}]}
    fa = _fa(tmp_path, prefs=prefs)
    assert [m['alias'] for m in free_agents.models(fa, env={})] == \
        ['nvidia-glm53', 'nvidia-mistral-large4', 'nvidia-gemini38']
    # layer 1: session-preferences.json order wins over dispatch prefs
    fa = _fa(tmp_path, prefs=prefs, session_prefs={'order': ['nvidia-gemini38', 'nvidia-mistral-large4']}, name='fa2')
    assert [m['alias'] for m in free_agents.models(fa, env={})] == \
        ['nvidia-gemini38', 'nvidia-mistral-large4', 'nvidia-glm53']


def test_launch_builds_quoted_osascript_roundtrip(tmp_path):
    fa = _fa(tmp_path)
    project = "sevenone adf test & co's"  # spaces, & and an apostrophe — the user's real shape
    playbook_path = os.path.join(project, 'MOTION_GRAPHICS_PLAYBOOK.md')
    inner, argv, prompt = free_agents.build_launch(fa, 'nvidia-glm53', 'high', project, playbook_path)
    assert argv[0] == 'osascript' and argv[1] == '-e'
    script = argv[2]
    assert script.startswith('tell application "Terminal" to do script "')
    extracted = script[len('tell application "Terminal" to do script '):]
    assert extracted.startswith('"') and extracted.endswith('"')
    # unescape AppleScript string escaping (backslash first, then quote) and round-trip
    src = extracted[1:-1]
    out = []
    i = 0
    while i < len(src):
        if src[i] == '\\' and i + 1 < len(src):
            out.append(src[i + 1])
            i += 2
        else:
            out.append(src[i])
            i += 1
    inner_back = ''.join(out)
    assert inner_back == inner
    parts = shlex.split(inner)
    assert parts == ['cd', project, '&&', fa.launcher, 'nvidia-glm53', '--effort', 'high',
                     '--prompt', prompt]
    assert playbook_path in prompt and 'AskUserQuestion' in prompt
    # link form: --prompt carries the playbook path in the text; --prompt-file never used
    assert '--prompt' in parts and '--prompt-file' not in parts
    assert parts[parts.index('--effort') + 1] == 'high'  # explicit effort, never a stored default


def test_launch_pre_trusts_and_raises_on_osascript_failure(tmp_path):
    fa = _fa(tmp_path)
    seen = {}

    proj = str(tmp_path / 'p')
    pb = os.path.join(proj, 'MOTION_GRAPHICS_PLAYBOOK.md')

    def ok_runner(argv, env):
        seen['env'] = env

        class R:
            returncode = 0
            stderr = ''
        return R()

    free_agents.launch(fa, 'a', 'high', proj, pb, runner=ok_runner)
    assert seen['env'].get('FA_PRE_TRUST') == '1'

    def bad_runner(argv, env):
        class R:
            returncode = 1
            stderr = 'Automation permission denied'
        return R()

    with pytest.raises(RuntimeError, match='Automation permission denied'):
        free_agents.launch(fa, 'a', 'high', proj, pb, runner=bad_runner)
