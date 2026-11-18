#!/usr/bin/env bash
# tests/test_version_consistency.sh — the repo-owned version gate rtc-ship.sh defers to
# (plain-repo wiring, 2026-11-18). All version surfaces must state the same version:
# VERSION, release-manifest.json, pyproject.toml, motion_pipeline/__init__.py, CHANGELOG top.
# Exit 0 agree · 1 disagree. rtc_version_surface.py has no reader for .py or PEP 621 [project],
# so the app surfaces are pinned here rather than by the tool.
set -euo pipefail
top="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0

ver() { tr -d '[:space:]' < "$top/VERSION"; }
manifest_ver() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$top/release-manifest.json"; }
pyproject_ver() { sed -n -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$top/pyproject.toml" | head -1; }
init_ver() { sed -n -E 's/^__version__[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$top/motion_pipeline/__init__.py" | head -1; }
changelog_ver() { sed -n -E 's/^##+[[:space:]]+\[?v?([0-9]+\.[0-9]+\.[0-9]+)\]?.*/\1/p' "$top/CHANGELOG.md" | head -1; }

want="$(ver)"
for pair in "VERSION:$(ver)" "release-manifest.json:$(manifest_ver)" "pyproject.toml:$(pyproject_ver)" \
            "motion_pipeline/__init__.py:$(init_ver)" "CHANGELOG.md top:$(changelog_ver)"; do
  name="${pair%%:*}"; got="${pair#*:}"
  printf '  %s : %s\n' "$name" "${got:-<none>}"
  if [ -z "$got" ]; then echo "✖ $name holds no version" >&2; fail=1
  elif [ "$got" != "$want" ]; then echo "✖ $name says $got, VERSION says $want" >&2; fail=1; fi
done
[ "$fail" = 0 ] || exit 1
echo "version surfaces agree: $want"
