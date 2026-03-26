"""Show current setlist-sync configuration and library stats."""

import os
from pathlib import Path

from setlist_sync.config import (
    DJ_SOFTWARE,
    DJAY_DB_PATH,
    REKORDBOX_DB_PATH,
    REKORDBOX_XML_PATH,
    DEFAULT_THRESHOLD,
    get_env_path,
    is_configured,
)


def run_status():
    """Display current configuration and library stats."""
    env_path = get_env_path()

    print("setlist-sync status\n")

    # Config file
    if env_path.exists():
        print(f"  Config:     {env_path}")
    else:
        print("  Config:     Not found (run 'setlist-sync init')")
        return

    if not is_configured():
        print("  DJ Software: Not configured (run 'setlist-sync init')")
        return

    # DJ Software
    print(f"  DJ Software: {DJ_SOFTWARE}")
    print(f"  Threshold:   {DEFAULT_THRESHOLD}")

    # Database info
    if DJ_SOFTWARE == "djay":
        db_path = DJAY_DB_PATH
        print(f"  Database:    {db_path}")
        if Path(db_path).exists():
            try:
                from setlist_sync.djay.library import load_djay_library
                tracks = load_djay_library(db_path=db_path)
                print(f"  Tracks:      {len(tracks)}")
            except Exception as e:
                print(f"  Tracks:      Error reading database ({e})")
        else:
            print(f"  Tracks:      Database not found!")

    elif DJ_SOFTWARE == "rekordbox":
        if REKORDBOX_XML_PATH:
            print(f"  XML:         {REKORDBOX_XML_PATH}")
            if Path(REKORDBOX_XML_PATH).exists():
                try:
                    from setlist_sync.rekordbox.library import load_rekordbox_library
                    tracks = load_rekordbox_library(REKORDBOX_XML_PATH)
                    print(f"  Tracks:      {len(tracks)}")
                except Exception as e:
                    print(f"  Tracks:      Error reading XML ({e})")
            else:
                print(f"  Tracks:      XML file not found!")
        else:
            db_path = REKORDBOX_DB_PATH or "(auto-discovery)"
            print(f"  Database:    {db_path}")
            try:
                from setlist_sync.rekordbox.library import load_rekordbox_library
                tracks = load_rekordbox_library(source=None)
                print(f"  Tracks:      {len(tracks)}")
            except Exception as e:
                print(f"  Tracks:      Error reading database ({e})")

    print()
