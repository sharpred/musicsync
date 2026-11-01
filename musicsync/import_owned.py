"""Imports a Music.app Library.xml export as the canonical "what I own" list.

Must be the full library export (Music.app: File > Library > Export Library...),
NOT "Export Playlist" on the Purchased smart list. Export Playlist writes an
.m3u8 of local file paths, so any purchased-but-not-downloaded track (no local
file) is silently dropped before it ever reaches this tool. Export Library
writes a plist/XML with one entry per track containing Name/Artist/Album
regardless of whether it's downloaded, plus a "Location" key only when a local
file exists -- which is exactly the "what do I own, and is it downloaded here"
signal this tool needs.
"""

from __future__ import annotations

import os
import plistlib

from . import db
from .config import AppConfig
from .normalize import track_key


def parse_library_xml(path: str) -> list[dict]:
    with open(path, "rb") as f:
        data = plistlib.load(f)

    tracks = data.get("Tracks", {})
    records = []
    for track_id, t in tracks.items():
        name = t.get("Name")
        if not name:
            continue
        artist = t.get("Artist")
        album = t.get("Album")
        persistent_id = t.get("Persistent ID") or str(track_id)
        has_location = 1 if t.get("Location") else 0
        records.append(
            dict(
                persistent_id=persistent_id,
                artist=artist,
                album=album,
                title=name,
                track_key=track_key(artist, name),
                has_local_location=has_location,
            )
        )
    return records


def import_owned(config: AppConfig) -> None:
    if not config.owned_library_xml:
        print("No owned_library_xml configured; skipping owned-library import.")
        return
    if not os.path.exists(config.owned_library_xml):
        print(f"WARNING: owned_library_xml not found: {config.owned_library_xml}")
        return

    records = parse_library_xml(config.owned_library_xml)

    lib_path = os.path.join(config.state_dir, "library.db")
    conn = db.connect(lib_path)
    db.init_schema(conn)
    db.replace_owned(conn, records)
    conn.commit()
    conn.close()

    print(f"Imported {len(records)} owned tracks from {config.owned_library_xml}")
