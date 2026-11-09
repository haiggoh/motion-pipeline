#!/usr/bin/env python3
"""check_chroma_steps.py — 10-bit-pipeline gate: no chroma staircase on a background strip.

usage:
  check_chroma_steps.py --video M.mp4 --frame N --strip x0,x1,y0,y1 [--max-step 2.0]

Decodes frame N of VIDEO as yuv422p10le, reads the Cb plane (4:2:2: half width, full height),
averages it over the strip's rows y0..y1 (full-res coordinates; Cb columns are x/2) and prints:
  - max |neighbour step| between adjacent averaged Cb columns, in 10-bit codes
  - the % of averaged samples that are multiples of 4 (the 8-bit-derived staircase signature)
exit 0 when max step <= --max-step, 1 when it exceeds it, 2 on bad arguments, 3 on decode error.
Strips per part live in tools/mac/chroma_strips.json {part: [{frame, strip}]} (part-local frames,
background-only rectangles — each confirmed by viewing a still when it was picked).
"""
import argparse
import subprocess
import sys
from typing import NoReturn

import numpy as np


def die(msg, code) -> NoReturn:
    print(f"check_chroma_steps: {msg}", file=sys.stderr)
    sys.exit(code)


def ffprobe_dims(video):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", video],
        capture_output=True, text=True)
    if r.returncode != 0:
        die(f"ffprobe failed for {video}: {r.stderr.strip()}", 3)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(","))
    except ValueError:
        die(f"cannot parse dimensions from ffprobe: {r.stdout!r}", 3)
    if w <= 0 or h <= 0 or w % 2:
        die(f"bad dimensions {w}x{h}", 3)
    return w, h


def decode_cb(video, frame, w, h):
    vf = f"trim=start_frame={frame}:end_frame={frame + 1},setpts=PTS-STARTPTS"
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video, "-vf", vf, "-f", "rawvideo",
         "-pix_fmt", "yuv422p10le", "-"],
        capture_output=True)
    expect = (w * h + 2 * (w // 2) * h) * 2
    if r.returncode != 0 or len(r.stdout) != expect:
        die(f"decode failed for {video} frame {frame} (rc={r.returncode}, {len(r.stdout)} bytes, want {expect}): {r.stderr.decode(errors='replace').strip()}", 3)
    ysz, csz = w * h, (w // 2) * h
    cb = np.frombuffer(r.stdout, dtype="<u2", count=csz, offset=ysz * 2).reshape(h, w // 2)
    return cb.astype(np.float64)


def main():
    ap = argparse.ArgumentParser(add_help=True, description="Chroma-staircase gate on a Cb strip (see module docstring).")
    ap.add_argument("--video", required=True)
    ap.add_argument("--frame", type=int, required=True)
    ap.add_argument("--strip", required=True, help="x0,x1,y0,y1 in full-res coordinates")
    ap.add_argument("--max-step", type=float, default=2.0, help="fail when max |neighbour step| exceeds this (10-bit codes)")
    try:
        args = ap.parse_args()
    except SystemExit as e:
        sys.exit(2 if e.code not in (0,) else 0)
    try:
        x0, x1, y0, y1 = (int(v) for v in args.strip.split(","))
    except ValueError:
        die(f"bad --strip {args.strip!r} (want x0,x1,y0,y1)", 2)
    if not (0 <= x0 < x1) or not (0 <= y0 < y1):
        die(f"bad --strip {args.strip!r} (need 0 <= x0 < x1 and 0 <= y0 < y1)", 2)

    w, h = ffprobe_dims(args.video)
    if x1 > w or y1 > h:
        die(f"strip {args.strip} outside frame {w}x{h}", 2)
    cb = decode_cb(args.video, args.frame, w, h)
    cx0, cx1, cy0, cy1 = x0 // 2, x1 // 2, y0, y1
    if cx1 - cx0 < 2:
        die(f"strip {args.strip} narrower than 2 Cb columns", 2)
    prof = cb[cy0:cy1, cx0:cx1].mean(axis=0)
    steps = np.abs(np.diff(prof))
    max_step = float(steps.max())
    mod4 = float(100.0 * np.mean(np.round(prof) % 4 == 0))
    verdict = "PASS" if max_step <= args.max_step else "FAIL"
    print(f"strip x{x0}-{x1} y{y0}-{y1} at frame {args.frame}: {cx1 - cx0} Cb cols x {cy1 - cy0} rows")
    print(f"max |neighbour step|: {max_step:.2f} (10-bit codes, threshold {args.max_step})   samples%4==0: {mod4:.1f}%")
    print(f"{verdict}: {'no staircase' if max_step <= args.max_step else f'staircase {max_step:.2f} > {args.max_step}'}")
    sys.exit(0 if max_step <= args.max_step else 1)


if __name__ == "__main__":
    main()
