#!/usr/bin/env python3
"""check_zone.py — generic keep-out-zone gate: no generated text block may intersect an
active zone rect (Task 9). Recomputes the layout from the project (same code path as the
generator) and checks every scene.

usage:
  check_zone.py --project DIR [--variant NAME]
exit 0 = all clear, 1 = offenders listed on stdout, 2 = bad args, 3 = project error.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motion_pipeline import generate, project  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.split('\n')[0],
                                 epilog=__doc__.split('\n', 2)[2],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', required=True)
    ap.add_argument('--variant', default='default')
    a = ap.parse_args(argv)

    p = project.load(a.project)
    tr = json.load(open(os.path.join(a.project, 'transcript_model.json')))
    W, H = p['resolution']
    from motion_pipeline.generate import ASPECT_FONT_SCALE
    font_px = int(H / 12 * ASPECT_FONT_SCALE.get(p['aspect'], 1.0))
    line_h = int(font_px * 1.25)
    bad = 0
    for sec in tr['sections']:
        words = [w for w in tr['words'] if w['section'] == sec['name']]
        if not words:
            continue
        lines = generate.layout_lines(words, max(8, int(W * 0.84 / (font_px * 0.52))), font_px)
        zs = [z for z in p.get('zones', []) if z['section'] == sec['name']]
        x, y = generate.place_text_block(lines, W, H, font_px, line_h, zs)
        max_w = max(len(''.join(pc for _, pc, _ in ln)) for ln in lines)
        block = (x, y, int(max_w * font_px * 0.52), len(lines) * line_h)
        for z in zs:
            if generate._rects_intersect(block, z['rect']):
                print(f'OFFENDER scene={sec["name"]} block={block} zone={z}')
                bad += 1
    if bad:
        return 1
    print('zones OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
