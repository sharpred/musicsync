"""Loads a per-machine musicsync.toml config.

Every machine gets its own copy of this repo and its own musicsync.toml
(copied from config.example.toml, never committed — paths differ per
machine). Only the "central" machine's config needs `peers` and
`owned_library_xml`; agent machines only need host_label/role/music_roots.
"""

from __future__ import annotations

import dataclasses
import os

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - older Python on e.g. the High Sierra iMac
    import tomli as tomllib  # type: ignore[no-redef]


@dataclasses.dataclass
class PeerConfig:
    label: str
    user: str
    host: str
    ssh_key: str
    remote_snapshot_path: str


@dataclasses.dataclass
class PlexConfig:
    base_url: str
    token: str
    library_section: str
    host_label: str


@dataclasses.dataclass
class AppConfig:
    host_label: str
    role: str
    music_roots: list[str]
    state_dir: str
    primary_host: str
    owned_library_xml: str | None
    peers: list[PeerConfig]
    plex: PlexConfig | None


def load_config(path: str) -> AppConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    peers = []
    for p in data.get("peers", []):
        p = dict(p)
        p["ssh_key"] = os.path.expanduser(p["ssh_key"])
        peers.append(PeerConfig(**p))
    owned_xml = data.get("owned_library_xml")

    plex_data = data.get("plex")
    plex = None
    if plex_data:
        plex = PlexConfig(
            base_url=plex_data["base_url"].rstrip("/"),
            token=plex_data["token"],
            library_section=plex_data.get("library_section", "Music"),
            host_label=plex_data.get("host_label", "Plex"),
        )

    return AppConfig(
        host_label=data["host_label"],
        role=data.get("role", "agent"),
        music_roots=[os.path.expanduser(r) for r in data.get("music_roots", [])],
        state_dir=os.path.expanduser(data.get("state_dir", "~/.musicsync")),
        primary_host=data.get("primary_host", "iMac"),
        owned_library_xml=os.path.expanduser(owned_xml) if owned_xml else None,
        peers=peers,
        plex=plex,
    )
