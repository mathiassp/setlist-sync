"""Interactive setup for first-time users."""

import os
from pathlib import Path


def _find_djay_db() -> str | None:
    """Try to find djay Pro's database on this system."""
    default = Path.home() / "Music" / "djay" / "djay Media Library.djayMediaLibrary" / "MediaLibrary.db"
    if default.exists():
        return str(default)
    return None


def _find_rekordbox_db() -> str | None:
    """Try to find Rekordbox's database on this system."""
    # macOS
    mac_path = Path.home() / "Library" / "Pioneer" / "rekordbox" / "master.db"
    if mac_path.exists():
        return str(mac_path)
    # Windows
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        win_path = Path(appdata) / "Pioneer" / "rekordbox" / "master.db"
        if win_path.exists():
            return str(win_path)
    return None


def _count_tracks(software: str, db_path: str) -> int | None:
    """Try to count tracks in a database to verify it works."""
    try:
        if software == "djay":
            from setlist_sync.djay.library import load_djay_library
            tracks = load_djay_library(db_path=db_path)
            return len(tracks)
        elif software == "rekordbox":
            from setlist_sync.rekordbox.library import load_rekordbox_library
            tracks = load_rekordbox_library(source=None)
            return len(tracks)
    except Exception:
        return None


def run_init():
    """Interactive setup wizard."""
    print("Welcome to setlist-sync!\n")

    # 1. Choose DJ software
    print("Which DJ software do you use?")
    print("  1. djay Pro")
    print("  2. Rekordbox")
    print()

    while True:
        choice = input("> ").strip()
        if choice in ("1", "djay", "djay pro"):
            software = "djay"
            break
        elif choice in ("2", "rekordbox"):
            software = "rekordbox"
            break
        else:
            print("Please enter 1 or 2.")

    # 2. Find database
    print()
    db_path = ""
    xml_path = ""

    if software == "djay":
        print("Searching for djay database...")
        found = _find_djay_db()
        if found:
            print(f"  Found: {found}")
            use = input("  Use this path? [Y/n] ").strip().lower()
            if use in ("", "y", "yes"):
                db_path = found
            else:
                db_path = input("  Enter custom path: ").strip()
        else:
            print("  djay database not found at default location.")
            db_path = input("  Enter path to MediaLibrary.db: ").strip()

    elif software == "rekordbox":
        print("Searching for Rekordbox database...")
        found = _find_rekordbox_db()
        if found:
            print(f"  Found: {found}")
            use = input("  Use this path? [Y/n] ").strip().lower()
            if use in ("", "y", "yes"):
                db_path = found
            else:
                db_path = input("  Enter custom path: ").strip()
        else:
            print("  Rekordbox database not found at default location.")
            db_path = input("  Enter path to master.db (or leave empty for auto-discovery): ").strip()

        # Ask about XML
        print()
        print("  Do you also have a Rekordbox XML export?")
        print("  (If set, XML will be used instead of the database)")
        xml_path = input("  Path to XML (or press Enter to skip): ").strip()

    # 3. Verify database
    if db_path and os.path.exists(db_path):
        print()
        print("Verifying database...")
        count = _count_tracks(software, db_path)
        if count is not None:
            print(f"  Found {count} tracks!")
        else:
            print("  Could not read database. The path might be wrong or the software may need to be closed.")

    # 4. Match threshold
    print()
    threshold = input("Match threshold (default: 85, press Enter to keep): ").strip()
    if not threshold:
        threshold = "85"

    # 5. Write .env
    env_path = Path.cwd() / ".env"
    lines = [
        "# setlist-sync configuration",
        f"DJ_SOFTWARE={software}",
        "",
    ]

    if software == "djay":
        lines.append(f"DJAY_DB_PATH={db_path}")
    elif software == "rekordbox":
        lines.append(f"REKORDBOX_DB_PATH={db_path}")
        if xml_path:
            lines.append(f"REKORDBOX_XML_PATH={xml_path}")

    lines.extend([
        "",
        f"MATCH_THRESHOLD={threshold}",
        "",
    ])

    env_path.write_text("\n".join(lines))

    print(f"\nConfig saved to {env_path}")
    print()
    print("You're all set! Try:")
    print(f'  setlist-sync "https://open.spotify.com/playlist/..."')
    print()
    print("Run 'setlist-sync status' to verify your setup.")
