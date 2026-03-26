"""Read tracks from djay Pro's SQLite database (macOS only)."""

import datetime
import os
import platform
import sqlite3
import struct
from pathlib import Path

from setlist_sync.config import normalize_string


def _check_macos():
    if platform.system() != "Darwin":
        raise RuntimeError(
            "djay Pro integration is only available on macOS. "
            "Use --rekordbox for cross-platform support."
        )

DEFAULT_DJAY_DB = str(
    Path.home()
    / "Music"
    / "djay"
    / "djay Media Library.djayMediaLibrary"
    / "MediaLibrary.db"
)


def _extract_tsaf_strings(data: bytes) -> list[str]:
    """Extract all 0x08-prefixed null-terminated strings from a TSAF blob.

    Scans byte-by-byte for the pattern: 0x08 + printable UTF-8 + 0x00.
    This avoids issues with binary data between fields.
    """
    strings = []
    i = 0
    while i < len(data):
        if data[i] == 0x08:
            end = data.find(b"\x00", i + 1)
            if end > i and end - i < 500:
                try:
                    s = data[i + 1 : end].decode("utf-8")
                    if s and all(c.isprintable() or c.isspace() for c in s):
                        strings.append(s)
                        i = end + 1
                        continue
                except UnicodeDecodeError:
                    pass
        i += 1
    return strings


_CORE_DATA_EPOCH = datetime.datetime(2001, 1, 1)


def _extract_core_data_date(data: bytes, field_name: str) -> str:
    """Extract a Core Data timestamp (8-byte double) stored before a field marker.

    Returns date as YYYY-MM-DD string, or empty string if not found.
    """
    marker = b"\x08" + field_name.encode() + b"\x00"
    idx = data.find(marker)
    if idx < 8:
        return ""
    try:
        ts = struct.unpack("<d", data[idx - 8 : idx])[0]
        dt = _CORE_DATA_EPOCH + datetime.timedelta(seconds=ts)
        return dt.strftime("%Y-%m-%d")
    except (struct.error, OverflowError, ValueError):
        return ""


def _parse_tsaf_fields(data: bytes) -> dict:
    """Parse a TSAF blob into a dict of field name → value.

    In TSAF, string fields follow the pattern: value BEFORE field name.
    E.g.: [0x08]"Kanye West"[0x00][0x08]"artist"[0x00]

    Date fields (addedDate, modifiedDate) are stored as 8-byte Core Data
    timestamps (doubles, seconds since 2001-01-01) before their field marker.
    """
    strings = _extract_tsaf_strings(data)

    result = {}
    field_names = {"title", "artist", "album", "duration", "uuid", "titleID",
                   "addedDate", "modifiedDate", "artistUUIDs", "albumUUID",
                   "genreUUIDs", "contentType", "name", "parentUUID",
                   "playlistUUID", "mediaItemUUID"}

    for i, s in enumerate(strings):
        if s in field_names and i >= 1:
            value = strings[i - 1]
            if value not in field_names:
                result[s] = value

    # Extract date fields from binary data
    result["addedDate"] = _extract_core_data_date(data, "addedDate")
    result["modifiedDate"] = _extract_core_data_date(data, "modifiedDate")

    # The database key is typically strings[1] (after class name)
    if len(strings) >= 2:
        result["_key"] = strings[1]

    return result


def load_djay_library(db_path: str = DEFAULT_DJAY_DB) -> list[dict]:
    """Load all tracks from djay's database.

    Returns list of dicts with: title, artist, album, key, date_added, norm_title, norm_artist
    """
    _check_macos()
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"djay database not found: {db_path}")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    rows = conn.execute(
        "SELECT key, data FROM database2 WHERE collection='mediaItems'"
    ).fetchall()

    tracks = []
    for key, data in rows:
        fields = _parse_tsaf_fields(data)
        title = fields.get("title", "").strip()
        artist = fields.get("artist", "").strip()

        if not title:
            continue

        tracks.append({
            "title": title,
            "artist": artist,
            "album": fields.get("album", ""),
            "key": key,
            "date_added": fields.get("addedDate", ""),
            "norm_title": normalize_string(title),
            "norm_artist": normalize_string(artist),
        })

    conn.close()

    print(f"Loaded djay library: {len(tracks)} tracks")
    return tracks


if __name__ == "__main__":
    tracks = load_djay_library()
    print(f"\nFirst 10 tracks:")
    for t in tracks[:10]:
        print(f"  {t['artist']} - {t['title']} (key: {t['key'][:16]}...)")
