"""Scan a music directory, read ID3 tags, and build a cached track index."""

import datetime
import json
import os
from pathlib import Path

import mutagen

from setlist_sync.config import SUPPORTED_FORMATS, normalize_string


def _read_tags(file_path: Path) -> dict:
    """Read ID3 / metadata tags from an audio file using mutagen.

    Falls back to filename parsing when tags are missing.
    """
    title = ""
    artist = ""
    album = ""

    try:
        audio = mutagen.File(str(file_path), easy=True)
        if audio and audio.tags:
            title = (audio.tags.get("title") or [""])[0]
            artist = (audio.tags.get("artist") or [""])[0]
            album = (audio.tags.get("album") or [""])[0]
    except Exception:
        # Mutagen could not read the file -- fall through to filename parsing.
        pass

    # Fallback: derive title (and possibly artist) from the filename.
    if not title:
        stem = file_path.stem
        if " - " in stem:
            parts = stem.split(" - ", maxsplit=1)
            artist = artist or parts[0].strip()
            title = parts[1].strip()
        else:
            title = stem.strip()

    # Get file modification time as date_added proxy
    try:
        mtime = file_path.stat().st_mtime
        date_added = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        date_added = ""

    return {
        "title": title,
        "artist": artist,
        "album": album,
        "path": str(file_path),
        "date_added": date_added,
        "norm_title": normalize_string(title),
        "norm_artist": normalize_string(artist),
    }


def _load_cache(cache_path: Path) -> dict:
    """Load the JSON cache file. Returns an empty dict on any failure."""
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache_path: Path, tracks: list[dict], mtimes: dict[str, float]) -> None:
    """Persist the track index and file modification times to disk."""
    payload = {"mtimes": mtimes, "tracks": tracks}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def scan_library(
    music_dir: str,
    cache_path: str = ".library_cache.json",
    force_rescan: bool = False,
) -> list[dict]:
    """Walk *music_dir* recursively, read tags, and return a list of track dicts.

    Results are cached to *cache_path*.  On subsequent runs only new or modified
    files are re-scanned and deleted files are pruned.  Pass *force_rescan=True*
    to ignore the cache entirely.
    """
    music_root = Path(music_dir).expanduser().resolve()
    cache_file = Path(cache_path)

    # ------------------------------------------------------------------
    # 1. Discover every audio file under music_root
    # ------------------------------------------------------------------
    current_files: dict[str, float] = {}
    for root, _dirs, files in os.walk(music_root):
        for name in files:
            if Path(name).suffix.lower() in SUPPORTED_FORMATS:
                full = Path(root) / name
                try:
                    current_files[str(full)] = full.stat().st_mtime
                except OSError:
                    continue

    # ------------------------------------------------------------------
    # 2. Load previous cache (unless forcing a full rescan)
    # ------------------------------------------------------------------
    cached_mtimes: dict[str, float] = {}
    cached_tracks_by_path: dict[str, dict] = {}

    if not force_rescan:
        cache_data = _load_cache(cache_file)
        cached_mtimes = cache_data.get("mtimes", {})
        for track in cache_data.get("tracks", []):
            cached_tracks_by_path[track["path"]] = track

    # ------------------------------------------------------------------
    # 3. Figure out what needs (re-)scanning
    # ------------------------------------------------------------------
    tracks: list[dict] = []
    new_count = 0

    for fpath, mtime in current_files.items():
        if fpath in cached_tracks_by_path and cached_mtimes.get(fpath) == mtime:
            # File unchanged -- reuse cached entry.
            tracks.append(cached_tracks_by_path[fpath])
        else:
            # New or modified file -- read tags.
            tracks.append(_read_tags(Path(fpath)))
            new_count += 1

    # Deleted files are implicitly dropped because we only iterate current_files.

    # ------------------------------------------------------------------
    # 4. Persist and report
    # ------------------------------------------------------------------
    _save_cache(cache_file, tracks, current_files)

    print(f"Scanning library... {len(tracks)} tracks found ({new_count} new since last scan)")

    return tracks
