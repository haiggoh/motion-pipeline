#!/usr/bin/env bash
# pre-flight.sh — flaky-shard pass: load-sensitive TUI/PTY/venv tests run SEPARATELY at low
# parallelism (Playbook-split-monolithic: the parallel gate must not pay for load flakes).
# 2026-11-21: four ship gates died on rotating flakes (PTY hang, pip timeout, render
# timeout, worker-cancel race) — all local-load, none NVIDIA (this repo's tests make no
# provider calls; tests/test_no_external_api_calls.py guards that).
set -euo pipefail
top="$(git rev-parse --show-toplevel)"
cd "$top"
.venv/bin/python -m pytest tests -q -p no:cacheprovider -m 'flaky' -rs   # serial: PTY/process tests are load-fragile
