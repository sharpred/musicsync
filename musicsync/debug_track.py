"""Prints raw owned + files rows matching a search term, with their computed
track_key, so you can see exactly why a track did or didn't match.

Run this on the central machine whenever the report looks wrong -- e.g. a
track reported "missing from iMac" that you know is actually there. It'll
show you the owned-list entry's artist/title next to the iMac scan's
artist/title; if the track_key strings differ, that's the mismatch, and the
printed values show exactly which field (and which characters) disagree.
"""

from __future__ import annotations

import os

from . import db
from .config import AppConfig


def debug_track(config: AppConfig, query: str) -> None:
    conn = db.connect(os.path.join(config.state_dir, "library.db"))
    like = f"%{query}%"

    print(f"=== owned rows matching '{query}' ===")
    owned_rows = conn.execute(
        "SELECT persistent_id, artist, title, album, track_key, has_local_location FROM owned "
        "WHERE artist LIKE ? OR title LIKE ? OR album LIKE ?",
        (like, like, like),
    ).fetchall()
    if not owned_rows:
        print("  (no matches)")
    for r in owned_rows:
        print(f"  artist={r['artist']!r} title={r['title']!r} album={r['album']!r}")
        print(f"    track_key={r['track_key']!r} has_local_location={r['has_local_location']}")

    print(f"\n=== files rows matching '{query}' ===")
    file_rows = conn.execute(
        "SELECT host, path, artist, title, album, track_key FROM files "
        "WHERE artist LIKE ? OR title LIKE ? OR album LIKE ?",
        (like, like, like),
    ).fetchall()
    if not file_rows:
        print("  (no matches -- this track may not have been scanned at all; check music_roots)")
    for r in file_rows:
        print(f"  host={r['host']} artist={r['artist']!r} title={r['title']!r} album={r['album']!r}")
        print(f"    track_key={r['track_key']!r} path={r['path']}")

    conn.close()
