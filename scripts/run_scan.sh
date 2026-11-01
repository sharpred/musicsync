#!/bin/sh
# Invoked by launchd (see launchd/*.plist). launchd's default PATH is tiny,
# so we widen it here to cover Homebrew, python.org installs, and pyenv.
cd "$(dirname "$0")/.."
mkdir -p logs
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.pyenv/shims:$PATH"
exec python3 -m musicsync.cli scan --config musicsync.toml
