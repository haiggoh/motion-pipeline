#!/usr/bin/env bash
# render_scene.sh — generic 10-bit render backend (Task 9): one config-driven backend for
# every project. Renders the generated scene pages (src/scene_*.html) of a project+variant.
#
#   usage: tools/render_scene.sh --project DIR --variant NAME --mode test|full [--frames S-E] [--out DIR] [--dry-run] [--stage-only] [--fresh]
#   --out DIR: custom render output directory (default <project>/renders/<variant>/)
#
#   --project DIR    project folder (holds project.json, src/, renders/)
#   --variant NAME   scheme variant name (must be in project.json variants[])
#   --mode test      short render of the first scene (background+sample text path == full path)
#   --mode full      all scenes, one master per scene
#   --frames S-E     limit frames (scene-local, 0-based; test mode default 0-59)
#   --dry-run        print the plan, render nothing
#   --stage-only     stage each scene's site dir (page, gsap, src/*.js, src/ai_graphics/), print 'site: DIR', render nothing
#   --fresh          clear intermediates + render_info.json first (refuses while masters exist)
#
# Pipeline (10-bit, measured on the source explainer project 2026-11-08): hyperframes --format png-sequence
# (lossless RGB capture, 1-based frame_%06d.png — naming pinned by a file-exists check) ->
# FFV1 -pix_fmt bgr0 .mkv (lossless packed RGB) -> master encode libx264 High 4:2:2
# yuv422p10le with scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv422p10le
# as the ONLY RGB->YUV conversion. render_info.json records intermediate=ffv1-bgr0; a resume
# over an info without it or with another value refuses (exit 4, names --fresh).
#
# Exit: 0 ok, 2 bad args, 3 setup, 4 resume mismatch. Every flag: --help prints usage exit 0,
# unknown flag -> usage on stderr exit 2.
set -euo pipefail

TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$TOOLS")"
INTERMEDIATE="ffv1-bgr0"
# helper scripts run under the caller's python (has numpy/PIL), not the system one
PY="${MP_PYTHON:-python3}"

PROJECT=""; VARIANT=""; MODE=""; FRAMES=""; DRY=0; FRESH=0; BANDED=0; OUT=""; STAGE=0
while [ $# -gt 0 ]; do case "$1" in
  --project) PROJECT="${2:?}"; shift 2;; --project=*) PROJECT="${1#*=}"; shift;;
  --variant) VARIANT="${2:?}"; shift 2;; --variant=*) VARIANT="${1#*=}"; shift;;
  --mode) MODE="${2:?}"; shift 2;; --mode=*) MODE="${1#*=}"; shift;;
  --frames) FRAMES="${2:?}"; shift 2;; --frames=*) FRAMES="${1#*=}"; shift;;
  --out) OUT="${2:?}"; shift 2;; --out=*) OUT="${1#*=}"; shift;;
  --dry-run) DRY=1; shift;; --fresh) FRESH=1; shift;;
  --banded) BANDED=1; shift;;  # known-bad mode for the chroma gate's discriminant (tests only)
  --stage-only) STAGE=1; shift;;  # stage each scene's site dir, print 'site: DIR', render nothing
  -h|--help) sed -n '2,24p' "$0"; exit 0;;
  *) echo "usage: $0 --project DIR --variant NAME --mode test|full [--frames S-E] [--out DIR] [--dry-run] [--stage-only] [--fresh] [--banded]  (unknown: $1)" >&2; exit 2;;
esac; done
[ -n "$PROJECT" ] && [ -n "$VARIANT" ] && [ -n "$MODE" ] || { echo "usage: $0 --project DIR --variant NAME --mode test|full [--frames S-E] [--dry-run] [--fresh]  (missing --project/--variant/--mode)" >&2; exit 2; }
case "$MODE" in test|full) ;; *) echo "bad --mode $MODE (want test|full)" >&2; exit 2;; esac
[ -f "$PROJECT/project.json" ] || { echo "no project.json in $PROJECT" >&2; exit 3; }
[ -d "$PROJECT/src" ] || { echo "no src/ in $PROJECT — run the generator first (motion_pipeline generate)" >&2; exit 3; }
"$PY" - "$PROJECT/project.json" "$VARIANT" <<'PY' || exit 3
import json, sys
p = json.load(open(sys.argv[1]))
if sys.argv[2] not in p.get('variants', []):
    print(f"variant {sys.argv[2]!r} not in project variants {p.get('variants')}", file=sys.stderr)
    sys.exit(1)
PY

OUT="${OUT:-$PROJECT/renders/$VARIANT}"   # --out DIR: custom render output directory
[ $DRY = 1 ] || mkdir -p "$OUT"   # 0.8.4: --dry-run prints the plan only — no filesystem changes

# 0.8.4: --fresh runs FIRST (before the toolchain probe and the resume check) — its cleanup
# removes a stale render_info.json, so the resume refusal can no longer block the fresh run
# that would fix it. Masters are .mov since Task 15, so the guard checks *.mov (old .mp4
# masters are still refused further below).
if [ $FRESH = 1 ]; then
  if ls "$OUT"/*.mov >/dev/null 2>&1; then echo "--fresh: masters exist in $OUT — move them away first (never deleted here)" >&2; exit 4; fi
  [ $DRY = 1 ] || rm -rf "$OUT"/work_* "$OUT"/.work_* "$OUT"/.stage_* "$OUT"/chunks_* "$OUT"/.chunks_* "$OUT"/.raw_* "$OUT"/.pl_* "$OUT"/.concat_* "$OUT"/.render_*.log "$OUT/render_info.json"
fi

# resume refusal: an existing render_info.json without the intermediate marker (or with
# another value) must refuse — old 8-bit-pipeline intermediates would be spliced in as complete
if [ -f "$OUT/render_info.json" ] && [ $DRY = 0 ] && [ $STAGE = 0 ]; then
  "$PY" "$TOOLS/render_info.py" check --dir "$OUT" --rev "$VARIANT" --arm pinned --hf "${HFV:-0.8.31}" --intermediate "$INTERMEDIATE" || exit 4
fi

if [ $DRY = 0 ] && [ $STAGE = 0 ]; then
  command -v hyperframes >/dev/null 2>&1 || { echo "hyperframes not on PATH (source tools/env.sh)" >&2; exit 3; }
  HFV="$(hyperframes --version 2>/dev/null | tail -1)"
fi

# Task 12: scene order comes from src/scenes.json (written by the generator), not the glob
[ -f "$PROJECT/src/scenes.json" ] || { echo "no src/scenes.json in $PROJECT — run the generator first" >&2; exit 3; }
# newline-joined + line-wise read: project paths may contain SPACES (dogfood 2026-11-19,
# 'sevenone adf test' — word-splitting the space-joined output broke the cp)
SCENES=()
while IFS= read -r f; do SCENES+=("$f"); done < <("$PY" -c "import json; print('\n'.join('$PROJECT/src/' + s['file'] for s in json.load(open('$PROJECT/src/scenes.json'))))")
[ ${#SCENES[@]} -gt 0 ] || { echo "no scenes in src/scenes.json" >&2; exit 3; }
[ "$MODE" = test ] && SCENES=( "${SCENES[0]}" )
[ -n "$FRAMES" ] || { [ "$MODE" = test ] && FRAMES="0-59" || FRAMES="all"; }

# disk guard (finding 17, Task 13): need = SUM over the scenes of ceil(duration*fps) frames,
# ~1.4 MB/frame at 1080p (measured), x2 for the png + ffv1 transient; durations from scenes.json
need_mb=$("$PY" - "$PROJECT" <<'PY'
import json, math, sys
p = json.load(open(sys.argv[1] + '/project.json'))
w, h = p['resolution']
frames = sum(max(1, math.ceil((s['end'] - s['start']) * p['fps']))
             for s in json.load(open(sys.argv[1] + '/src/scenes.json')))
print(max(1, int(frames * w * h * 1.4 / (1920 * 1080) * 2)))
PY
)
if [ $DRY = 0 ]; then   # 0.8.4: the disk guard sizes a real render — skip in dry-run ($OUT may not exist)
  free_kb=$(df -k "$OUT" | tail -1 | awk '{print $4}')
  need_kb=$(( need_mb * 1024 ))
  if [ "$free_kb" -lt "$need_kb" ]; then
    echo "disk guard: free $(( free_kb / 1024 )) MB < needed $(( need_kb / 1024 )) MB for the intermediates — free space and retry" >&2
    exit 3
  fi
fi

# zone gate BEFORE any capture (Task 13): recomputes the layout; a failure stops before minutes
# are spent. exit 6.
if [ $DRY = 0 ] && [ $STAGE = 0 ]; then
  if ! "$PY" "$TOOLS/check_zone.py" --project "$PROJECT" --variant "$VARIANT"; then
    echo "zone gate: a text block intersects an active keep-out zone — see above (exit 6)" >&2
    exit 6
  fi
fi

for scene in "${SCENES[@]}"; do
  name="$(basename "$scene" .html)"
  work="$OUT/work_$name"
  [ $DRY = 1 ] || { rm -rf "$work"; mkdir -p "$work/frames"; }   # 0.8.4: dry-run touches nothing
  echo "[render_scene] $name mode=$MODE frames=$FRAMES"
  if [ $DRY = 1 ]; then
    echo "  would: hyperframes render $scene --format png-sequence -> $work/frames -> FFV1 bgr0 $work/raw.mkv -> master $OUT/$name.mov (yuv422p10le bt709)"
    continue
  fi
  [ $STAGE = 1 ] || "$PY" "$TOOLS/render_info.py" start --dir "$OUT" --rev "$VARIANT" --colour blue --parts "$name" --arm pinned --hf "$HFV" --intermediate "$INTERMEDIATE" --content "$PROJECT" >/dev/null
  # stage the scene as a site directory (hyperframes renders a directory, not a file)
  site="$work/site"; mkdir -p "$site"
  cp "$scene" "$site/index.html"
  [ $BANDED = 1 ] && sed -i '' 's|<head>|<head><script>window.__BANDED=true</script>|' "$site/index.html"
  [ -f "$ROOT/vendor/gsap.min.js" ] && cp "$ROOT/vendor/gsap.min.js" "$site/gsap.min.js"
  cp "$PROJECT"/src/*.js "$site/" 2>/dev/null || true
  # Task 1 (0.8.0): stage package graphics + vendor plugins AFTER project src — the package
  # copy wins, loudly, on a name collision (a project file named like a package file must
  # neither 404 nor silently win)
  for f in "$ROOT"/vendor/*.js "$ROOT"/motion_pipeline/graphics/*.js; do
    [ -f "$f" ] || continue
    b="$(basename "$f")"
    [ -f "$PROJECT/src/$b" ] && echo "staging: package $b overrides project src/$b" >&2
    cp "$f" "$site/$b"
  done
  [ -d "$PROJECT/src/fonts" ] && cp -R "$PROJECT/src/fonts" "$site/fonts"  # Task 11: embedded faces
  # AI-owned graphics (ai_layer.py) the generator linked as ai_graphics/<file>
  [ -d "$PROJECT/src/ai_graphics" ] && cp -R "$PROJECT/src/ai_graphics" "$site/ai_graphics"
  if [ $STAGE = 1 ]; then echo "  site: $site"; continue; fi
  # P4: never pass --resolution — compositions are authored at the project's real resolution
  # (hyperframes renders 1080x1350 natively when omitted, E5)
  (cd "$site" && NODE_OPTIONS="--max-old-space-size=4096" hyperframes render . --fps "$("$PY" -c "import json;print(json.load(open('$PROJECT/project.json'))['fps'])")" --quality high --format png-sequence --output "$work/frames" > "$work/render.log" 2>&1 < /dev/null) \
    || { echo "render FAILED $name (see $work/render.log)" >&2; exit 1; }
  [ -f "$work/frames/frame_000001.png" ] || { echo "$name: unexpected png naming (no frame_000001.png)" >&2; exit 1; }
  # Task 11 font gate: a role face that did not load is logged by the page as MP_FONT_MISSING
  if grep -q 'MP_FONT_MISSING' "$work/render.log" 2>/dev/null; then
    missing="$(grep -o 'MP_FONT_MISSING .*' "$work/render.log" | head -1)"
    echo "font gate: $missing — the embedded face did not load (see $work/render.log)" >&2
    exit 5
  fi
  n=$(find "$work/frames" -name '*.png' | wc -l | tr -d ' ')
  ffmpeg -v error -y -f image2 -framerate "$("$PY" -c "import json;print(json.load(open('$PROJECT/project.json'))['fps'])")" -start_number 1 -i "$work/frames/frame_%06d.png" -c:v ffv1 -level 3 -pix_fmt bgr0 -g 1 "$work/raw.mkv" || exit 1
  got=$(ffprobe -v error -count_frames -select_streams v -show_entries stream=nb_read_frames -of csv=p=0 "$work/raw.mkv")
  [ "$got" = "$n" ] || { echo "$name: packed $got != $n pngs" >&2; exit 1; }
  rm -rf "$work/frames"
  # master: the single RGB->YUV conversion is here and only here (honour --frames S-E)
  trimvf=""
  case "$FRAMES" in
    all) ;;
    *) s="${FRAMES%-*}"; e="${FRAMES#*-}"; trimvf="trim=start_frame=$s:end_frame=$((e + 1)),setpts=PTS-STARTPTS," ;;
  esac
  # Task 15: the video-only encode is TEMPORARY ($work) — it is muxed into the .mov and deleted
  ffmpeg -v error -y -i "$work/raw.mkv" \
    -vf "${trimvf}scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv422p10le" \
    -an -c:v libx264 -preset veryfast -tune grain -profile:v high422 -pix_fmt yuv422p10le \
    -b:v 49M -maxrate 60M -bufsize 60M -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
    -metadata title="$name" "$work/video.mp4" || exit 1
  # Task 15: mux VO+SFX into the scene master .mov (video stream copied bit-exact, E9)
  "$PY" - "$PROJECT" "$work/video.mp4" "$OUT/$name.mov" "$ROOT" <<'PY' || { echo "audio mux failed for $name" >&2; exit 1; }
import json, os, sys
proj_dir, video, out_mov, root = sys.argv[1:5]
sys.path.insert(0, root)
from motion_pipeline import audio_mux, project as pm
p = pm.load(proj_dir)
timing = json.load(open(os.path.join(proj_dir, 'timing.json')))
model = json.load(open(os.path.join(proj_dir, 'transcript_model.json')))
scenes = json.load(open(os.path.join(proj_dir, 'src', 'scenes.json')))
scene = next(s for s in scenes if s['file'] == os.path.basename(out_mov)[:-4] + '.html')
vo = p.get('vo')
if vo and not os.path.isabs(vo):
    vo = os.path.join(proj_dir, vo)
cues = audio_mux.sfx_cues(proj_dir, timing, model)
audio_mux.mux_scene(video, out_mov, scene['start'], scene['end'], vo, cues)
PY
  # chroma gate (Task 13) after each MASTER (.mov): no chroma staircase on the top strip; exit 6
  # on failure, master kept in $OUT, render_info.json NOT marked VERIFIED
  if [ "${MP_SKIP_CHROMA_GATE:-0}" = "1" ]; then
    echo "chroma gate skipped: MP_SKIP_CHROMA_GATE=1 (loud)"
  else
    read -r W H < <("$PY" -c "import json;p=json.load(open('$PROJECT/project.json'));print(*p['resolution'])")
    strip="$(( W / 20 )),$(( W * 19 / 20 )),$(( H / 50 )),$(( H * 3 / 50 ))"  # 0.05W..0.95W x 0.02H..0.06H
    overlap=$("$PY" - "$PROJECT" "$W" "$H" <<'PY'
import json, sys
root = sys.argv[1]
sys.path.insert(0, root)
from motion_pipeline import project as pm
p = json.load(open(root + '/project.json'))
w, h = p['resolution']
s = (int(w * 0.05), int(w * 0.95), int(h * 0.02), int(h * 0.06))
srect = (s[0], s[2], s[1] - s[0], s[3] - s[2])
def inter(a, b):
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
hits = [z['section'] for z in pm.active_zones(p) if inter(srect, z['rect'])]
print(' '.join(hits))
PY
)
    if [ -n "$overlap" ]; then
      echo "chroma gate skipped: strip overlaps zone/AI graphic ($overlap)"
    elif ! "$PY" "$TOOLS/check_chroma_steps.py" --video "$OUT/$name.mov" --frame 0 --strip "$strip" --max-step 2.0; then
      echo "chroma gate FAILED for $name (strip $strip) — master kept in $OUT, render_info not VERIFIED (exit 6)" >&2
      exit 6
    fi
  fi
  rm -rf "$work"  # no video-only copy is ever kept (user 2026-11-16)
  echo "[render_scene] $name ok: $got fr -> $OUT/$name.mov"
done
# old .mp4 masters are refused (masters are .mov now)
if [ $DRY = 0 ] && [ $STAGE = 0 ] && ls "$OUT"/*.mp4 >/dev/null 2>&1; then
  echo "old .mp4 masters present in $OUT — masters are .mov now; move them away and re-render (exit 3)" >&2
  exit 3
fi
# Task 15 outputs after all scenes: timeline.json, preview, optional joined master, info fields
[ $DRY = 1 ] && { echo "[render_scene] dry run complete"; exit 0; }
[ $STAGE = 1 ] && { echo "[render_scene] staged sites only"; exit 0; }
"$PY" - "$PROJECT" "$VARIANT" "$OUT" "$ROOT" <<'PY'
import json, os, sys
proj_dir, variant, out, root = sys.argv[1:5]
sys.path.insert(0, root)
from motion_pipeline import audio_mux, project as pm
p = pm.load(proj_dir)
fps = p['fps']
scenes = json.load(open(os.path.join(proj_dir, 'src', 'scenes.json')))
movs = [os.path.join(out, s['file'][:-5] + '.mov') for s in scenes]
audio_mux.write_timeline(os.path.join(out, 'timeline.json'), scenes, fps)
audio_mux.preview(movs, os.path.join(out, f'{variant}_preview.mp4'))
timing = json.load(open(os.path.join(proj_dir, 'timing.json')))
model = json.load(open(os.path.join(proj_dir, 'transcript_model.json')))
vo = p.get('vo')
if vo and not os.path.isabs(vo):
    vo = os.path.join(proj_dir, vo)
cues = audio_mux.sfx_cues(proj_dir, timing, model)
full = os.environ.get('FULL_MASTER') or ('1' if p.get('full_master') else '0')
if full == '1':
    ok, frames = audio_mux.join([dict(s, file=m) for s, m in zip(scenes, movs)],
                                os.path.join(out, f'{variant}_full.mov'), vo, cues)
    want = sum(round((s['end'] - s['start']) * fps) for s in scenes)
    if not ok or frames != want:
        print(f'[render_scene] joined master SKIPPED: concat frames {frames} != {want} (re-encode is forbidden, D2)')
    else:
        print(f'[render_scene] joined master: {frames} fr')
# record container/audio/scene spans in render_info.json for remux checks
ip = os.path.join(out, 'render_info.json')
if os.path.isfile(ip):
    info = json.load(open(ip))
    info['container'] = 'mov'
    info['audio'] = 'vo+sfx'
    info['scenes'] = [{'file': s['file'], 'start': s['start'], 'end': s['end']} for s in scenes]
    with open(ip, 'w') as f:
        json.dump(info, f, indent=2)
PY
[ $DRY = 1 ] && { echo "[render_scene] dry run complete"; exit 0; }
"$PY" "$TOOLS/render_info.py" finish --dir "$OUT" --verify VERIFIED >/dev/null
echo "[render_scene] DONE $OUT"
