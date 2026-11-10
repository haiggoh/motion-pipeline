"""projfix.py — build a small but complete, generatable project (sample transcript, estimated
timing, base scheme) in a given folder. Shared by the variant and project-layout tests."""
import json
import os
import shutil

from motion_pipeline import align, project, transcript
from motion_pipeline.scheme import save_scheme

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DARK = {'name': 'default', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}


def make_project(d, name='demo'):
    d = str(d)
    shutil.copytree(os.path.join(ROOT, 'samples', 'globe'), d, dirs_exist_ok=True)
    p = project.default_project(name)
    p['fonts'] = {'family': 'Montserrat'}
    project.save(d, p)
    save_scheme(os.path.join(d, 'scheme.json'), DARK)
    tr = transcript.load(os.path.join(d, 'transcript.txt'))
    with open(os.path.join(d, 'transcript_model.json'), 'w') as f:
        json.dump(tr, f)
    align.save_timing(os.path.join(d, 'timing.json'), align.estimate_timings(tr, wpm=140))
    return d
