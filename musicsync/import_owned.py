"""Imports an iTunes/Music.app Library.xml export as the canonical "what I own" list.

Must be the full library export -- File > Library > Export Library... in
either iTunes (High Sierra and earlier) or Music.app (Catalina and later;
same menu, same underlying XML format) -- NOT "Export Playlist" on the
Purchased smart list. Export Playlist writes an .m3u8 of local file paths, so
any purchased-but-not-downloaded track (no local file) is silently dropped
before it ever reaches this tool. Export Library writes a plist/XML with one
entry per track containing Name/Artist/Album regardless of whether it's
downloaded, plus a "Location" key only when a local file exists -- which is
exactly the "what do I own, and is it downloaded here" signal this tool needs.
"""

from __future__ import annotations

import datetime
import os
import plistlib

from . import db
from .config import AppConfig
from .normalize import track_key


def _is_podcast(t: dict) -> bool:
    """iTunes/Music store podcast episodes in the same Tracks dict as songs."""
    if t.get("Podcast"):
        return True
    if (t.get("Genre") or "").strip().lower() == "podcast":
        return True
    if "podcast" in (t.get("Kind") or "").strip().lower():
        return True
    # Podcast-only fields that never appear on a music track.
    if "Episode Order" in t or "Episode Global ID" in t:
        return True
    return False


def parse_library_xml(path: str) -> tuple[list[dict], int]:
    with open(path, "rb") as f:
        data = plistlib.load(f)

    tracks = data.get("Tracks", {})
    records = []
    skipped_podcasts = 0
    for track_id, t in tracks.items():
        name = t.get("Name")
        if not name:
            continue
        if _is_podcast(t):
            skipped_podcasts += 1
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
    return records, skipped_podcasts


def import_owned(config: AppConfig) -> None:
    if not config.owned_library_xml:
        print("No owned_library_xml configured; skipping owned-library import.")
        return
    if not os.path.exists(config.owned_library_xml):
        print(f"WARNING: owned_library_xml not found: {config.owned_library_xml}")
        return

    mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(config.owned_library_xml), tz=datetime.timezone.utc
    )
    age = datetime.datetime.now(datetime.timezone.utc) - mtime
    print(
        f"Reading {config.owned_library_xml} (exported {mtime.strftime('%Y-%m-%d %H:%M UTC')}, "
        f"{age.days}d{(age.seconds // 3600)}h ago -- if you added/removed anything since "
        f"then, re-export and re-copy it first)"
    )

    records, skipped_podcasts = parse_library_xml(config.owned_library_xml)

    lib_path = os.path.join(config.state_dir, "library.db")
    conn = db.connect(lib_path)
    db.init_schema(conn)
    db.replace_owned(conn, records)
    conn.commit()
    conn.close()

    print(
        f"Imported {len(records)} owned tracks from {config.owned_library_xml} "
        f"(skipped {skipped_podcasts} podcast episode(s))"
    )
