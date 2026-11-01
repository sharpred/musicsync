"""Shared sqlite schema + helpers for snapshot and library databases.

Both the per-machine snapshot.db and the merged library.db use the same
`files` table shape, so merging is just "copy rows from one db into another".
"""

from __future__ import annotations

import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    host TEXT NOT NULL,
    path TEXT NOT NULL,
    size INTEGER,
    mtime REAL,
    artist TEXT,
    album TEXT,
    title TEXT,
    track_num INTEGER,
    duration REAL,
    track_key TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    PRIMARY KEY (host, path)
);
CREATE INDEX IF NOT EXISTS idx_files_track_key ON files(track_key);

CREATE TABLE IF NOT EXISTS owned (
    persistent_id TEXT PRIMARY KEY,
    artist TEXT,
    album TEXT,
    title TEXT,
    track_key TEXT NOT NULL,
    has_local_location INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_owned_track_key ON owned(track_key);
"""


def connect(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def replace_host_files(conn: sqlite3.Connection, host: str, records: list[dict]) -> None:
    """Swap in a fresh set of files for `host`, dropping anything no longer scanned."""
    conn.execute("DELETE FROM files WHERE host = ?", (host,))
    if not records:
        return
    conn.executemany(
        """
        INSERT INTO files
            (host, path, size, mtime, artist, album, title, track_num, duration, track_key, scanned_at)
        VALUES
            (:host, :path, :size, :mtime, :artist, :album, :title, :track_num, :duration, :track_key, :scanned_at)
        """,
        records,
    )


def replace_owned(conn: sqlite3.Connection, records: list[dict]) -> None:
    conn.execute("DELETE FROM owned")
    if not records:
        return
    conn.executemany(
        """
        INSERT INTO owned (persistent_id, artist, album, title, track_key, has_local_location)
        VALUES (:persistent_id, :artist, :album, :title, :track_key, :has_local_location)
        """,
        records,
    )
