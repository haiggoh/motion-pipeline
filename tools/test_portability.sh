#!/usr/bin/env bash
# test_portability.sh — gate suite for the generic backend (Task 9), ported from the PGCube
# 10-bit plan's gates. Run: bash tools/test_portability.sh   (exit 0 = PORTABLE)
set -uo pipefail
TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$TOOLS")"
FAIL=0
ok() { echo "  ok: $1"; }
bad() { echo "  FAIL: $1" >&2; FAIL=1; }

echo "== (l) backend: no 8-bit-YUV/lossy intermediate step; ffv1 bgr0 pins present"
if grep -nE 'yuv420p|(^|[^-])-crf[ =]|--crf|-qp 0|bt601' "$TOOLS/render_scene.sh" | grep -v '^[0-9]*:#' | grep -v '^[[:space:]]*#'; then
  bad "forbidden intermediate pattern in render_scene.sh"
else ok "no 8-bit-YUV/lossy intermediate patterns"; fi
if grep -q -- '-pix_fmt bgr0' "$TOOLS/render_scene.sh" && grep -q -- '-c:v ffv1' "$TOOLS/render_scene.sh"; then
  ok "ffv1 bgr0 pins present"
else bad "ffv1 bgr0 pins missing"; fi
if grep -q 'out_color_matrix=bt709' "$TOOLS/render_scene.sh"; then
  ok "single bt709 master conversion present"
else bad "bt709 master conversion missing"; fi

echo "== (m) every tool: --help exit 0, unknown flag exit 2"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
for t in "$TOOLS/render_scene.sh" "$TOOLS/check_chroma_steps.py" "$TOOLS/check_zone.py" "$TOOLS/audit_assets.py" "$TOOLS/render_info.py"; do
  if [[ "$t" == *.sh ]]; then
    bash "$t" --help >/dev/null 2>&1 || { bad "$t --help not 0"; continue; }
    bash "$t" --bogus >/dev/null 2>&1; [ $? = 2 ] || { bad "$t --bogus not 2"; continue; }
  else
    "$PY" "$t" --help >/dev/null 2>&1 || { bad "$t --help not 0"; continue; }
    "$PY" "$t" --bogus >/dev/null 2>&1; [ $? = 2 ] || { bad "$t --bogus not 2"; continue; }
  fi
  ok "$(basename "$t") help/unknown-flag contract"
done

echo "== (n) render_info resume refusal: info without 'intermediate' -> exit 4 naming --fresh"
tmp=$(mktemp -d)
python3 - "$tmp" <<'PY' || true
import json, sys
json.dump({'rev': 'v', 'hf_arm': 'pinned', 'hf_version': '0.8.31'}, open(sys.argv[1] + '/render_info.json', 'w'))
PY
r=$(python3 "$TOOLS/render_info.py" check --dir "$tmp" --rev v --arm pinned --hf 0.8.31 --intermediate ffv1-bgr0 2>&1); rc=$?
[ $rc = 4 ] && echo "$r" | grep -q -- '--fresh' && echo "$r" | grep -q intermediate && ok "old-info refusal (exit 4, --fresh, intermediate named)" || bad "resume refusal (rc=$rc): $r"
rm -rf "$tmp"

echo "== (o) render_scene.sh refuses unknown variant / missing src (exit 3), bad mode (exit 2)"
tmp=$(mktemp -d); mkdir -p "$tmp/p"
python3 - "$tmp/p" <<'PY' || true
import json, sys
json.dump({'name': 'p', 'aspect': '16:9', 'resolution': [1920, 1080], 'fps': 60,
           'variants': ['default'], 'zones': [], 'fonts': {}, 'transcript': 'transcript.txt', 'vo': None},
          open(sys.argv[1] + '/project.json', 'w'))
PY
bash "$TOOLS/render_scene.sh" --project "$tmp/p" --variant nope --mode full >/dev/null 2>&1; [ $? = 3 ] && ok "unknown variant -> exit 3" || bad "unknown variant exit"
bash "$TOOLS/render_scene.sh" --project "$tmp/p" --variant default --mode nope >/dev/null 2>&1; [ $? = 2 ] && ok "bad mode -> exit 2" || bad "bad mode exit"
bash "$TOOLS/render_scene.sh" --project "$tmp/p" --variant default --mode full >/dev/null 2>&1; [ $? = 3 ] && ok "missing src/ -> exit 3" || bad "missing src exit"
rm -rf "$tmp"

echo "== (p) audit_assets: clean repo passes; planted client-asset fixture fails"
r=$(python3 "$TOOLS/audit_assets.py" --root "$ROOT" 2>&1); rc=$?
# the repo itself must be clean (vendor/gsap.min.js contains no client patterns)
[ $rc = 0 ] && ok "repo asset audit clean" || { bad "asset audit: $r"; }
tmp=$(mktemp -d); git -C "$tmp" init -q; echo 'P&G logo' > "$tmp/x.txt"; git -C "$tmp" add x.txt
r=$(python3 "$TOOLS/audit_assets.py" --root "$tmp" 2>&1); rc=$?
[ $rc = 1 ] && echo "$r" | grep -q 'client brand' && ok "planted client-asset fixture -> exit 1" || bad "planted fixture (rc=$rc): $r"
rm -rf "$tmp"

echo "== (q) fast pytest suite green, 0 unexpected skips (e2e render test excluded — slow)"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
pr=$("$PY" -m pytest "$ROOT/tests" -q -rs --deselect tests/test_sample_e2e.py::test_real_test_render_and_chroma_gate 2>&1)
echo "$pr" | tail -1 | sed 's/^/  /'
echo "$pr" | grep -qE '[0-9]+ passed' || bad "pytest fast suite not green"
if echo "$pr" | grep -qE 'SKIPPED|XFAIL'; then bad "unexpected skip/xfail in fast suite"; else ok "0 unexpected skips"; fi

echo "== (r) README structure (approved direction): CI inputs + VO timing lead, 10-bit section, output options, free-agents link"
rmiss=0
for pat in 'CI inputs' 'Voiceover timing workflow' '10-bit' 'Output options' 'works out of the box' 'free-agents' 'github.com/haiggoh/free-agents'; do
  grep -q -- "$pat" "$ROOT/README.md" || { bad "README missing: $pat"; rmiss=1; }
done
[ $rmiss = 0 ] && ok "README sections present"

[ $FAIL = 0 ] && echo "== PORTABLE" || echo "== NOT PORTABLE" >&2
exit $FAIL
