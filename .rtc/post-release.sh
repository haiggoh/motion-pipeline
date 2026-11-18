#!/usr/bin/env bash
# post-release.sh — bump the homebrew-tap formula to the shipped version: url + sha256 of the
# deterministic git-archive tarball just released, then commit and push the tap (for the tap,
# MERGING IS SHIPPING — installers brew from its default branch).
#
# usage: .rtc/post-release.sh [--help]
#   (no args)   rewrite Formula/motion-pipeline.rb (url + sha256), commit, push the tap
#   --help      print this usage, exit 0
# env: MP_TAP_DIR  path of the tap checkout to push from (default: the tap Homebrew has
#                  registered, discovered via `brew --repo haiggoh/homebrew-tap`; set-but-
#                  invalid MP_TAP_DIR aborts naming it)
set -euo pipefail
case "${1:-}" in
  "") ;;
  -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "usage: .rtc/post-release.sh [--help] (no other arguments)" >&2; exit 2 ;;
esac
top="$(git rev-parse --show-toplevel)"
version="$(tr -d '[:space:]' < "$top/VERSION")"
formula_rel="Formula/motion-pipeline.rb"
tarball="$top/dist/mp-$version.tar.gz"
[ -f "$tarball" ] || { echo "post-release: missing $tarball (pre-package must run first)" >&2; exit 1; }
sha="$(shasum -a 256 "$tarball" | awk '{print $1}')"

tap=""
if [ -n "${MP_TAP_DIR:-}" ]; then
  tap="$MP_TAP_DIR"
  [ -d "$tap/.git" ] || { echo "post-release: MP_TAP_DIR=$tap is not a git repo" >&2; exit 1; }
elif command -v brew >/dev/null 2>&1; then
  tap="$(brew --repo haiggoh/homebrew-tap 2>/dev/null || true)"
  [ -n "$tap" ] && [ -d "$tap/.git" ] || tap=""
fi
[ -n "$tap" ] || { echo "post-release: no tap checkout found — set MP_TAP_DIR=<path>" >&2; exit 1; }
formula="$tap/$formula_rel"
[ -f "$formula" ] || { echo "post-release: $formula missing in the discovered tap" >&2; exit 1; }

python3 - "$formula" "$version" "$sha" <<'PY'
import re
import sys

path, version, sha = sys.argv[1:4]
text = open(path).read()
text2 = re.sub(r'releases/download/v[\d.]+/mp-[\d.]+\.tar\.gz',
               f'releases/download/v{version}/mp-{version}.tar.gz', text)
text2 = re.sub(r'sha256 "[0-9a-f]{64}"', f'sha256 "{sha}"', text2, count=1)
if text2 == text:
    sys.exit(f'post-release: {path} unchanged — url/sha patterns did not match')
open(path, 'w').write(text2)
print(f'post-release: formula -> v{version} sha {sha[:12]}...')
PY
git -C "$tap" add -- "$formula_rel"
git -C "$tap" commit -q -m "motion-pipeline ${version}"
git -C "$tap" push -q origin main
echo "post-release: tap pushed ($formula_rel -> v${version})"
