"""Configuration and string normalization for setlist-sync."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# DJ Software preference
DJ_SOFTWARE = os.getenv("DJ_SOFTWARE", "").lower()  # "djay" or "rekordbox"

# Database paths
DJAY_DB_PATH = str(Path(os.getenv("DJAY_DB_PATH", str(
    Path.home() / "Music" / "djay" / "djay Media Library.djayMediaLibrary" / "MediaLibrary.db"
))).expanduser())
REKORDBOX_DB_PATH = os.getenv("REKORDBOX_DB_PATH", "")
if REKORDBOX_DB_PATH:
    REKORDBOX_DB_PATH = str(Path(REKORDBOX_DB_PATH).expanduser())
REKORDBOX_XML_PATH = os.getenv("REKORDBOX_XML_PATH", "")
if REKORDBOX_XML_PATH:
    REKORDBOX_XML_PATH = str(Path(REKORDBOX_XML_PATH).expanduser())

# Library settings
DEFAULT_MUSIC_DIR = str(Path(os.getenv("MUSIC_DIR", str(Path.home() / "Music"))).expanduser())
SUPPORTED_FORMATS = (".mp3", ".wav", ".aiff", ".flac", ".m4a", ".alac")
LIBRARY_CACHE_FILE = ".library_cache.json"

# Output settings
DEFAULT_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")

# Matching settings
DEFAULT_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "85"))
HANDLE_DUPLICATES = os.getenv("HANDLE_DUPLICATES", "false").lower() == "true"
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


def is_configured() -> bool:
    """Check if setlist-sync has been configured (DJ_SOFTWARE is set)."""
    return bool(DJ_SOFTWARE)


def get_env_path() -> Path:
    """Return the path to the .env file (in current directory or project root)."""
    # Check current directory first, then walk up to find project root
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        env_file = p / ".env"
        if env_file.exists():
            return env_file
        # Stop at home directory
        if p == Path.home():
            break
    return cwd / ".env"
