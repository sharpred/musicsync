"""Generates .m3u8 playlists of tracks missing from the primary host.

Only covers "missing from <primary_host>" -- those tracks have a real file
on some other host, so a playlist pointing at it is meaningful. "Missing
everywhere" tracks have no file anywhere to point a playlist at, so there's
nothing to generate for them; that stays a plain list in the report.

One playlist is written per source host (not merged), because a file's path
is only valid on the machine that actually has it -- a playlist of MacAir's
paths only opens usefully in Music.app/iTunes running on MacAir itself.
Plex is excluded: its paths are on the Plex server's filesystem, which
doesn't run Music.app/iTunes at all.
"""

from __future__ import annotations

import os

from . import db
from .config import AppConfig


def _m3u_entry(artist, title, path) -> str:
    label = f"{artist} - {title}" if artist else (title or os.path.basename(path))
    return f"#EXTINF:-1,{label}\n{path}\n"


def missing_from_primary_by_host(conn, primary: str, exclude_hosts: set[str]) -> dict[str, list[dict]]:
    owned_keys = {r["track_key"] for r in conn.execute("SELECT DISTINCT track_key FROM owned")}

    rows = conn.execute("SELECT host, path, track_key, artist, title, album FROM files").fetchall()
    present: dict[str, set[str]] = {}
    for r in rows:
        present.setdefault(r["track_key"], set()).add(r["host"])

    by_host: dict[str, list[dict]] = {}
    for r in rows:
        key = r["track_key"]
        if key not in owned_keys:
            continue
        if r["host"] == primary or r["host"] in exclude_hosts:
            continue
        if primary in present.get(key, set()):
            continue
        by_host.setdefault(r["host"], []).append(dict(r))

    return by_host


def write_missing_playlists(config: AppConfig) -> list[str]:
    conn = db.connect(os.path.join(config.state_dir, "library.db"))
    exclude = {config.plex.host_label} if config.plex else set()
    by_host = missing_from_primary_by_host(conn, config.primary_host, exclude)
    conn.close()

    out_dir = os.path.join(config.state_dir, "playlists")
    os.makedirs(out_dir, exist_ok=True)

    written = []
    for host, tracks in by_host.items():
        safe_host = "".join(c if c.isalnum() else "_" for c in host)
        path = os.path.join(out_dir, f"missing_from_{config.primary_host}__{safe_host}.m3u8")
        tracks.sort(key=lambda r: (r["artist"] or "", r["album"] or "", r["title"] or ""))
        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for t in tracks:
                f.write(_m3u_entry(t["artist"], t["title"], t["path"]))
        written.append(path)
        print(f"Wrote {len(tracks)} tracks to {path} (open on {host} itself via File > Library > Import Playlist)")

    if not written:
        print("No 'missing from primary' tracks with a real file elsewhere -- nothing to write.")

    return written
