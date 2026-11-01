"""Pulls your Plex music library in over its HTTP API, as one more "host".

Unlike the Macs, the Plex box (e.g. a Minisforum mini-PC) likely isn't macOS
and may not have Python or SSH access set up at all -- so rather than
installing an agent on it, the central machine queries Plex's own API
directly over the network. Each Plex track becomes a `files` row with
host = config.plex.host_label, which means it folds straight into the
existing "missing from iMac" / "missing everywhere" reports for free: a
track Plex has is no longer "missing everywhere" just because no Mac has it.
"""

from __future__ import annotations

import datetime
import json
import os
import urllib.parse
import urllib.request

from . import db
from .config import AppConfig, PlexConfig
from .normalize import track_key

# Plex media "type" codes: 8 = artist, 9 = album, 10 = track.
_TRACK_TYPE = 10
_ARTIST_LIBRARY_TYPE = "artist"


def _get_json(url: str, token: str) -> dict:
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}X-Plex-Token={urllib.parse.quote(token)}"
    req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _find_music_section_key(base_url: str, token: str, library_section: str) -> str:
    data = _get_json(f"{base_url}/library/sections", token)
    directories = data.get("MediaContainer", {}).get("Directory", [])
    for d in directories:
        if d.get("type") == _ARTIST_LIBRARY_TYPE and d.get("title") == library_section:
            return d["key"]
    # Fall back to the first music-type library if the name didn't match.
    for d in directories:
        if d.get("type") == _ARTIST_LIBRARY_TYPE:
            return d["key"]
    raise RuntimeError(f"No Plex music library section found (looking for '{library_section}')")


def fetch_track_metadata(plex: PlexConfig) -> list[dict]:
    section_key = _find_music_section_key(plex.base_url, plex.token, plex.library_section)
    data = _get_json(f"{plex.base_url}/library/sections/{section_key}/all?type={_TRACK_TYPE}", plex.token)
    return data.get("MediaContainer", {}).get("Metadata", [])


def tracks_from_metadata(metadata: list[dict], host_label: str) -> list[dict]:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    records = []
    for t in metadata:
        title = t.get("title")
        if not title:
            continue
        artist = t.get("grandparentTitle") or t.get("originalTitle")
        album = t.get("parentTitle")

        media = t.get("Media") or []
        part = (media[0].get("Part") or [{}])[0] if media else {}
        path = part.get("file") or f"plex:{t.get('ratingKey', title)}"
        size = part.get("size")

        duration_ms = t.get("duration")
        duration = (duration_ms / 1000.0) if duration_ms else None

        records.append(
            dict(
                host=host_label,
                path=path,
                size=size,
                mtime=None,
                artist=artist,
                album=album,
                title=title,
                track_num=t.get("index"),
                duration=duration,
                track_key=track_key(artist, title),
                scanned_at=now,
            )
        )
    return records


def import_plex(config: AppConfig) -> None:
    if not config.plex:
        print("No [plex] section configured; skipping Plex import.")
        return

    metadata = fetch_track_metadata(config.plex)
    records = tracks_from_metadata(metadata, config.plex.host_label)

    lib_path = os.path.join(config.state_dir, "library.db")
    conn = db.connect(lib_path)
    db.init_schema(conn)
    db.replace_host_files(conn, config.plex.host_label, records)
    conn.commit()
    conn.close()

    print(f"Imported {len(records)} tracks from Plex ({config.plex.host_label}) at {config.plex.base_url}")
