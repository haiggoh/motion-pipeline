#!/usr/bin/env python3
"""audit_assets.py — publication gate (Task 12): no client assets in the published repo.

usage:
  audit_assets.py [--root DIR]     scan `git ls-files` under DIR (default: repo root)
exit 0 = clean, 1 = matches listed on stdout (file: pattern), 2 = bad args, 3 = not a git repo.

Patterns (anti-goal list from the design): client brand names in tracked paths or text,
voiceover/SFX asset names, the client CD's measured gradient constants, logo files.
"""
import argparse
import os
import re
import subprocess
import sys

PATH_PATTERNS = [
    (re.compile(r'(?i)(logo|brand)[^/]*\.(png|svg|jpg|jpeg|mp3|wav|flac)$'), 'logo/brand asset file'),
    (re.compile(r'(?i)\.(mp3|flac|wav)$'), 'audio asset file (VO/SFX)'),
    (re.compile(r'(?i)(vo|sfx)[^/]*$'), 'VO/SFX-named path'),
]
TEXT_PATTERNS = [
    (re.compile(r'(?i)\b(p&g|procter|seven\.?one|prosieben)\b'), 'client brand name'),
    (re.compile(r'(?i)(bild\s*1|cd.?gradient|measured gradient)'), 'client CD gradient constants'),
    (re.compile(r'(?i)0\.4641|9\.8739|15\.6699'), 'client-measured gradient coefficients'),
]
SKIP_DIRS = ('.venv', 'node_modules', 'renders', 'scratch', '__pycache__', 'projects')


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.split('\n')[0],
                                 epilog=__doc__.split('\n', 2)[2],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args(argv)
    r = subprocess.run(['git', '-C', a.root, 'ls-files'], capture_output=True, text=True)
    if r.returncode != 0:
        print(f'audit_assets: not a git repo: {a.root}', file=sys.stderr)
        return 3
    bad = 0
    for path in r.stdout.splitlines():
        if any(path.startswith(s) or f'/{s}/' in path for s in SKIP_DIRS):
            continue
        if path.endswith(('audit_assets.py', 'test_portability.sh')):
            continue  # own pattern literals / planted-fixture text would self-match
        for pat, label in PATH_PATTERNS:
            if pat.search(path):
                print(f'{path}: {label}')
                bad += 1
                break
        full = os.path.join(a.root, path)
        if os.path.isfile(full) and os.path.getsize(full) < 2_000_000:
            try:
                text = open(full, errors='ignore').read()
            except OSError:
                continue
            for pat, label in TEXT_PATTERNS:
                m = pat.search(text)
                if m:
                    print(f'{path}: {label} (text {m.group(0)!r})')
                    bad += 1
                    break
    if bad:
        return 1
    print('assets OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
