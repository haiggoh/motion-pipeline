#!/usr/bin/env python3
"""render_info.py — the render_info.json beside each revision's masters (renders/<rev>/<colour>/).

usage:
  render_info.py check  --dir DIR --rev ID --arm ARM --hf VERSION --intermediate TAG
        exit 4 if DIR/render_info.json exists and its rev, hf_arm, hf_version or intermediate differ
        (a resumed render would splice two revisions/renderers/intermediate formats: chunks are
        skipped by name, so 8-bit-pipeline chunks would silently join a 10-bit run)
  render_info.py start  --dir DIR --rev ID --colour C --parts "A B" --arm ARM --hf VERSION
                        --intermediate TAG --content ABS_PATH [--node VERSION]
        write/refresh the file at the start of a render; keeps 'started' while that run is unfinished
        (verify still empty), keeps an earlier 'finished'
  render_info.py finish --dir DIR --verify VERIFIED|FAILED [--verify-only]
        stamp 'finished' + 'verify'; with --verify-only only 'verify' + 'verified_at' (the render time stays)
        (no-op with a note if the file does not exist)
exit: 0 ok, 2 bad arguments, 4 mismatch
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

NAME = 'render_info.json'


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def git(*args, cwd):
    r = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def read(d):
    p = os.path.join(d, NAME)
    try:
        with open(p) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def write(d, info):
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, NAME + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(info, f, indent=2)
        f.write('\n')
    os.replace(tmp, os.path.join(d, NAME))


def main(argv=None):
    doc = __doc__ or ''
    ap = argparse.ArgumentParser(prog='render_info.py', description=doc.split('\n')[0],
                                 epilog=doc.split('\n', 2)[2], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    s = sub.add_parser('start')
    f = sub.add_parser('finish')
    for p in (c, s, f):
        p.add_argument('--dir', required=True)
    for p in (c, s):
        p.add_argument('--rev', required=True)
        p.add_argument('--arm', required=True)
        p.add_argument('--hf', required=True)
        p.add_argument('--intermediate', required=True,
                       help='intermediate format tag, e.g. ffv1-bgr0 (10-bit pipeline); '
                            'an existing render_info.json without it or with another value refuses (exit 4)')
    s.add_argument('--colour', required=True)
    s.add_argument('--parts', required=True)
    s.add_argument('--content', required=True)
    s.add_argument('--node', default='')
    f.add_argument('--verify', required=True, choices=('VERIFIED', 'FAILED'))
    f.add_argument('--verify-only', action='store_true')
    a = ap.parse_args(argv)

    old = read(a.dir)
    if a.cmd == 'check':
        if old:
            bad = [(k, old.get(k), v) for k, v in (('rev', a.rev), ('hf_arm', a.arm), ('hf_version', a.hf),
                                                   ('intermediate', a.intermediate))
                   if old.get(k) != v]
            if bad:
                diff = '; '.join(f'{k}: existing {o!r} vs now {n!r}' for k, o, n in bad)
                print(f'render_info: {a.dir} holds a render made differently ({diff}). Resuming would mix '
                      f'them. Move those masters away, then re-run with --fresh.', file=sys.stderr)
                return 4
        return 0
    if a.cmd == 'start':
        top = git('rev-parse', '--show-toplevel', cwd=a.content)
        rel = os.path.relpath(a.content, top) if top else None
        info = dict(old or {})
        info.update(rev=a.rev, colour=a.colour, parts=a.parts.split(), hf_arm=a.arm, hf_version=a.hf,
                    intermediate=a.intermediate,
                    node=a.node, pipeline_commit=git('rev-parse', 'HEAD', cwd=a.content),
                    content_tree=git('rev-parse', f'HEAD:{rel}', cwd=a.content) if rel else None,
                    dirty=bool(git('status', '--porcelain', '--', '.', cwd=a.content)),
                    started=(old['started'] if old and old.get('started') and old.get('verify') is None else now()),
                    verify=None)   # one run = one start: render_all calls start before every part
        write(a.dir, info)
        return 0
    if old is None:
        print(f'render_info: no {NAME} in {a.dir}; verify result not recorded')
        return 0
    if a.verify_only:
        old.update(verify=a.verify, verified_at=now())
    else:
        old.update(finished=now(), verify=a.verify)
    write(a.dir, old)
    return 0


if __name__ == '__main__':
    sys.exit(main())
