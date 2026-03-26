#!/usr/bin/env python3
"""setlist-sync CLI — Match streaming playlists to your DJ library."""

import argparse
import re
import sys
import time


def main():
    parser = argparse.ArgumentParser(
        prog="setlist-sync",
        description="Match a streaming playlist against your music library and "
        "create a playlist in your DJ software.",
    )
    parser.add_argument(
        "source",
        help="Spotify playlist URL/URI or path to a CSV file",
    )
    parser.add_argument(
        "--playlist-name",
        help="Name for the created playlist (default: Spotify playlist name)",
    )

    # Output target (mutually exclusive)
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--rekordbox",
        nargs="?",
        const="db",
        metavar="XML_PATH",
        help="Match against Rekordbox library. Without a path: reads database directly. "
        "With a path: uses XML file (e.g. --rekordbox collection.xml)",
    )
    target.add_argument(
        "--files",
        action="store_true",
        help="Copy matched files to an output folder with M3U playlist",
    )
    # djay is default when neither --rekordbox nor --files is specified

    parser.add_argument(
        "--threshold",
        type=int,
        default=85,
        help="Fuzzy match threshold 0-100 (default: 85)",
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
        help="Path to djay Pro database (default: ~/Music/djay/djay Media Library.djayMediaLibrary/MediaLibrary.db)",
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

    # Early check: djay mode requires djay to be closed
    use_djay = not args.rekordbox and not args.files
    if use_djay:
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
    if args.rekordbox:
        from setlist_sync.rekordbox.library import load_rekordbox_library
        xml_path = args.rekordbox if args.rekordbox != "db" else None
        library = load_rekordbox_library(xml_path)
    elif args.files:
        from setlist_sync.config import DEFAULT_MUSIC_DIR, LIBRARY_CACHE_FILE
        from setlist_sync.library_scanner import scan_library
        music_dir = args.music_dir or DEFAULT_MUSIC_DIR
        library = scan_library(music_dir=music_dir, cache_path=LIBRARY_CACHE_FILE)
    else:
        from setlist_sync.djay.library import load_djay_library
        library = load_djay_library(db_path=args.djay_db) if args.djay_db else load_djay_library()

    if not library:
        print("No tracks found in library.", file=sys.stderr)
        sys.exit(1)

    # 3. Fuzzy match
    from setlist_sync.matcher import match_tracks

    start = time.time()
    matched, unmatched = match_tracks(
        spotify_tracks=playlist["tracks"],
        library_tracks=library,
        threshold=args.threshold,
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
    if args.rekordbox:
        from setlist_sync.rekordbox.playlist import create_rekordbox_playlist
        xml_path = args.rekordbox if args.rekordbox != "db" else None
        create_rekordbox_playlist(
            playlist_name=name,
            matched_tracks=matched,
            xml_path=xml_path,
            output_path=args.rekordbox_output,
            dry_run=args.dry_run,
        )
    elif args.files:
        from setlist_sync.output import create_event_output
        create_event_output(
            event_name=name,
            matched=matched,
            unmatched=unmatched,
            output_dir=args.output_dir,
            use_symlinks=args.symlink,
        )
    else:
        from setlist_sync.djay.playlist import create_djay_playlist
        kwargs = {"playlist_name": name, "matched_tracks": matched, "dry_run": args.dry_run}
        if args.djay_db:
            kwargs["db_path"] = args.djay_db
        create_djay_playlist(**kwargs)

    # 5. Summary
    total = len(playlist["tracks"])
    print(f"\nDone! {len(matched)}/{total} tracks matched, {len(unmatched)} unmatched.")
    if unmatched:
        print(f"\nUnmatched tracks:")
        for t in unmatched:
            print(f"  - {t['spotify_artist']} - {t['spotify_title']}")


if __name__ == "__main__":
    main()
