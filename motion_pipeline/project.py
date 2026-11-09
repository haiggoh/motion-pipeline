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


def default_project(name, aspect='16:9', fps=60, uhd=False):
    base = ASPECTS.get(aspect, ASPECTS['16:9'])
    w, h = UHD if (uhd and aspect == '16:9') else base
    return {'name': name, 'aspect': aspect, 'resolution': [w, h], 'fps': fps,
            'variants': ['default'], 'zones': [], 'fonts': {}, 'transcript': 'transcript.txt',
            'vo': None}


def validate(p):
    if not isinstance(p, dict):
        raise ValueError('project.json must be a JSON object')
    for k in REQUIRED_KEYS:
        if k not in p:
            raise ValueError(f'project.json missing key {k!r}')
    if p['aspect'] not in ASPECTS:
        raise ValueError(f"invalid aspect {p['aspect']!r} (want one of {sorted(ASPECTS)})")
    w, h = p['resolution']
    if [w, h] != list(ASPECTS[p['aspect']]) and [w, h] != list(UHD):
        raise ValueError(f"invalid resolution {p['resolution']} for aspect {p['aspect']} "
                         f"(want {list(ASPECTS[p['aspect']])}, or {list(UHD)} UHD for 16:9)")
    if p['fps'] not in FPS_CHOICES:
        raise ValueError(f"invalid fps {p['fps']!r} (want one of {list(FPS_CHOICES)})")
    if not isinstance(p['variants'], list) or not p['variants']:
        raise ValueError("invalid variants: want a non-empty list of scheme names")
    for z in p.get('zones', []):
        for k in ('section', 'rect'):
            if k not in z:
                raise ValueError(f"zone missing key {k!r}: {z}")
        if len(z['rect']) != 4:
            raise ValueError(f"zone rect must be [x,y,w,h]: {z['rect']}")
    return p


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
