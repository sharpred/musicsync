"""Cross-references library.db (what's where) against owned (what you own)
and, if configured, against your Plex library."""

from __future__ import annotations

import csv
import datetime
import html
import os
import shutil

from . import db
from .config import AppConfig


def _collect_presence(conn):
    present: dict[str, set[str]] = {}
    meta: dict[str, tuple] = {}
    for r in conn.execute("SELECT host, track_key, artist, title, album FROM files"):
        present.setdefault(r["track_key"], set()).add(r["host"])
        meta.setdefault(r["track_key"], (r["artist"], r["title"], r["album"]))
    return present, meta


def build_owned_report(conn, present, meta, primary: str):
    owned_rows = conn.execute(
        "SELECT track_key, artist, title, album FROM owned ORDER BY artist, album, title"
    ).fetchall()

    missing_from_primary = []
    missing_everywhere = []
    seen = set()

    for r in owned_rows:
        key = r["track_key"]
        if key in seen:
            continue
        seen.add(key)
        hosts = present.get(key, set())
        row = meta.get(key, (r["artist"], r["title"], r["album"]))
        if not hosts:
            missing_everywhere.append(row)
        elif primary not in hosts:
            missing_from_primary.append((*row, sorted(hosts)))

    return missing_from_primary, missing_everywhere


def build_plex_gap_report(present, meta, plex_host: str):
    """Direct gap check between Plex and every other (Mac) host -- independent
    of the owned-library cross-reference, so it also surfaces anything on
    your Macs or in Plex that never made it into Library.xml."""
    on_macs_not_plex = []
    in_plex_not_macs = []

    for key, hosts in present.items():
        mac_hosts = hosts - {plex_host}
        on_mac = bool(mac_hosts)
        on_plex = plex_host in hosts
        row = meta.get(key, (None, None, None))
        if on_mac and not on_plex:
            on_macs_not_plex.append((*row, sorted(mac_hosts)))
        elif on_plex and not on_mac:
            in_plex_not_macs.append(row)

    on_macs_not_plex.sort(key=lambda r: (r[0] or "", r[2] or "", r[1] or ""))
    in_plex_not_macs.sort(key=lambda r: (r[0] or "", r[2] or "", r[1] or ""))
    return on_macs_not_plex, in_plex_not_macs


def build_report(config: AppConfig):
    conn = db.connect(os.path.join(config.state_dir, "library.db"))
    present, meta = _collect_presence(conn)

    missing_from_primary, missing_everywhere = build_owned_report(conn, present, meta, config.primary_host)
    conn.close()

    plex_gaps = None
    if config.plex:
        plex_gaps = build_plex_gap_report(present, meta, config.plex.host_label)

    return missing_from_primary, missing_everywhere, plex_gaps


def _rows_html(items, with_hosts):
    out = []
    for item in items:
        artist, title, album = item[0], item[1], item[2]
        cells = [html.escape(artist or ""), html.escape(title or ""), html.escape(album or "")]
        if with_hosts:
            cells.append(html.escape(", ".join(item[3])))
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    colspan = 4 if with_hosts else 3
    return "\n".join(out) if out else f'<tr><td colspan="{colspan}"><em>None</em></td></tr>'


def _write_html(path, config: AppConfig, missing_from_primary, missing_everywhere, plex_gaps, generated_at):
    primary = config.primary_host

    plex_section = ""
    if plex_gaps is not None:
        on_macs_not_plex, in_plex_not_macs = plex_gaps
        plex_host = html.escape(config.plex.host_label)
        plex_section = f"""
<h2>On your Macs but not in {plex_host} ({len(on_macs_not_plex)})</h2>
<table>
<tr><th>Artist</th><th>Title</th><th>Album</th><th>Present on</th></tr>
{_rows_html(on_macs_not_plex, True)}
</table>

<h2>In {plex_host} but not on any Mac ({len(in_plex_not_macs)})</h2>
<table>
<tr><th>Artist</th><th>Title</th><th>Album</th></tr>
{_rows_html(in_plex_not_macs, False)}
</table>
"""

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
{_rows_html(missing_from_primary, True)}
</table>

<h2>Missing from every machine ({len(missing_everywhere)})</h2>
<table>
<tr><th>Artist</th><th>Title</th><th>Album</th></tr>
{_rows_html(missing_everywhere, False)}
</table>
{plex_section}
</body>
</html>
"""
    with open(path, "w") as f:
        f.write(doc)


def write_reports(config: AppConfig):
    missing_from_primary, missing_everywhere, plex_gaps = build_report(config)

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
        if plex_gaps is not None:
            on_macs_not_plex, in_plex_not_macs = plex_gaps
            for artist, title, album, hosts in on_macs_not_plex:
                w.writerow(["on_macs_not_plex", artist, title, album, ";".join(hosts)])
            for artist, title, album in in_plex_not_macs:
                w.writerow(["in_plex_not_macs", artist, title, album, ""])

    _write_html(html_path, config, missing_from_primary, missing_everywhere, plex_gaps, generated_at)

    latest_csv = os.path.join(out_dir, "latest.csv")
    latest_html = os.path.join(out_dir, "latest.html")
    shutil.copyfile(csv_path, latest_csv)
    shutil.copyfile(html_path, latest_html)

    summary = (
        f"{len(missing_from_primary)} tracks missing from {config.primary_host}; "
        f"{len(missing_everywhere)} tracks missing from all machines."
    )
    if plex_gaps is not None:
        on_macs_not_plex, in_plex_not_macs = plex_gaps
        summary += (
            f" {len(on_macs_not_plex)} on Macs but not in Plex; "
            f"{len(in_plex_not_macs)} in Plex but not on any Mac."
        )
    print(summary)
    print(f"Report: {html_path}")
    print(f"Latest symlink-equivalent: {latest_html}")

    return html_path, csv_path
