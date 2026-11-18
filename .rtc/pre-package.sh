#!/usr/bin/env bash
# pre-package.sh — build the deterministic release tarball (git archive, mp-<version>/ prefix).
# The tap formula consumes exactly this asset: the auto-generated archive/refs/tags tarball is
# NOT byte-stable across downloads, so the sha256 would not pin.
#
# usage: .rtc/pre-package.sh [--help]
#   (no args)   build dist/mp-<VERSION>.tar.gz from HEAD (VERSION is the version source)
#   --help      print this usage, exit 0
# env: none (VERSION supplies the version)
set -euo pipefail
case "${1:-}" in
  "") ;;
  -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "usage: .rtc/pre-package.sh [--help] (no other arguments)" >&2; exit 2 ;;
esac
top="$(git rev-parse --show-toplevel)"
version="$(tr -d '[:space:]' < "$top/VERSION")"
mkdir -p "$top/dist"
rm -f "$top/dist/mp-$version.tar.gz"
git -C "$top" archive --prefix="mp-$version/" -o "$top/dist/mp-$version.tar.gz" HEAD
echo "pre-package: dist/mp-$version.tar.gz"
