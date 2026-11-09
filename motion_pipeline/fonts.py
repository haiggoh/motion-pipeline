"""fonts.py — font selection, role mapping, and the font gate (Task 3, design G4).

Bundled faces (OFL only) live in motion_pipeline/fonts/<Family>/ with the OFL file beside
them and resolve via importlib.resources — no system install needed. A project may instead
reference a client font from its own gitignored <project>/fonts/ folder (decide-question 2,
user-approved default): such a font passes the gate but is flagged licence='non-OFL' and the
menu shows a licence warning; it is never committed to this repo.

Role map (pinned in the plan): {role: {"family": str, "weight": int, "file": relpath}} for
roles headline, label, body, emphasis. Default weights: headline 700, label 600, body 400,
emphasis 700. The generator emits `font-family: <family>; font-weight: <weight>;` from this.
"""
import importlib.resources
import os

ROLES = ('headline', 'label', 'body', 'emphasis')
DEFAULT_WEIGHTS = {'headline': 700, 'label': 600, 'body': 400, 'emphasis': 700}
FACE_SUFFIX = {100: 'Thin', 400: 'Regular', 600: 'SemiBold', 700: 'Bold', 900: 'Black'}


def bundled_families():
    """Families bundled in this package (each dir under motion_pipeline/fonts/)."""
    root = importlib.resources.files('motion_pipeline') / 'fonts'
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def bundled_face(family, weight):
    """Path-like ref of a bundled face file, or None if that weight is not bundled."""
    name = FACE_SUFFIX.get(weight)
    if not name:
        return None
    root = importlib.resources.files('motion_pipeline') / 'fonts' / family
    if not root.is_dir():
        return None
    for p in root.iterdir():
        if p.name == f'{family}-{name}.ttf' or p.name == f'{family}-{name}.otf':
            return f'motion_pipeline/fonts/{family}/{p.name}'
    return None


def project_font_dir(project_dir):
    return os.path.join(project_dir, 'fonts')


def project_fonts(project_dir):
    """Font files in the project's gitignored fonts/ dir -> {family-ish name: path}."""
    d = project_font_dir(project_dir)
    if not os.path.isdir(d):
        return {}
    out = {}
    for f in sorted(os.listdir(d)):
        if f.lower().endswith(('.ttf', '.otf', '.woff2')):
            out[os.path.splitext(f)[0]] = os.path.join(d, f)
    return out


def default_role_map(family):
    return {role: {'family': family, 'weight': DEFAULT_WEIGHTS[role]}
            for role in ROLES}


def resolve_role_map(project_dir, family, role_weights=None):
    """Full pinned role map with resolved face files. Raises naming the role if a face is missing."""
    weights = dict(DEFAULT_WEIGHTS)
    if role_weights:
        weights.update(role_weights)
    pfonts = project_fonts(project_dir)
    out = {}
    for role in ROLES:
        w = weights[role]
        face = bundled_face(family, w)
        licence = 'OFL'
        if face is None:
            # fall back to a project-local client font of the family name
            cand = {k: v for k, v in pfonts.items() if k.lower().startswith(family.lower())}
            if cand:
                k = sorted(cand)[0]
                face = cand[k]
                licence = 'non-OFL (client font — not committed to this repo)'
            else:
                raise ValueError(f'font gate: no face for role {role!r} '
                                 f'(family {family!r}, weight {w}) — bundle it (OFL) or put a client '
                                 f'font into {project_font_dir(project_dir)}/')
        out[role] = {'family': family, 'weight': w, 'file': face, 'licence': licence}
    return out


def font_gate(project_dir, project_json=None):
    """Validate a project's font config; returns the resolved role map. Fails loudly per role."""
    cfg = (project_json or {}).get('fonts', {})
    family = cfg.get('family')
    if not family:
        raise ValueError("font gate: project.json has no fonts.family")
    return resolve_role_map(project_dir, family, cfg.get('roles'))


def audit_bundled_licences():
    """Every bundled family dir must contain an OFL file. Returns list of violations."""
    bad = []
    root = importlib.resources.files('motion_pipeline') / 'fonts'
    for fam in bundled_families():
        d = root / fam
        if not any(p.name.upper().startswith('OFL') for p in d.iterdir()):
            bad.append(fam)
    return bad
