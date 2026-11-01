"""Merges this machine's own snapshot plus pulled peer snapshots into library.db."""

from __future__ import annotations

import datetime
import os
import sqlite3

from . import db
from .config import AppConfig


def _age_str(path: str) -> str:
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path), tz=datetime.timezone.utc)
    age = datetime.datetime.now(datetime.timezone.utc) - mtime
    return f"{mtime.strftime('%Y-%m-%d %H:%M UTC')}, {age.days}d{age.seconds // 3600}h ago"


def _merge_snapshot(conn: sqlite3.Connection, snapshot_path: str) -> int:
    if not os.path.exists(snapshot_path):
        print(f"  (missing, skipped: {snapshot_path})")
        return 0

    print(f"  snapshot file last written: {_age_str(snapshot_path)}")

    src = sqlite3.connect(snapshot_path)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM files").fetchall()
    src.close()

    by_host: dict[str, list[dict]] = {}
    for r in rows:
        by_host.setdefault(r["host"], []).append(dict(r))

    for host, records in by_host.items():
        db.replace_host_files(conn, host, records)

    return len(rows)


def merge(config: AppConfig) -> None:
    lib_path = os.path.join(config.state_dir, "library.db")
    conn = db.connect(lib_path)
    db.init_schema(conn)

    own_snapshot = os.path.join(config.state_dir, "snapshot.db")
    print(f"Merging own snapshot ({config.host_label}): {own_snapshot}")
    total = _merge_snapshot(conn, own_snapshot)

    incoming_dir = os.path.join(config.state_dir, "incoming")
    if os.path.isdir(incoming_dir):
        for fn in sorted(os.listdir(incoming_dir)):
            if fn.endswith(".db"):
                path = os.path.join(incoming_dir, fn)
                print(f"Merging peer snapshot: {path}")
                total += _merge_snapshot(conn, path)

    conn.commit()
    conn.close()
    print(f"Merged {total} file rows into {lib_path}")
