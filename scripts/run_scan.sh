#!/bin/sh
# Invoked by launchd (see launchd/*.plist). Uses the repo's own .venv
# explicitly -- not plain `python3` off $PATH -- so a scheduled run always
# gets the interpreter that actually has mutagen installed, regardless of
# what the system's default python3 happens to be.
cd "$(dirname "$0")/.."
mkdir -p logs
exec .venv/bin/python3 -m musicsync.cli scan --config musicsync.toml
