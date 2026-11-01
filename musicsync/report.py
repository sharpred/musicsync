"""Cross-references library.db (what's where) against owned (what you own)."""

from __future__ import annotations

import csv
import datetime
import html
import os
import shutil

from . import db
from .config import AppConfig


def build_report(config: AppConfig):
    conn = db.connect(os.path.join(config.state_dir, "library.db"))

    present: dict[str, set[str]] = {}
    for r in conn.execute("SELECT DISTINCT host, track_key FROM files"):
        present.setdefault(r["track_key"], set()).add(r["host"])

    owned_rows = conn.execute(
        "SELECT track_key, artist, title, album FROM owned ORDER BY artist, album, title"
    ).fetchall()
    conn.close()

    primary = config.primary_host
    missing_from_primary = []
    missing_everywhere = []
    seen = set()

    for r in owned_rows:
        key = r["track_key"]
        if key in seen:
            continue
        seen.add(key)
        hosts = present.get(key, set())
        row = (r["artist"], r["title"], r["album"])
        if not hosts:
            missing_everywhere.append(row)
        elif primary not in hosts:
            missing_from_primary.append((*row, sorted(hosts)))

    return missing_from_primary, missing_everywhere


def _write_html(path, primary, missing_from_primary, missing_everywhere, generated_at):
    def rows(items, with_hosts):
        out = []
        for item in items:
            artist, title, album = item[0], item[1], item[2]
            cells = [html.escape(artist or ""), html.escape(title or ""), html.escape(album or "")]
            if with_hosts:
                cells.append(html.escape(", ".join(item[3])))
            out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        return "\n".join(out) if out else '<tr><td colspan="4"><em>None</em></td></tr>'

    doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>musicsync report</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 2rem; color: #1a1a1a; background: #fff; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; font-size: 0.9rem; }}
  th {{ background: #f5f5f5; }}
  .meta {{ color: #666; font-size: 0.85rem; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1a1a1a; color: #eee; }}
    th {{ background: #2a2a2a; }}
    th, td {{ border-bottom: 1px solid #333; }}
    .meta {{ color: #999; }}
  }}
</style>
</head>
<body>
<h1>musicsync report</h1>
<p class="meta">Generated {html.escape(generated_at)} &middot; primary host: {html.escape(primary)}</p>

<h2>Missing from {html.escape(primary)} ({len(missing_from_primary)})</h2>
<table>
<tr><th>Artist</th><th>Title</th><th>Album</th><th>Present on</th></tr>
{rows(missing_from_primary, True)}
</table>

<h2>Missing from every machine ({len(missing_everywhere)})</h2>
<table>
<tr><th>Artist</th><th>Title</th><th>Album</th></tr>
{rows(missing_everywhere, False)}
</table>
</body>
</html>
"""
    with open(path, "w") as f:
        f.write(doc)


def write_reports(config: AppConfig):
    missing_from_primary, missing_everywhere = build_report(config)

    out_dir = os.path.join(config.state_dir, "reports")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_path = os.path.join(out_dir, f"report_{stamp}.csv")
    html_path = os.path.join(out_dir, f"report_{stamp}.html")
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "artist", "title", "album", "present_on"])
        for artist, title, album, hosts in missing_from_primary:
            w.writerow([f"missing_from_{config.primary_host}", artist, title, album, ";".join(hosts)])
        for artist, title, album in missing_everywhere:
            w.writerow(["missing_everywhere", artist, title, album, ""])

    _write_html(html_path, config.primary_host, missing_from_primary, missing_everywhere, generated_at)

    latest_csv = os.path.join(out_dir, "latest.csv")
    latest_html = os.path.join(out_dir, "latest.html")
    shutil.copyfile(csv_path, latest_csv)
    shutil.copyfile(html_path, latest_html)

    print(
        f"{len(missing_from_primary)} tracks missing from {config.primary_host}; "
        f"{len(missing_everywhere)} tracks missing from all machines."
    )
    print(f"Report: {html_path}")
    print(f"Latest symlink-equivalent: {latest_html}")

    return html_path, csv_path
