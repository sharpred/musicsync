#!/bin/sh
# Run this ONCE on the central machine (the one you set role = "central" in
# musicsync.toml). It creates a dedicated ed25519 key pair used only for
# musicsync's snapshot pulls, then copies the public half to each peer you
# list below so the central machine can rsync from them without a password.
#
# Usage:
#   scripts/setup_ssh.sh paulryanwork@imac.local paulryan@macair.local
#
# Prereqs on EACH peer machine first (System Settings > General > Sharing):
#   - Turn on "Remote Login" (this is what enables SSH).
#   - Note the account name shown (paulryanwork on the iMac, paulryan elsewhere).

set -e

KEY="$HOME/.ssh/musicsync_ed25519"

if [ ! -f "$KEY" ]; then
  echo "Generating dedicated key pair at $KEY (no passphrase, so launchd can use it unattended)..."
  ssh-keygen -t ed25519 -f "$KEY" -N "" -C "musicsync (do not use for anything else)"
else
  echo "Key already exists at $KEY, reusing it."
fi

if [ "$#" -eq 0 ]; then
  echo "No peers given. Re-run as: $0 user@host [user@host ...]"
  exit 0
fi

for peer in "$@"; do
  echo "Copying public key to $peer (you'll be prompted for that machine's password once)..."
  ssh-copy-id -i "${KEY}.pub" "$peer"
  echo "Verifying passwordless login to $peer..."
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 "$peer" 'echo ok from $(hostname)'
done

echo
echo "Done. Each peer's musicsync.toml peer entry should use:"
echo "  ssh_key = \"$KEY\""
