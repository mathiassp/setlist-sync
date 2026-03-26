"""Read tracks from Rekordbox's database or XML export."""

import xml.etree.ElementTree as ET
from urllib.parse import unquote

from setlist_sync.config import normalize_string


def load_rekordbox_library(source: str = None) -> list[dict]:
    """Load tracks from Rekordbox.

    If source is None or 'db', reads directly from Rekordbox's database.
    If source is a path to an XML file, parses the XML export.
    """
    if source and source.endswith(".xml"):
        return _load_from_xml(source)
    return _load_from_database()


def _load_from_database() -> list[dict]:
    """Load tracks directly from Rekordbox's encrypted SQLite database."""
    from pyrekordbox import Rekordbox6Database

    db = Rekordbox6Database()
    tracks = []

    for track in db.get_content():
        title = (track.Title or "").strip()
        if not title:
            continue

        artist = ""
        if track.Artist:
            artist = track.Artist.Name or ""

        date_added = ""
        if hasattr(track, "DateAdded") and track.DateAdded:
            date_added = str(track.DateAdded)

        tracks.append({
            "title": title,
            "artist": artist,
            "album": track.Album.Name if track.Album else "",
            "key": str(track.ID),
            "date_added": date_added,
            "norm_title": normalize_string(title),
            "norm_artist": normalize_string(artist),
        })

    print(f"Loaded Rekordbox library: {len(tracks)} tracks")
    return tracks


def _load_from_xml(xml_path: str) -> list[dict]:
    """Load tracks from a Rekordbox XML export."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    tracks = []
    for track_el in root.findall(".//COLLECTION/TRACK"):
        title = track_el.get("Name", "").strip()
        if not title:
            continue

        artist = track_el.get("Artist", "").strip()
        tracks.append({
            "title": title,
            "artist": artist,
            "album": track_el.get("Album", ""),
            "key": track_el.get("TrackID", ""),
            "location": _sanitize_path(track_el.get("Location", "")),
            "date_added": track_el.get("DateAdded", ""),
            "norm_title": normalize_string(title),
            "norm_artist": normalize_string(artist),
        })

    print(f"Loaded Rekordbox library: {len(tracks)} tracks from {xml_path}")
    return tracks


def _sanitize_path(location: str) -> str:
    path = unquote(location)
    if path.startswith("file://localhost/"):
        path = path[len("file://localhost"):]
    return path
