"""Fetch playlist tracks from Spotify or CSV files."""

import csv
import logging
import re
from pathlib import Path

from spotify_scraper import SpotifyClient

logging.getLogger("spotify_scraper").setLevel(logging.WARNING)

PLAYLIST_URL_PATTERN = re.compile(
    r"(?:https?://open\.spotify\.com/playlist/|spotify:playlist:)"
    r"([a-zA-Z0-9]+)"
)


def fetch_playlist(playlist_url: str) -> dict:
    """Fetch all tracks from a Spotify playlist using web scraping.

    No API key or Premium account required.
    """
    if not PLAYLIST_URL_PATTERN.search(playlist_url):
        raise ValueError(
            f"Invalid Spotify playlist URL: {playlist_url}\n"
            "Expected format: https://open.spotify.com/playlist/<id> "
            "or spotify:playlist:<id>"
        )

    client = SpotifyClient()
    data = client.get_playlist_info(playlist_url)

    name = data.get("name", "Unknown Playlist")
    owner = data.get("owner", {}).get("name", "") if isinstance(data.get("owner"), dict) else ""
    raw_tracks = data.get("tracks", [])

    print(f'Fetching playlist "{name}" ({len(raw_tracks)} tracks)...')

    tracks = []
    for t in raw_tracks:
        artists_data = t.get("artists", [])
        if isinstance(artists_data, list):
            artist_names = ", ".join(
                a["name"] if isinstance(a, dict) else str(a) for a in artists_data
            )
        else:
            artist_names = str(artists_data)

        title = t.get("name", "")
        if not title:
            continue

        tracks.append({
            "title": title,
            "artist": artist_names,
            "album": t.get("album", {}).get("name", "") if isinstance(t.get("album"), dict) else "",
            "spotify_uri": t.get("uri", ""),
        })

    return {"name": name, "owner": owner, "tracks": tracks}


def load_csv_playlist(file_path: str) -> dict:
    """Load tracks from a CSV file (e.g. exported via Exportify).

    Supports Exportify format (columns: Track Name, Artist Name(s))
    and simple format (columns: title, artist).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    tracks = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []

        # Detect column names (Exportify vs simple format)
        if "Track Name" in fields:
            title_col, artist_col = "Track Name", "Artist Name(s)"
        elif "track_name" in fields:
            title_col, artist_col = "track_name", "artist_name"
        elif "title" in fields:
            title_col, artist_col = "title", "artist"
        else:
            raise ValueError(
                f"Unrecognized CSV format. Expected columns like 'Track Name' and "
                f"'Artist Name(s)' (Exportify) or 'title' and 'artist'. "
                f"Found: {fields}"
            )

        for row in reader:
            title = row.get(title_col, "").strip()
            artist = row.get(artist_col, "").strip()
            if title:
                tracks.append({
                    "title": title,
                    "artist": artist,
                    "album": row.get("Album Name", row.get("album", "")),
                    "spotify_uri": row.get("Track URI", row.get("spotify_uri", "")),
                })

    name = path.stem
    print(f'Loaded CSV "{name}" ({len(tracks)} tracks)')
    return {"name": name, "owner": "", "tracks": tracks}
