"""Best-effort normalization so the same song matches across rips/purchases/machines.

This is intentionally fuzzy, not exact: a CD rip and a purchased copy of the same
song rarely have identical tags (remaster suffixes, "feat." formatting, stray
punctuation). We normalize artist + title into a stable key and accept that a
handful of edge cases (e.g. deliberately different live recordings) may collide
or fail to collide. Good enough for "where is this roughly, or is it nowhere".
"""

from __future__ import annotations

import re
import unicodedata

_FEAT_RE = re.compile(r"\s*[\(\[]?\b(feat\.?|featuring|ft\.?)\b.*", re.IGNORECASE)
_NOISE_RE = re.compile(
    r"\s*[\(\[]\s*("
    r"remaster(ed)?(\s*\d{2,4})?"
    r"|deluxe(\s*edition)?"
    r"|bonus\s*track"
    r"|single(\s*version)?"
    r"|radio\s*edit"
    r"|album\s*version"
    r"|explicit"
    r"|clean"
    r")\s*[\)\]]",
    re.IGNORECASE,
)
_NONALNUM_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")
# CDDB/Gracenote-sourced rips sometimes embed the track number directly into
# the title tag ("02 Baltimore" instead of "Baltimore"). Stripped from titles
# only, never artists (would otherwise mangle a numeric artist name like
# "3 Doors Down"). Applied identically on both sides of every comparison, so
# a genuinely numeric title ("99 Luftballons") still matches itself fine --
# it just also strips a tiny bit of specificity for those rare titles.
_LEADING_TRACK_NUM_RE = re.compile(r"^\d{1,3}\s+")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _norm_part(s: str | None) -> str:
    if not s:
        return ""
    s = _strip_accents(s).lower()
    s = _FEAT_RE.sub("", s)
    s = _NOISE_RE.sub("", s)
    s = _NONALNUM_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _norm_title(s: str | None) -> str:
    return _LEADING_TRACK_NUM_RE.sub("", _norm_part(s))


def track_key(artist: str | None, title: str | None) -> str:
    """Stable match key for a track, independent of file/source."""
    return f"{_norm_part(artist)}::{_norm_title(title)}"
