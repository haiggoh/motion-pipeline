#!/usr/bin/env bash
# tests/test_version_consistency.sh — the repo-owned version gate rtc-ship.sh defers to
# (plain-repo wiring, 2026-11-18). All version surfaces must state the same version:
# VERSION, release-manifest.json, pyproject.toml, motion_pipeline/__init__.py, CHANGELOG top.
# Exit 0 agree · 1 disagree. Parsed, not grepped-first-match (QC 2026-11-18): pyproject via
# tomllib ([project].version, immune to decoy tables), __version__ must appear EXACTLY once
# (Python binds the last assignment; a first-match read would stay green on a duplicate),
# CHANGELOG top = the FIRST `## ` heading (deeper levels ignored), VERSION must be x.y.z.
set -euo pipefail
top="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0

ver() { tr -d '[:space:]' < "$top/VERSION"; }
manifest_ver() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$top/release-manifest.json"; }
pyproject_ver() { python3 - "$top/pyproject.toml" <<'PY'
import sys
import tomllib
print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])
PY
}
init_ver() { python3 - "$top/motion_pipeline/__init__.py" <<'PY'
import re
import sys

ms = re.findall(r'^__version__\s*=\s*"([^"]+)"', open(sys.argv[1]).read(), re.M)
assert len(ms) == 1, f'want exactly one __version__ assignment, got {ms}'
print(ms[0])
PY
}
changelog_ver() { sed -n -E 's/^##[[:space:]]+\[?v?([0-9]+\.[0-9]+\.[0-9]+)\]?.*/\1/p' "$top/CHANGELOG.md" | head -1; }

want="$(ver)"
if ! [[ "$want" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "✖ VERSION is not x.y.z: '$want'" >&2
  exit 1
fi
for pair in "VERSION:$(ver)" "release-manifest.json:$(manifest_ver)" "pyproject.toml:$(pyproject_ver)" \
            "motion_pipeline/__init__.py:$(init_ver)" "CHANGELOG.md top:$(changelog_ver)"; do
  name="${pair%%:*}"; got="${pair#*:}"
  printf '  %s : %s\n' "$name" "${got:-<none>}"
  if [ -z "$got" ]; then echo "✖ $name holds no version" >&2; fail=1
  elif [ "$got" != "$want" ]; then echo "✖ $name says $got, VERSION says $want" >&2; fail=1; fi
done
[ "$fail" = 0 ] || exit 1
echo "version surfaces agree: $want"
