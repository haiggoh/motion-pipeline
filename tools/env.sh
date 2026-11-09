#!/usr/bin/env bash
# env.sh — pinned motion-pipeline toolchain for macOS (Apple Silicon), ported from the
# P&G Cube One 10-bit pipeline.
#
# Source me (bash):   source tools/env.sh
# Run me for usage:   bash tools/env.sh --help
# Executing instead of sourcing prints usage and exports nothing.
#
# When sourced it sets:
#   PATH                    — fnm Node 24.19.0 first, then the repo .venv, then node_modules/.bin
#   HYPERFRAMES_BROWSER_PATH — pinned chrome-headless-shell 156.0.8078.4 under $MP_CHROME_DIR
#
# Environment variables:
#   MP_CHROME_DIR — override for the chrome root (default ~/.cache/motion-pipeline/chrome).
#                   If SET but missing, sourcing fails with exit 1 (no silent fallback).

_mp_env_usage() {
  cat <<'USAGE'
Usage:
  source tools/env.sh          activate the pinned toolchain (bash)
  bash  tools/env.sh --help    print this usage, export nothing, exit 0
  bash  tools/env.sh <other>   usage on stderr, exit 2

Sets when sourced:
  PATH                     node 24.19.0, repo .venv, node_modules/.bin (hyperframes 0.8.31 pinned)
  HYPERFRAMES_BROWSER_PATH $MP_CHROME_DIR/chrome-headless-shell/mac_arm-156.0.8078.4/chrome-headless-shell-mac-arm64/chrome-headless-shell
  HF_DIST                  node_modules/hyperframes/dist (seek helpers)

Environment variables read:
  MP_CHROME_DIR            chrome root override (default ~/.cache/motion-pipeline/chrome);
                           set-but-missing => error naming it, exit 1
USAGE
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  case "${1:-}" in
    --help|-h|"") _mp_env_usage; exit 0 ;;
    *) _mp_env_usage >&2; exit 2 ;;
  esac
fi

MP_SELF="${BASH_SOURCE[0]:-$0}"
MP_TOOLS_DIR="$(cd "$(dirname "$MP_SELF")" && pwd)"
MP_ROOT="$(cd "$MP_TOOLS_DIR/.." && pwd)"
MP_NODE24_BIN="$HOME/.local/share/fnm/node-versions/v24.19.0/installation/bin"
MP_VENV="$MP_ROOT/.venv"

if ! command -v fnm >/dev/null 2>&1; then
  echo "env.sh: fnm missing — install with: brew install fnm" >&2; return 1
fi
if [ ! -x "$MP_NODE24_BIN/node" ]; then
  echo "env.sh: Node 24.19.0 missing at $MP_NODE24_BIN — install with: fnm install 24.19.0" >&2; return 1
fi
if [ ! -x "$MP_VENV/bin/python" ]; then
  echo "env.sh: repo venv missing at $MP_VENV — uv venv --python /opt/homebrew/bin/python3.11 .venv && uv pip install --python .venv/bin/python -e '.[dev]'" >&2; return 1
fi

if [ -n "${MP_CHROME_DIR:-}" ] && [ ! -d "$MP_CHROME_DIR" ]; then
  echo "env.sh: MP_CHROME_DIR is set but does not exist: $MP_CHROME_DIR" >&2
  return 1
fi
MP_CHROME_DIR="${MP_CHROME_DIR:-$HOME/.cache/motion-pipeline/chrome}"
export MP_CHROME_DIR
export HYPERFRAMES_BROWSER_PATH="$MP_CHROME_DIR/chrome-headless-shell/mac_arm-156.0.8078.4/chrome-headless-shell-mac-arm64/chrome-headless-shell"
export PATH="$MP_NODE24_BIN:$MP_VENV/bin:$MP_ROOT/node_modules/.bin:$PATH"

if [ ! -x "$MP_ROOT/node_modules/.bin/hyperframes" ]; then
  echo "env.sh: hyperframes not installed — cd $MP_ROOT && npm install" >&2; return 1
fi
MP_HF_GOT="$("$MP_ROOT/node_modules/.bin/hyperframes" --version 2>/dev/null | tail -1)"
MP_HF_PIN="$(sed -n 's/.*"hyperframes": *"\([^"]*\)".*/\1/p' "$MP_ROOT/tools/versions.lock.json" 2>/dev/null | head -1)"
if [ -n "$MP_HF_PIN" ] && [ "$MP_HF_GOT" != "$MP_HF_PIN" ]; then
  echo "env.sh: hyperframes version mismatch: got '$MP_HF_GOT', pinned '$MP_HF_PIN' — npm install hyperframes@$MP_HF_PIN" >&2; return 1
fi
export HF_DIST="$MP_ROOT/node_modules/hyperframes/dist"

if [ -x "$HYPERFRAMES_BROWSER_PATH" ]; then
  MP_CHROME_STATE="installed"
else
  MP_CHROME_STATE="not installed yet — npx --yes @puppeteer/browsers install chrome-headless-shell@156.0.8078.4 --path \"$MP_CHROME_DIR\""
fi
echo "motion-pipeline env: node $(node --version) · python $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))') · hyperframes $MP_HF_GOT · chrome: $MP_CHROME_STATE"
