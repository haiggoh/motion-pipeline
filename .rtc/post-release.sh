#!/usr/bin/env bash
# post-release.sh — bump the homebrew-tap formula to the shipped version: url + sha256 of the
# deterministic git-archive tarball just released, then commit and push the tap (for the tap,
# MERGING IS SHIPPING — installers brew from its default branch).
#
# usage: .rtc/post-release.sh [--help]
#   (no args)   rewrite Formula/motion-pipeline.rb (url + sha256), commit, push the tap
#   --help      print this usage, exit 0
# env: MP_TAP_DIR  path of the tap checkout to push from (default: the tap Homebrew has
#                  registered, discovered via `brew --repo haiggoh/homebrew-tap`); the resolved
#                  tap must be haiggoh/homebrew-tap on branch main — any other repo or branch
#                  is a LOUD refusal, never a silent rewrite; set-but-invalid MP_TAP_DIR
#                  aborts naming it
set -euo pipefail
case "${1:-}" in
  "") ;;
  -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
# identity checks (QC 2026-11-18): the resolved checkout must be THE tap, on main — a fork,
# a vendored copy, or a feature branch would otherwise be rewritten and pushed as "shipped".
url="$(git -C "$tap" remote get-url origin 2>/dev/null || true)"
case "$url" in
  *github.com/haiggoh/homebrew-tap*) ;;
  *) echo "post-release: refusing — $tap origin is '${url:-<none>}', want haiggoh/homebrew-tap" >&2; exit 1 ;;
esac
branch="$(git -C "$tap" branch --show-current)"
[ "$branch" = "main" ] || { echo "post-release: refusing — tap is on branch '$branch', want main" >&2; exit 1; }
formula="$tap/$formula_rel"
[ -f "$formula" ] || { echo "post-release: $formula missing in the discovered tap" >&2; exit 1; }

python3 - "$formula" "$version" "$sha" <<'PY'
import re
import sys

path, version, sha = sys.argv[1:4]
lines = open(path).read().splitlines(keepends=True)
ui = next((i for i, ln in enumerate(lines)
           if 'releases/download/' in ln and 'mp-' in ln), None)
if ui is None:
    sys.exit(f'post-release: no release url line in {path}')
lines[ui] = re.sub(r'v[\d.]+/mp-[\d.]+\.tar\.gz', f'v{version}/mp-{version}.tar.gz', lines[ui])
# the sha256 is the line FOLLOWING the url (bound to it — a resource block's sha elsewhere in
# the file must never be rewritten, QC 2026-11-18)
for j in range(ui + 1, len(lines)):
    if re.search(r'sha256 "[0-9a-f]{64}"', lines[j]):
        lines[j] = re.sub(r'sha256 "[0-9a-f]{64}"', f'sha256 "{sha}"', lines[j], count=1)
        break
else:
    sys.exit(f'post-release: no sha256 line after the url in {path}')
if ''.join(lines) == open(path).read():
    sys.exit(f'post-release: {path} unchanged — url/sha patterns did not match')
open(path, 'w').write(''.join(lines))
print(f'post-release: formula -> v{version} sha {sha[:12]}...')
PY
git -C "$tap" add -- "$formula_rel"
staged="$(git -C "$tap" diff --cached --name-only)"
[ "$staged" = "$formula_rel" ] || { echo "post-release: refusing — staged files: ${staged:-<none>}" >&2; exit 1; }
git -C "$tap" commit -q -m "motion-pipeline ${version}"
git -C "$tap" push -q origin main
echo "post-release: tap pushed ($formula_rel -> v${version}) from $tap"
