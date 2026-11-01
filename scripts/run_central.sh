#!/bin/sh
# Invoked by launchd on the central machine only. Pulls both peers, merges,
# re-imports the owned-library XML, and writes a fresh report. Uses the
# repo's own .venv explicitly, for the same reason as run_scan.sh.
cd "$(dirname "$0")/.."
mkdir -p logs
exec .venv/bin/python3 -m musicsync.cli run-central --config musicsync.toml
