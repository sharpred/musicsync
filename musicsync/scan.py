"""Walks this machine's music folders and records what's here into snapshot.db.

Runs standalone on every machine (including the High Sierra iMac) — stdlib
plus mutagen only, no compiled dependencies.
"""

from __future__ import annotations

import datetime
import os

from mutagen import File as MutagenFile

from . import db
from .config import AppConfig
from .normalize import track_key

AUDIO_EXTS = {".mp3", ".m4a", ".m4p", ".m4b", ".aac", ".flac", ".alac", ".aiff", ".aif", ".wav", ".ogg", ".wma"}
# WAV has no standard tagging convention most rippers honor -- no tags there
# is the normal case, not a sign anything's wrong, so don't warn about it.
_NO_TAG_WARNING_EXEMPT_EXTS = {".wav"}
# Apple package bundles that can contain non-music audio assets (UI sound
# effects, etc.) alongside real tracks -- .itlp is the old (2009-2011)
# "iTunes LP" interactive/enhanced album format. Their contents aren't songs
# and shouldn't be scanned as if they were.
_SKIP_BUNDLE_EXTS = {".itlp", ".ite"}


def iter_audio_files(roots: list[str]):
    for root in roots:
        if not os.path.isdir(root):
            print(f"  WARNING: music root does not exist, skipping: {root}")
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames if os.path.splitext(d)[1].lower() not in _SKIP_BUNDLE_EXTS
            ]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in AUDIO_EXTS:
                    yield os.path.join(dirpath, fn)


def read_tags(path: str):
    artist = album = title = None
    track_num = None
    duration = None
    try:
        mf = MutagenFile(path, easy=True)
    except Exception as e:
        print(f"  WARNING: could not read tags from {path}: {e!r}")
        mf = None
    else:
        if mf is None:
            print(f"  WARNING: mutagen didn't recognize file type, no tags read: {path}")

    if mf is not None:
        tags = mf.tags or {}
        if not tags and os.path.splitext(path)[1].lower() not in _NO_TAG_WARNING_EXEMPT_EXTS:
            print(f"  WARNING: file opened but has no tags at all (untagged or DRM?): {path}")

        def first(key):
            v = tags.get(key)
            return v[0] if v else None

        artist = first("artist")
        album = first("album")
        title = first("title")
        tracknumber = first("tracknumber")
        if tracknumber:
            try:
                track_num = int(str(tracknumber).split("/")[0])
            except ValueError:
                track_num = None
        info = getattr(mf, "info", None)
        if info is not None:
            duration = getattr(info, "length", None)

    if not title:
        title = os.path.splitext(os.path.basename(path))[0]

    return artist, album, title, track_num, duration


def scan(roots: list[str], host_label: str) -> list[dict]:
    records = []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for path in iter_audio_files(roots):
        try:
            st = os.stat(path)
        except OSError:
            continue
        artist, album, title, trk, duration = read_tags(path)
        records.append(
            dict(
                host=host_label,
                path=path,
                size=st.st_size,
                mtime=st.st_mtime,
                artist=artist,
                album=album,
                title=title,
                track_num=trk,
                duration=duration,
                track_key=track_key(artist, title),
                scanned_at=now,
            )
        )
    return records


def main(config: AppConfig) -> None:
    print(f"Scanning {len(config.music_roots)} root(s) on {config.host_label}...")
    records = scan(config.music_roots, config.host_label)

    snapshot_path = os.path.join(config.state_dir, "snapshot.db")
    conn = db.connect(snapshot_path)
    db.init_schema(conn)
    db.replace_host_files(conn, config.host_label, records)
    conn.commit()
    conn.close()

    print(f"Scanned {len(records)} tracks on {config.host_label}. Snapshot: {snapshot_path}")
