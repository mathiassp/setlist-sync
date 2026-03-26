#!/usr/bin/env python3
"""setlist-sync CLI — Match streaming playlists to your DJ library."""

import argparse
import re
import sys
import time


def main():
    # Handle subcommands before argparse (to avoid conflicts with positional source arg)
    if len(sys.argv) >= 2 and sys.argv[1] == "init":
        from setlist_sync.init import run_init
        run_init()
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "status":
        from setlist_sync.status import run_status
        run_status()
        return

    parser = argparse.ArgumentParser(
        prog="setlist-sync",
        description="Match a streaming playlist against your music library and "
        "create a playlist in your DJ software.\n\n"
        "Commands:\n"
        "  setlist-sync init      Interactive first-time setup\n"
        "  setlist-sync status    Show current configuration and library stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        help="Spotify playlist URL/URI or path to a CSV file",
    )
    parser.add_argument(
        "--playlist-name",
        help="Name for the created playlist (default: Spotify playlist name)",
    )

    # Output target overrides (override .env DJ_SOFTWARE)
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--rekordbox",
        nargs="?",
        const="db",
        metavar="XML_PATH",
        help="Use Rekordbox (overrides .env). Without path: database. With path: XML file",
    )
    target.add_argument(
        "--djay",
        action="store_true",
        help="Use djay Pro (overrides .env)",
    )
    target.add_argument(
        "--files",
        action="store_true",
        help="Copy matched files to an output folder with M3U playlist",
    )

    parser.add_argument(
        "--threshold",
        type=int,
        help="Fuzzy match threshold 0-100 (overrides .env MATCH_THRESHOLD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing anything",
    )
    parser.add_argument(
        "--handle-duplicates",
        action="store_true",
        help="Interactively choose between multiple library matches per track",
    )
    parser.add_argument(
        "--djay-db",
        metavar="PATH",
        help="Custom djay Pro database path (overrides .env DJAY_DB_PATH)",
    )
    parser.add_argument(
        "--rekordbox-output",
        metavar="PATH",
        help="Output path for Rekordbox XML (default: {input}_synced.xml)",
    )
    parser.add_argument(
        "--music-dir",
        help="Path to music library for --files mode (default: ~/Music)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for --files mode (default: output/)",
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Use symlinks instead of copies in --files mode",
    )
    args = parser.parse_args()

    # Load config
    from setlist_sync.config import (
        DJ_SOFTWARE, DJAY_DB_PATH, REKORDBOX_DB_PATH,
        REKORDBOX_XML_PATH, DEFAULT_THRESHOLD, is_configured,
    )

    # Auto-trigger init if not configured and no explicit flags
    if not is_configured() and not args.rekordbox and not args.djay and not args.files:
        print("setlist-sync is not configured yet.\n")
        from setlist_sync.init import run_init
        run_init()
        print("\nNow re-run your command:")
        print(f'  setlist-sync "{args.source}"')
        return

    # Determine which DJ software to use (CLI flags override .env)
    if args.djay:
        mode = "djay"
    elif args.rekordbox:
        mode = "rekordbox"
    elif args.files:
        mode = "files"
    elif DJ_SOFTWARE == "rekordbox":
        mode = "rekordbox"
    elif DJ_SOFTWARE == "djay":
        mode = "djay"
    else:
        mode = "djay"  # fallback default

    # Resolve threshold (CLI overrides .env)
    threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLD

    # Early check: djay mode requires djay to be closed
    if mode == "djay":
        from setlist_sync.djay.playlist import _is_djay_running
        if _is_djay_running():
            print("Error: djay Pro is running. Please close it before syncing.", file=sys.stderr)
            sys.exit(1)

    # 1. Load playlist (CSV file or Spotify URL)
    from pathlib import Path

    source = args.source
    is_file = Path(source).exists() or source.endswith(".csv") or source.endswith(".txt")

    if is_file:
        from setlist_sync.spotify_client import load_csv_playlist
        try:
            playlist = load_csv_playlist(source)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        from setlist_sync.spotify_client import fetch_playlist
        try:
            playlist = fetch_playlist(source)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Spotify error: {e}", file=sys.stderr)
            sys.exit(1)

    if not playlist["tracks"]:
        print("Playlist is empty — nothing to match.")
        sys.exit(0)

    # 2. Load library
    if mode == "rekordbox":
        from setlist_sync.rekordbox.library import load_rekordbox_library
        # Priority: CLI --rekordbox XML > .env XML > .env DB > auto-discovery
        if args.rekordbox and args.rekordbox != "db":
            xml_source = args.rekordbox
        elif REKORDBOX_XML_PATH:
            xml_source = REKORDBOX_XML_PATH
        else:
            xml_source = None
        library = load_rekordbox_library(xml_source)
    elif mode == "files":
        from setlist_sync.config import DEFAULT_MUSIC_DIR, LIBRARY_CACHE_FILE
        from setlist_sync.library_scanner import scan_library
        music_dir = args.music_dir or DEFAULT_MUSIC_DIR
        library = scan_library(music_dir=music_dir, cache_path=LIBRARY_CACHE_FILE)
    else:  # djay
        from setlist_sync.djay.library import load_djay_library
        db_path = args.djay_db or DJAY_DB_PATH
        library = load_djay_library(db_path=db_path)

    if not library:
        print("No tracks found in library.", file=sys.stderr)
        sys.exit(1)

    # 3. Fuzzy match
    from setlist_sync.matcher import match_tracks

    start = time.time()
    matched, unmatched = match_tracks(
        spotify_tracks=playlist["tracks"],
        library_tracks=library,
        threshold=threshold,
        collect_all=args.handle_duplicates,
    )
    elapsed = time.time() - start
    print(f"Matched in {elapsed:.1f}s")

    if args.handle_duplicates:
        from setlist_sync.duplicate_prompt import resolve_duplicates
        matched = resolve_duplicates(matched)

    # Derive playlist name
    name = args.playlist_name
    if not name:
        name = re.sub(r'[/\\:*?"<>|]', "", playlist["name"]).strip()
        name = name or "Playlist"

    # 4. Output
    if mode == "rekordbox":
        from setlist_sync.rekordbox.playlist import create_rekordbox_playlist
        # Use XML path if available
        if args.rekordbox and args.rekordbox != "db":
            xml_out = args.rekordbox
        elif REKORDBOX_XML_PATH:
            xml_out = REKORDBOX_XML_PATH
        else:
            xml_out = None
        create_rekordbox_playlist(
            playlist_name=name,
            matched_tracks=matched,
            xml_path=xml_out,
            output_path=args.rekordbox_output,
            dry_run=args.dry_run,
        )
    elif mode == "files":
        from setlist_sync.output import create_event_output
        create_event_output(
            event_name=name,
            matched=matched,
            unmatched=unmatched,
            output_dir=args.output_dir,
            use_symlinks=args.symlink,
        )
    else:  # djay
        from setlist_sync.djay.playlist import create_djay_playlist
        db_path = args.djay_db or DJAY_DB_PATH
        create_djay_playlist(
            playlist_name=name,
            matched_tracks=matched,
            db_path=db_path,
            dry_run=args.dry_run,
        )

    # 5. Summary
    total = len(playlist["tracks"])
    print(f"\nDone! {len(matched)}/{total} tracks matched, {len(unmatched)} unmatched.")
    if unmatched:
        print(f"\nUnmatched tracks:")
        for t in unmatched:
            print(f"  - {t['spotify_artist']} - {t['spotify_title']}")

    # 6. Check for updates
    from setlist_sync.update_check import check_for_update
    check_for_update()


if __name__ == "__main__":
    main()
