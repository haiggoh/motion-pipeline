#!/usr/bin/env python3
"""check_zone.py — generic keep-out-zone gate: no generated text block may intersect an
active zone rect (Task 9). Recomputes the layout from the project (same code path as the
generator) and checks every scene.

usage:
  check_zone.py --project DIR [--variant NAME]
exit 0 = all clear, 1 = offenders listed on stdout, 2 = bad args, 3 = project error.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motion_pipeline import generate, project, text_styles
from motion_pipeline.util import load_json


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.split('\n')[0],
                                 epilog=__doc__.split('\n', 2)[2],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', required=True)
    ap.add_argument('--variant', default='default')
    a = ap.parse_args(argv)

    p = project.load(a.project)
    _style_name = p.get('text_style', text_styles.DEFAULT)
    if _style_name not in text_styles.STYLES:
        raise ValueError(f"invalid text_style {_style_name!r} — want one of "
                         f"{sorted(text_styles.STYLES)} (key 'text_style')")
    style = text_styles.STYLES[_style_name]  # zone gate sees the style's real geometry
    tr = load_json(os.path.join(a.project, 'transcript_model.json'))
    W, H = p['resolution']
    from motion_pipeline.generate import ASPECT_FONT_SCALE
    font_px = int(H / 12 * ASPECT_FONT_SCALE.get(p['aspect'], 1.0))
    line_h = int(font_px * 1.25)
    bad = 0
    for sec in tr['sections']:
        words = [w for w in tr['words'] if w['section'] == sec['name']]
        if not words:
            continue
        lines = style.layout(words, max(8, int(W * 0.84 / (font_px * 0.52))), font_px)
        zs = [z for z in project.active_zones(p) if z['section'] == sec['name']]
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
