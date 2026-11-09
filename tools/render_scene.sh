#!/usr/bin/env bash
# render_scene.sh — generic 10-bit render backend (Task 9): one config-driven backend for
# every project. Renders the generated scene pages (src/scene_*.html) of a project+variant.
#
#   usage: tools/render_scene.sh --project DIR --variant NAME --mode test|full [--frames S-E] [--dry-run] [--fresh]
#
#   --project DIR    project folder (holds project.json, src/, renders/)
#   --variant NAME   scheme variant name (must be in project.json variants[])
#   --mode test      short render of the first scene (background+sample text path == full path)
#   --mode full      all scenes, one master per scene
#   --frames S-E     limit frames (scene-local, 0-based; test mode default 0-59)
#   --dry-run        print the plan, render nothing
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

PROJECT=""; VARIANT=""; MODE=""; FRAMES=""; DRY=0; FRESH=0; BANDED=0
while [ $# -gt 0 ]; do case "$1" in
  --project) PROJECT="${2:?}"; shift 2;; --project=*) PROJECT="${1#*=}"; shift;;
  --variant) VARIANT="${2:?}"; shift 2;; --variant=*) VARIANT="${1#*=}"; shift;;
  --mode) MODE="${2:?}"; shift 2;; --mode=*) MODE="${1#*=}"; shift;;
  --frames) FRAMES="${2:?}"; shift 2;; --frames=*) FRAMES="${1#*=}"; shift;;
  --dry-run) DRY=1; shift;; --fresh) FRESH=1; shift;;
  --banded) BANDED=1; shift;;  # known-bad mode for the chroma gate's discriminant (tests only)
  -h|--help) sed -n '2,20p' "$0"; exit 0;;
  *) echo "usage: $0 --project DIR --variant NAME --mode test|full [--frames S-E] [--dry-run] [--fresh] [--banded]  (unknown: $1)" >&2; exit 2;;
esac; done
[ -n "$PROJECT" ] && [ -n "$VARIANT" ] && [ -n "$MODE" ] || { echo "usage: $0 --project DIR --variant NAME --mode test|full [--frames S-E] [--dry-run] [--fresh]  (missing --project/--variant/--mode)" >&2; exit 2; }
case "$MODE" in test|full) ;; *) echo "bad --mode $MODE (want test|full)" >&2; exit 2;; esac
[ -f "$PROJECT/project.json" ] || { echo "no project.json in $PROJECT" >&2; exit 3; }
[ -d "$PROJECT/src" ] || { echo "no src/ in $PROJECT — run the generator first (motion_pipeline generate)" >&2; exit 3; }
python3 - "$PROJECT/project.json" "$VARIANT" <<'PY' || exit 3
import json, sys
p = json.load(open(sys.argv[1]))
if sys.argv[2] not in p.get('variants', []):
    print(f"variant {sys.argv[2]!r} not in project variants {p.get('variants')}", file=sys.stderr)
    sys.exit(1)
PY

OUT="$PROJECT/renders/$VARIANT"
mkdir -p "$OUT"
command -v hyperframes >/dev/null 2>&1 || { echo "hyperframes not on PATH (source tools/env.sh)" >&2; exit 3; }
HFV="$(hyperframes --version 2>/dev/null | tail -1)"

# resume refusal: an existing render_info.json without the intermediate marker (or with
# another value) must refuse — old 8-bit-pipeline intermediates would be spliced in as complete
if [ -f "$OUT/render_info.json" ]; then
  python3 "$TOOLS/render_info.py" check --dir "$OUT" --rev "$VARIANT" --arm pinned --hf "$HFV" --intermediate "$INTERMEDIATE" || exit 4
fi
if [ $FRESH = 1 ]; then
  if ls "$OUT"/*.mp4 >/dev/null 2>&1; then echo "--fresh: masters exist in $OUT — move them away first (never deleted here)" >&2; exit 4; fi
  [ $DRY = 1 ] || rm -rf "$OUT"/work_* "$OUT"/.work_* "$OUT"/.stage_* "$OUT"/chunks_* "$OUT"/.chunks_* "$OUT"/.raw_* "$OUT"/.pl_* "$OUT"/.concat_* "$OUT"/.render_*.log "$OUT/render_info.json"
fi

SCENES=( "$PROJECT"/src/scene_*.html )
[ ${#SCENES[@]} -gt 0 ] && [ -e "${SCENES[0]}" ] || { echo "no src/scene_*.html in $PROJECT" >&2; exit 3; }
[ "$MODE" = test ] && SCENES=( "${SCENES[0]}" )
[ -n "$FRAMES" ] || { [ "$MODE" = test ] && FRAMES="0-59" || FRAMES="all"; }

# disk guard (Review Focus 3): lossless intermediates ~1.4 MB/frame at 1080p
need_mb=$(( $(python3 -c "import json;p=json.load(open('$PROJECT/project.json'));w,h=p['resolution'];print(max(1,(w*h*3)//1024//1024))") * 2 ))
free_kb=$(df -k "$OUT" | tail -1 | awk '{print $4}')
need_kb=$(( need_mb * 1024 * 2 ))  # png + mkv transient
if [ "$free_kb" -lt "$need_kb" ]; then
  echo "disk guard: free $(( free_kb / 1024 )) MB < needed $(( need_kb / 1024 )) MB for the intermediates — free space and retry" >&2
  exit 3
fi

for scene in "${SCENES[@]}"; do
  name="$(basename "$scene" .html)"
  work="$OUT/work_$name"; rm -rf "$work"; mkdir -p "$work/frames"
  echo "[render_scene] $name mode=$MODE frames=$FRAMES"
  if [ $DRY = 1 ]; then
    echo "  would: hyperframes render $scene --format png-sequence -> $work/frames -> FFV1 bgr0 $work/raw.mkv -> master $OUT/$name.mp4 (yuv422p10le bt709)"
    continue
  fi
  python3 "$TOOLS/render_info.py" start --dir "$OUT" --rev "$VARIANT" --colour blue --parts "$name" --arm pinned --hf "$HFV" --intermediate "$INTERMEDIATE" --content "$PROJECT" >/dev/null
  # stage the scene as a site directory (hyperframes renders a directory, not a file)
  site="$work/site"; mkdir -p "$site"
  cp "$scene" "$site/index.html"
  [ $BANDED = 1 ] && sed -i '' 's|<head>|<head><script>window.__BANDED=true</script>|' "$site/index.html"
  [ -f "$ROOT/vendor/gsap.min.js" ] && cp "$ROOT/vendor/gsap.min.js" "$site/gsap.min.js"
  cp "$PROJECT"/src/*.js "$site/" 2>/dev/null || true
  # hyperframes 0.8.31 renders at preset resolutions whose aspect must match the composition
  res="$(python3 - "$PROJECT/project.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
w, h = p['resolution']
preset = {('16:9', False): 'landscape', ('16:9', True): 'landscape-4k',
          ('9:16', False): 'portrait', ('9:16', True): 'portrait-4k',
          ('1:1', False): 'square', ('1:1', True): 'square-4k'}.get((p['aspect'], w > 1920))
if preset is None:
    print('square', file=sys.stderr)  # 4:5 has no preset in hyperframes 0.8.31 — nearest aspect
    preset = 'square'
print(preset)
PY
)"
  (cd "$site" && NODE_OPTIONS="--max-old-space-size=4096" hyperframes render . --fps "$(python3 -c "import json;print(json.load(open('$PROJECT/project.json'))['fps'])")" --resolution "$res" --quality high --format png-sequence --output "$work/frames" > "$work/render.log" 2>&1 < /dev/null) \
    || { echo "render FAILED $name (see $work/render.log)" >&2; exit 1; }
  [ -f "$work/frames/frame_000001.png" ] || { echo "$name: unexpected png naming (no frame_000001.png)" >&2; exit 1; }
  n=$(find "$work/frames" -name '*.png' | wc -l | tr -d ' ')
  ffmpeg -v error -y -f image2 -framerate "$(python3 -c "import json;print(json.load(open('$PROJECT/project.json'))['fps'])")" -start_number 1 -i "$work/frames/frame_%06d.png" -c:v ffv1 -level 3 -pix_fmt bgr0 -g 1 "$work/raw.mkv" || exit 1
  got=$(ffprobe -v error -count_frames -select_streams v -show_entries stream=nb_read_frames -of csv=p=0 "$work/raw.mkv")
  [ "$got" = "$n" ] || { echo "$name: packed $got != $n pngs" >&2; exit 1; }
  rm -rf "$work/frames"
  # master: the single RGB->YUV conversion is here and only here (honour --frames S-E)
  trimvf=""
  case "$FRAMES" in
    all) ;;
    *) s="${FRAMES%-*}"; e="${FRAMES#*-}"; trimvf="trim=start_frame=$s:end_frame=$((e + 1)),setpts=PTS-STARTPTS," ;;
  esac
  ffmpeg -v error -y -i "$work/raw.mkv" \
    -vf "${trimvf}scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv422p10le" \
    -an -c:v libx264 -preset veryfast -tune grain -profile:v high422 -pix_fmt yuv422p10le \
    -b:v 49M -maxrate 60M -bufsize 60M -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
    -metadata title="$name" "$OUT/$name.mp4" || exit 1
  rm -rf "$work"
  echo "[render_scene] $name ok: $got fr -> $OUT/$name.mp4"
done
[ $DRY = 1 ] && { echo "[render_scene] dry run complete"; exit 0; }
python3 "$TOOLS/render_info.py" finish --dir "$OUT" --verify VERIFIED >/dev/null
echo "[render_scene] DONE $OUT"
