"""config.py — per-user settings: where projects live, which project was open last.

  ~/.config/motion-pipeline/config.json   {"projects_root": "<abs path>", "last_project": "<abs path>"}
  MP_CONFIG_DIR   overrides the config directory; set but missing -> ValueError naming it
                  (never a silent fallback to the default).

The projects root is asked once on first launch (first-run screen) and remembered. It may
never be inside the installed package (Homebrew replaces libexec on every upgrade — v0.4.x
kept projects there, so an upgrade would wipe them).
"""
import json
import os

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo / libexec
SUGGESTED_ROOT = os.path.join('~', 'motion-pipeline', 'projects')


def config_dir() -> str:
    env = os.environ.get('MP_CONFIG_DIR')
    if env:
        if not os.path.isdir(env):
            raise ValueError(f'MP_CONFIG_DIR is set but is not a directory: {env}')
        return env
    return os.path.join(os.path.expanduser('~'), '.config', 'motion-pipeline')


def _path():
    return os.path.join(config_dir(), 'config.json')


def load() -> dict:
    p = _path()
    if not os.path.isfile(p):
        return {}
    with open(p) as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f'{p}: want a JSON object, got {type(cfg).__name__}')
    return cfg


def _save(cfg: dict) -> None:
    d = config_dir()
    os.makedirs(d, exist_ok=True)
    tmp = _path() + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(cfg, f, indent=2)
        f.write('\n')
    os.replace(tmp, _path())


def inside_package(path: str) -> bool:
    p = os.path.realpath(os.path.expanduser(path))
    root = os.path.realpath(PKG_ROOT)
    return p == root or p.startswith(root + os.sep)


def projects_root():
    """The remembered projects root, or None when not chosen yet (first run)."""
    return load().get('projects_root')


def set_projects_root(path: str) -> str:
    p = os.path.abspath(os.path.expanduser(path.strip()))
    if not path.strip():
        raise ValueError('projects folder is empty')
    if inside_package(p):
        raise ValueError(f'projects folder may not be inside the installed package ({PKG_ROOT}) — '
                         'it is replaced on every upgrade')
    os.makedirs(p, exist_ok=True)
    cfg = load()
    cfg['projects_root'] = p
    _save(cfg)
    return p


def last_project():
    p = load().get('last_project')
    return p if p and os.path.isfile(os.path.join(p, 'project.json')) else None


def set_last_project(path: str) -> None:
    cfg = load()
    cfg['last_project'] = os.path.abspath(path)
    _save(cfg)
