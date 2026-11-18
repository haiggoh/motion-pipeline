"""free_agents.py — detect, query and launch free-agents (plan Task 23 / M5).

Portability rule (Playbook-portable-repos): never a hardcoded checkout path. Resolution order:
  1. MP_FREE_AGENTS env (must contain .claude-plugin/plugin.json + bin/launch-remote-window.sh;
     set-but-invalid -> ValueError naming it)
  2. highest NUMERIC version dir under ~/.claude/plugins/cache/*/free-agents/ that carries
     .claude-plugin/plugin.json (version-tuple sort: 0.59.3 > 0.6.0 — never lexical; cache
     dirs without plugin.json are stale/corrupt and skipped)
  3. free-agents-resolve.sh on PATH
Model lists are resolved LIVE through a preference ladder (never a hardcoded model id):
  (1) session order when the plugin config exposes one (FA_SESSION_ORDER env,
      config/session-preferences.json "order", or dispatch-preferences.json "session_order"),
  (2) dispatch-preferences order (FA_DISPATCH_PREFS / dispatch-preferences.local.json override),
  (3) raw --inventory order.
"""
import json
import os
import shlex
import subprocess


class FreeAgents:
    def __init__(self, root, launcher, inventory_cmd):
        self.root = root
        self.launcher = launcher
        self.inventory_cmd = list(inventory_cmd)


def _version_key(name):
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in name.split('.'))


def _mk(root):
    return FreeAgents(root=root,
                      launcher=os.path.join(root, 'bin', 'launch-remote-window.sh'),
                      inventory_cmd=[os.path.join(root, 'bin', 'remote-session.sh'), '--inventory'])


def detect(env=None, home=None, path=None):
    env = os.environ if env is None else env
    home = os.path.expanduser('~') if home is None else home
    path = os.environ.get('PATH') if path is None else path
    v = env.get('MP_FREE_AGENTS')
    if v:
        root = os.path.abspath(os.path.expanduser(v))
        if not (os.path.isfile(os.path.join(root, '.claude-plugin', 'plugin.json'))
                and os.path.isfile(os.path.join(root, 'bin', 'launch-remote-window.sh'))):
            raise ValueError(f'MP_FREE_AGENTS={v!r} is not a free-agents checkout: needs '
                             f'.claude-plugin/plugin.json and bin/launch-remote-window.sh')
        return _mk(root)
    cache = os.path.join(home, '.claude', 'plugins', 'cache')
    best = None
    if os.path.isdir(cache):
        for market in sorted(os.listdir(cache)):
            fad = os.path.join(cache, market, 'free-agents')
            if not os.path.isdir(fad):
                continue
            for ver in os.listdir(fad):
                root = os.path.join(fad, ver)
                if os.path.isfile(os.path.join(root, '.claude-plugin', 'plugin.json')):
                    if best is None or _version_key(ver) > _version_key(best[0]):
                        best = (ver, root)
    if best:
        return _mk(best[1])
    for d in (path or '').split(os.pathsep):
        if not d:
            continue
        cand = os.path.join(d, 'free-agents-resolve.sh')
        if os.path.isfile(cand):
            r = subprocess.run(['bash', cand], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return _mk(r.stdout.strip().splitlines()[0])
            break
    return None


def _inventory(fa):
    """remote-session.sh --inventory TSV, 8 fields (pinned live 2026-11-16/18, U7):
    alias, provider, display, tier, local-capable-hidden, key_ok, broken, catalog model id."""
    r = subprocess.run(fa.inventory_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'{os.path.basename(fa.inventory_cmd[0])} --inventory failed '
                           f'(exit {r.returncode}): {r.stderr.strip()[:300]}')
    rows = []
    for line in r.stdout.splitlines():
        f = line.split('\t')
        if len(f) < 8:
            continue
        alias, prov, disp, tier, _lc, key, br, model = f[:8]
        rows.append({'alias': alias, 'provider': prov, 'display': disp, 'tier': tier,
                     'key_ok': key == '1', 'free': tier not in ('trial', 'paid_only'),
                     'broken': br == '1', 'model': model})
    return rows


def _dispatch_prefs_path(fa, env):
    v = env.get('FA_DISPATCH_PREFS')
    if v:
        if not os.path.isfile(v):
            raise ValueError(f'FA_DISPATCH_PREFS={v!r} does not exist')
        return v
    local = os.path.join(fa.root, 'config', 'dispatch-preferences.local.json')
    if os.path.isfile(local):
        return local
    p = os.path.join(fa.root, 'config', 'dispatch-preferences.json')
    return p if os.path.isfile(p) else None


def _ladder(fa, env):
    """Preference ladder resolved live; [] when no layer exposes an order."""
    v = env.get('FA_SESSION_ORDER')
    if v:
        return [x for x in v.replace(',', ' ').split() if x]
    sp = os.path.join(fa.root, 'config', 'session-preferences.json')
    if os.path.isfile(sp):
        try:
            order = json.load(open(sp)).get('order')
            if isinstance(order, list) and order:
                return [str(x) for x in order]
        except (ValueError, OSError):
            pass
    dp = _dispatch_prefs_path(fa, env)
    if dp:
        try:
            d = json.load(open(dp))
            so = d.get('session_order')
            if isinstance(so, list) and so:
                return [str(x) for x in so]
            order = d.get('order')
            if isinstance(order, list):
                return [str(e.get('id', e)) if isinstance(e, dict) else str(e) for e in order]
        except (ValueError, OSError):
            pass
    return []


def models(fa, env=None):
    """Session-launch candidates: key_ok AND free-tier AND not broken/retired, ordered by the
    ladder (session order -> dispatch prefs -> raw inventory order)."""
    env = os.environ if env is None else env
    rows = [r for r in _inventory(fa) if r['key_ok'] and r['free'] and not r['broken']]
    ladder = _ladder(fa, env)

    def sort_key(item):
        idx, r = item
        for i, lid in enumerate(ladder):
            if lid == r['alias'] or lid == r['model']:
                return (0, i, idx)
        return (1, 0, idx)

    return [r for _, r in sorted(enumerate(rows), key=sort_key)]


FIRST_PROMPT = ('Read {playbook} first and follow it exactly. Begin with section 0: ask me '
                'your design questions with AskUserQuestion before you create or change any file.')


def _applescript_string(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def build_launch(fa, alias, effort, project_dir, playbook):
    """The exact inner shell command, the osascript argv and the first prompt (separated so
    tests can round-trip the quoting)."""
    prompt = FIRST_PROMPT.format(playbook=playbook)
    inner = 'cd {cd} && {launcher} {alias} --effort {effort} --prompt {prompt}'.format(
        cd=shlex.quote(project_dir), launcher=shlex.quote(fa.launcher), alias=shlex.quote(alias),
        effort=shlex.quote(effort), prompt=shlex.quote(prompt))
    script = 'tell application "Terminal" to do script ' + _applescript_string(inner)
    return inner, ['osascript', '-e', script], prompt


def launch(fa, alias, effort, project_dir, playbook, runner=None):
    """Open a NEW Terminal.app window running the launcher (always interactive, never headless).
    The first prompt is always passed in LINK form (--prompt with the playbook path inside the
    text — never --prompt-file) and --effort is always explicit. FA_PRE_TRUST=1 pre-trusts the
    project folder. osascript failure -> RuntimeError quoting stderr + the manual fallback."""
    inner, argv, _prompt = build_launch(fa, alias, effort, project_dir, playbook)
    env = dict(os.environ, FA_PRE_TRUST='1')
    run = runner or (lambda a, e: subprocess.run(a, capture_output=True, text=True, env=e))
    r = run(argv, env)
    if r.returncode != 0:
        raise RuntimeError(f'osascript failed (exit {r.returncode}): '
                           f'{(getattr(r, "stderr", "") or "").strip()} — manual fallback: {inner}')
    return r
