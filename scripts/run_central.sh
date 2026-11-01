#!/bin/sh
# Invoked by launchd on the central machine only. Pulls both peers, merges,
# re-imports the owned-library XML, and writes a fresh report.
cd "$(dirname "$0")/.."
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.pyenv/shims:$PATH"
exec python3 -m musicsync.cli run-central --config musicsync.toml
