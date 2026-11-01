"""Dumps every raw tag mutagen can find in a single file -- for when a file
shows up with missing artist/title/album but `scan`'s warnings didn't fire
(meaning *some* tags exist, just not under the keys we look up). Much faster
than re-running a full `scan` over the whole library to check one file.
"""

from __future__ import annotations

from mutagen import File as MutagenFile


def debug_file(path: str) -> None:
    print(f"=== raw mutagen.File({path!r}) ===")
    try:
        mf_raw = MutagenFile(path)
    except Exception as e:
        print(f"  EXCEPTION opening (non-easy mode): {e!r}")
        mf_raw = None

    if mf_raw is not None:
        print(f"  type: {type(mf_raw).__name__}")
        print(f"  info: {getattr(mf_raw, 'info', None)}")
        if mf_raw.tags:
            print("  raw tag keys/values:")
            for k, v in mf_raw.tags.items():
                print(f"    {k!r} = {v!r}")
        else:
            print("  (no raw tags at all)")

    print(f"\n=== easy mutagen.File({path!r}, easy=True) ===")
    try:
        mf_easy = MutagenFile(path, easy=True)
    except Exception as e:
        print(f"  EXCEPTION opening (easy mode): {e!r}")
        return

    if mf_easy is None:
        print("  (mutagen didn't recognize this file type)")
        return

    if mf_easy.tags:
        print("  easy tag keys/values:")
        for k, v in mf_easy.tags.items():
            print(f"    {k!r} = {v!r}")
    else:
        print("  (no easy tags at all)")

    for key in ("artist", "title", "album", "albumartist", "tracknumber"):
        v = mf_easy.tags.get(key) if mf_easy.tags else None
        print(f"  easy.get({key!r}) = {v!r}")
