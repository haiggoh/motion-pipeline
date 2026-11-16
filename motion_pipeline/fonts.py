"""fonts.py — per-role font selection, legacy migration, and the font gate (Task 8, design G4).

Bundled faces (OFL only) live in motion_pipeline/fonts/<Family>/ with the OFL file beside
them. A project may instead reference a client font from its own gitignored
<project>/fonts/ folder: such a font passes the gate but is flagged
licence='non-OFL (client font — not committed to this repo)' and the menu shows a licence
warning; it is never committed to this repo.

Role map (pinned in the plan, Task 8): project.json fonts =
{"roles": {role: {"family", "weight", "file", "index"}}} for roles headline, label, body,
emphasis. `file` is the bundled ref `motion_pipeline/fonts/...` or `fonts/<name>` relative to
the project. Default weights: headline 700, label 600, body 400, emphasis 700.
"""
import importlib.resources
import os
import re

from PIL import ImageFont

from . import font_index

ROLES = ('headline', 'label', 'body', 'emphasis')
DEFAULT_WEIGHTS = {'headline': 700, 'label': 600, 'body': 400, 'emphasis': 700}
FACE_SUFFIX = {100: 'Thin', 400: 'Regular', 600: 'SemiBold', 700: 'Bold', 900: 'Black'}
CLIENT_LICENCE = 'non-OFL (client font — not committed to this repo)'


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
    """Font files in the project's gitignored fonts/ dir -> {file name stem: path}."""
    d = project_font_dir(project_dir)
    if not os.path.isdir(d):
        return {}
    out = {}
    for f in sorted(os.listdir(d)):
        if f.lower().endswith(('.ttf', '.otf', '.woff2', '.ttc')):
            out[os.path.splitext(f)[0]] = os.path.join(d, f)
    return out


def _family_faces(project_dir, family):
    """[(weight, label, file_ref, index, licence)] for a family: bundled set first, then the
    project's own fonts/ dir. Client faces resolve by their CONTENT (family+OS/2 weight via
    the face index), never by file name (Review Focus 5)."""
    out = []
    root = importlib.resources.files('motion_pipeline') / 'fonts' / family
    if root.is_dir():
        suffix2weight = {v: k for k, v in FACE_SUFFIX.items()}
        for p in sorted(root.iterdir()):
            m = re.match(rf'{re.escape(family)}-(.+)\.(ttf|otf)$', p.name)
            if m and m.group(1) in suffix2weight:
                out.append((suffix2weight[m.group(1)], m.group(1),
                            f'motion_pipeline/fonts/{family}/{p.name}', 0, 'OFL'))
    pf = project_font_dir(project_dir)
    if os.path.isdir(pf):
        for name in sorted(os.listdir(pf)):
            path = os.path.join(pf, name)
            if os.path.splitext(name)[1].lower() not in ('.ttf', '.otf', '.ttc'):
                continue
            for i in range(font_index._face_count(path)):
                try:
                    fam, style = ImageFont.truetype(path, 10, index=i).getname()
                except (OSError, ValueError):
                    continue
                if fam != family:
                    continue
                w = font_index.read_os2_weight(path, i) or 400
                out.append((w, style or font_index.CSS_WEIGHT_NAMES.get(w, str(w)),
                            f'fonts/{name}', i, CLIENT_LICENCE))
    # dedupe by (weight, file), keep first (bundled wins)
    seen = set()
    deduped = []
    for item in out:
        k = (item[0], item[2])
        if k not in seen:
            seen.add(k)
            deduped.append(item)
    return deduped


def normalise_fonts(cfg, project_dir=''):
    """Legacy {family, roles:{role:int}} -> new per-role shape; a new-shape cfg passes through.
    Faces are looked up by family+weight (bundled set or <project>/fonts/); unresolvable ->
    ValueError naming the role, family and weight, with the available faces listed."""
    if not isinstance(cfg, dict):
        raise ValueError('fonts config must be a JSON object')
    roles = cfg.get('roles')
    if isinstance(roles, dict) and roles and all(isinstance(v, dict) for v in roles.values()):
        return {'roles': roles}
    family = cfg.get('family')
    if not family:
        raise ValueError("font gate: project.json has no fonts.family")
    weights = roles if isinstance(roles, dict) else {}
    available = _family_faces(project_dir, family)
    out = {'roles': {}}
    for role in ROLES:
        w = weights.get(role, DEFAULT_WEIGHTS[role])
        if not isinstance(w, int):
            w = DEFAULT_WEIGHTS[role]
        hit = next((f for f in available if f[0] == w), None)
        if hit is None:
            avail = ', '.join(f'{label} ({w2})' for w2, label, *_ in sorted(available)) or 'none'
            raise ValueError(f"font gate: role {role!r} wants {family} {w} — available: {avail}")
        weight, label, file_ref, index, licence = hit
        out['roles'][role] = {'family': family, 'weight': weight, 'file': file_ref,
                              'index': index, 'licence': licence}
    return out


def resolve_role_map(project_dir, fonts_cfg):
    """{role: {family, weight, file(ABS path), index, licence}} — every role's face must exist
    on disk; fails naming the role otherwise."""
    cfg = normalise_fonts(fonts_cfg, project_dir)
    out = {}
    for role, r in cfg['roles'].items():
        file = r['file']
        if file.startswith('motion_pipeline/'):
            abs_path = str(importlib.resources.files('motion_pipeline') / file.split('motion_pipeline/', 1)[1])
        else:
            abs_path = os.path.join(project_dir, file)
        if not os.path.isfile(abs_path):
            raise ValueError(f"font gate: role {role!r} face file missing on disk: {file}")
        licence = 'OFL' if file.startswith('motion_pipeline/') else CLIENT_LICENCE
        out[role] = {'family': r['family'], 'weight': r['weight'], 'file': abs_path,
                     'index': r.get('index', 0), 'licence': r.get('licence', licence)}
    return out


def copy_client_faces(project_dir, roles):
    """P5: copy each non-bundled, not-yet-project-local face into <project>/fonts/ and rewrite
    its `file` to the project-relative ref. Bundled refs are returned unchanged."""
    import shutil
    out = {}
    dst_dir = project_font_dir(project_dir)
    for role, r in roles.items():
        file = r['file']
        if file.startswith('motion_pipeline/') or file.startswith('fonts/'):
            out[role] = dict(r)
            continue
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(file))
        if os.path.abspath(file) != os.path.abspath(dst):
            shutil.copy(file, dst)
        r = dict(r)
        r['file'] = f'fonts/{os.path.basename(file)}'
        r['licence'] = CLIENT_LICENCE
        out[role] = r
    return out


def font_gate(project_dir, project_json=None):
    """Validate a project's font config (legacy or new shape); returns the resolved role map
    with ABS face paths. Fails loudly per role."""
    cfg = (project_json or {}).get('fonts', {})
    if not cfg:
        raise ValueError("font gate: project.json has no fonts config")
    return resolve_role_map(project_dir, cfg)


def default_role_map(family, project_dir=''):
    """New-shape default role map for a family (all roles on the family, default weights)."""
    return normalise_fonts({'family': family}, project_dir)


def audit_bundled_licences():
    """Every bundled family dir must contain an OFL file. Returns list of violations."""
    bad = []
    root = importlib.resources.files('motion_pipeline') / 'fonts'
    for fam in bundled_families():
        d = root / fam
        if not any(p.name.upper().startswith('OFL') for p in d.iterdir()):
            bad.append(fam)
    return bad
