"""project.py — project folder model + validation (Task 5).

A project lives in projects/<name>/:
  project.json   {name, aspect, resolution:[w,h], fps, variants:[schemeName,...],
                  fonts:{family,roles}, transcript, vo, zones:[...]}
  scheme.json per variant (Task 2), transcript.txt (Task 6), audio/vo.* (Task 7),
  timing.json (G5 shape), fonts/ (gitignored client fonts), src/ (generated pages),
  ai_graphics/ (never written by the generator), renders/ (output)

Set-but-invalid settings fail loudly naming the key (user's global rule).
"""
import json
import os

ASPECTS = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080), '4:5': (1080, 1350)}
UHD = (3840, 2160)
FPS_CHOICES = (25, 30, 50, 60)
REQUIRED_KEYS = ('name', 'aspect', 'resolution', 'fps', 'variants')
# every key the menu owns in project.json. Anything else is refused by validate(): AI
# additions belong in ai_graphics/ (ai_layer.py), never in the menu's files (0.5.0 Task 4d).
OWNED_KEYS = REQUIRED_KEYS + ('zones', 'fonts', 'transcript', 'vo', 'graphics', 'wpm', 'language', 'aligner')
AGENTS_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'project_AGENTS.md')


def resolution_for(aspect, uhd=False):
    """Resolution [w, h] for an aspect; UHD only applies to 16:9 (the caller refuses the
    combination). ONE aspect -> resolution wiring: default_project() and the project
    screen's Save format both read this."""
    base = ASPECTS.get(aspect)
    if base is None:
        raise ValueError(f'invalid aspect {aspect!r} (want one of {sorted(ASPECTS)})')
    return list(UHD) if (uhd and aspect == '16:9') else list(base)


def default_project(name, aspect='16:9', fps=60, uhd=False):
    return {'name': name, 'aspect': aspect, 'resolution': resolution_for(aspect, uhd),
            'fps': fps, 'variants': ['default'], 'zones': [], 'fonts': {},
            'transcript': 'transcript.txt', 'vo': None, 'wpm': 140, 'language': 'de', 'aligner': 'auto'}


def validate(p):
    if not isinstance(p, dict):
        raise ValueError('project.json must be a JSON object')
    for k in REQUIRED_KEYS:
        if k not in p:
            raise ValueError(f'project.json missing key {k!r}')
    foreign = sorted(set(p) - set(OWNED_KEYS))
    if foreign:
        raise ValueError(f'project.json has keys the menu does not own: {foreign} — additions '
                         'belong in ai_graphics/ (see AGENTS.md); move them there, the menu '
                         'will not rewrite this file while they are present')
    if p['aspect'] not in ASPECTS:
        raise ValueError(f"invalid aspect {p['aspect']!r} (want one of {sorted(ASPECTS)})")
    w, h = p['resolution']
    ar = {'16:9': (16, 9), '9:16': (9, 16), '1:1': (1, 1), '4:5': (4, 5)}[p['aspect']]
    if w * ar[1] != h * ar[0]:
        raise ValueError(f"invalid resolution {p['resolution']} for aspect {p['aspect']} "
                         f"(want {ar[0]}:{ar[1]}, e.g. {list(ASPECTS[p['aspect']])} or {list(UHD)} UHD)")
    if p['fps'] not in FPS_CHOICES:
        raise ValueError(f"invalid fps {p['fps']!r} (want one of {list(FPS_CHOICES)})")
    if 'wpm' in p:
        wpm = p['wpm']
        if not isinstance(wpm, int) or isinstance(wpm, bool) or not 60 <= wpm <= 300:
            raise ValueError(f"invalid wpm {wpm!r} — want an integer 60–300 (key 'wpm')")
    if 'language' in p and p['language'] not in ('de', 'en', 'auto'):
        raise ValueError(f"invalid language {p['language']!r} — want 'de', 'en' or 'auto' (key 'language')")
    if 'aligner' in p and p['aligner'] not in ('auto', 'classical', 'whisper'):
        raise ValueError(f"invalid aligner {p['aligner']!r} — want 'auto', 'classical' or 'whisper' (key 'aligner')")
    if not isinstance(p['variants'], list) or not p['variants']:
        raise ValueError("invalid variants: want a non-empty list of scheme names")
    for z in p.get('zones', []):
        for k in ('section', 'rect'):
            if k not in z:
                raise ValueError(f"zone missing key {k!r}: {z}")
        if len(z['rect']) != 4:
            raise ValueError(f"zone rect must be [x,y,w,h]: {z['rect']}")
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in z['rect']):
            raise ValueError(f"zone rect must be integers x,y,w,h: {z['rect']}")
        zx, zy, zw, zh = z['rect']
        if zx < 0 or zy < 0 or zw <= 0 or zh <= 0:
            raise ValueError(f"zone rect must have x,y >= 0 and w,h > 0: {z['rect']}")
        if 'aspect' in z and z['aspect'] not in ASPECTS:
            raise ValueError(f"invalid zone aspect {z['aspect']!r} (want one of {sorted(ASPECTS)})")
        if z.get('aspect', p['aspect']) == p['aspect']:  # only ACTIVE zones must fit this frame
            fw, fh = p['resolution']
            if zx + zw > fw or zy + zh > fh:
                raise ValueError(f"zone rect {z['rect']} is outside the {fw}×{fh} frame")
    return p


def active_zones(p):
    """Zones active for p's aspect (P1): a zone with no `aspect` (legacy project) means the
    project's aspect. Inactive-aspect zones stay on disk, just unused."""
    return [z for z in p.get('zones', []) if z.get('aspect', p['aspect']) == p['aspect']]


def project_dir(root, name):
    return os.path.join(root, 'projects', name)


def load(project_path):
    """project_path = projects/<name> dir or its project.json; returns validated dict."""
    pj = project_path if project_path.endswith('project.json') else os.path.join(project_path, 'project.json')
    if not os.path.isfile(pj):
        raise ValueError(f'no project.json at {pj}')
    with open(pj) as f:
        return validate(json.load(f))


def save(project_path, p):
    validate(p)
    pj = project_path if project_path.endswith('project.json') else os.path.join(project_path, 'project.json')
    os.makedirs(os.path.dirname(pj), exist_ok=True)
    tmp = pj + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(p, f, indent=2)
        f.write('\n')
    os.replace(tmp, pj)
    write_agents_md(os.path.dirname(pj))


def write_agents_md(project_path):
    """(Re)write the project's AGENTS.md — the three-zone contract for anyone (AI or human)
    adding graphics. Written on EVERY save, so it is current for every project."""
    with open(AGENTS_TEMPLATE) as f:
        text = f.read()
    with open(os.path.join(project_path, 'AGENTS.md'), 'w') as f:
        f.write(text)
