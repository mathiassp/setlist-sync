import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Spotify credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")
SPOTIFY_USERNAME = os.getenv("SPOTIFY_USERNAME")

# Library settings
DEFAULT_MUSIC_DIR = str(Path.home() / "Music")
SUPPORTED_FORMATS = (".mp3", ".wav", ".aiff", ".flac", ".m4a", ".alac")
LIBRARY_CACHE_FILE = ".library_cache.json"

# Matching settings
DEFAULT_THRESHOLD = 85
TITLE_WEIGHT = 0.6
ARTIST_WEIGHT = 0.4

# Patterns to strip from track titles for better matching
STRIP_PATTERNS = [
    r"\(feat\.?\s+[^)]+\)",       # (feat. Artist)
    r"\(ft\.?\s+[^)]+\)",         # (ft. Artist)
    r"\(with\s+[^)]+\)",          # (with Artist)
    r"\(remaster(ed)?\s*\d*\)",   # (Remastered 2023)
    r"\(radio\s+edit\)",          # (Radio Edit)
    r"\(single\s+edit\)",         # (Single Edit)
    r"\(original\s+mix\)",        # (Original Mix)
    r"\(album\s+version\)",       # (Album Version)
    r"\(deluxe(\s+edition)?\)",   # (Deluxe Edition)
    r"\(live\)",                   # (Live)
    r"\(acoustic\)",               # (Acoustic)
    r"-\s*single\s+edit",         # - Single Edit
    r"-\s*radio\s+edit",          # - Radio Edit
    r"-\s*remaster(ed)?\s*\d*",   # - Remastered 2023
]

_strip_regex = re.compile("|".join(STRIP_PATTERNS), re.IGNORECASE)


def normalize_string(s: str) -> str:
    """Clean up strings for better fuzzy matching."""
    s = s.lower()
    s = _strip_regex.sub("", s)
    s = s.replace("&", "and")
    s = re.sub(r"[^\w\s]", " ", s)  # replace punctuation with spaces
    s = re.sub(r"\s+", " ", s)      # collapse multiple spaces
    return s.strip()
