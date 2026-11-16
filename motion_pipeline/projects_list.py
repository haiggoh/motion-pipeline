"""projects_list.py — list the projects in the projects root for the step-0 picker (Task 3).

A folder whose project.json is invalid is listed WITH its error (dimmed in the UI, never
hidden). Sorted by mtime, newest first.
"""
import os

from . import project as project_mod


def list_projects(root: str) -> list[dict]:
    """[{"name", "dir", "aspect", "fps", "mtime", "error": str|None}] sorted by mtime desc."""
    out = []
    if not root or not os.path.isdir(root):
        return out
    for name in os.listdir(root):
        d = os.path.join(root, name)
        if not os.path.isdir(d):
            continue
        pj = os.path.join(d, 'project.json')
        mtime = os.path.getmtime(pj) if os.path.isfile(pj) else os.path.getmtime(d)
        entry = {'name': name, 'dir': d, 'aspect': None, 'fps': None, 'mtime': mtime, 'error': None}
        try:
            p = project_mod.load(d)
            entry['aspect'] = p['aspect']
            entry['fps'] = p['fps']
        except Exception as e:
            entry['error'] = str(e)
        out.append(entry)
    out.sort(key=lambda e: e['mtime'], reverse=True)
    return out
