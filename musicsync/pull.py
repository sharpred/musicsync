"""Pulls every peer machine's snapshot.db file to the central machine over SSH.

Uses a dedicated key pair (see scripts/setup_ssh.sh) so this never touches the
user's personal SSH keys, and BatchMode so a misconfigured host fails fast
instead of hanging on a password prompt.
"""

from __future__ import annotations

import os
import subprocess

from .config import AppConfig


def pull(config: AppConfig) -> None:
    incoming_dir = os.path.join(config.state_dir, "incoming")
    os.makedirs(incoming_dir, exist_ok=True)

    if not config.peers:
        print("No peers configured; nothing to pull.")
        return

    for peer in config.peers:
        dest = os.path.join(incoming_dir, f"{peer.label}.db")
        remote = f"{peer.user}@{peer.host}:{peer.remote_snapshot_path}"
        cmd = [
            "rsync",
            "-az",
            "-e",
            f"ssh -i {peer.ssh_key} -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new",
            remote,
            dest,
        ]
        print(f"Pulling {peer.label} ({remote}) -> {dest}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  WARNING: pull from {peer.label} failed: {result.stderr.strip()}")
        else:
            print("  OK")
