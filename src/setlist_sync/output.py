"""
Output manager for music-matching.

Creates event-specific output folders containing matched music files,
an M3U playlist, an unmatched tracks list, and a CSV match report.
"""

import csv
import os
import re
import shutil
from pathlib import Path


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames on common filesystems."""
    return re.sub(r'[/\\:*?"<>|]', "", name)


def _unique_folder(base: Path) -> Path:
    """Return *base* if it does not exist, otherwise base_2, base_3, etc."""
    if not base.exists():
        return base
    n = 2
    while True:
        candidate = base.with_name(f"{base.name}_{n}")
        if not candidate.exists():
            return candidate
        n += 1


def _unique_filepath(dest: Path) -> Path:
    """Return *dest* if it does not exist, otherwise append (2), (3), etc."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _human_size(nbytes: int) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def create_event_output(
    event_name: str,
    matched: list[dict],
    unmatched: list[dict],
    output_dir: str = "output",
    use_symlinks: bool = False,
) -> str:
    """Create an event output folder with music files and reports.

    Parameters
    ----------
    event_name:
        Human-readable event name used as folder name.
    matched:
        List of dicts with keys: spotify_title, spotify_artist,
        matched_title, matched_artist, path, score.
    unmatched:
        List of dicts with keys: spotify_title, spotify_artist.
    output_dir:
        Parent directory for event folders.
    use_symlinks:
        Create symbolic links instead of copying files.

    Returns
    -------
    str
        Absolute path to the created event folder.
    """
    base = Path(output_dir) / event_name
    event_folder = _unique_folder(base)
    event_folder.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Copy / symlink matched files
    # ------------------------------------------------------------------
    m3u_entries: list[str] = []
    report_rows: list[dict] = []
    total_size = 0
    copied_count = 0

    for track in matched:
        source = Path(track["path"])
        if not source.exists():
            report_rows.append(
                {
                    "Spotify Title": track["spotify_title"],
                    "Spotify Artist": track["spotify_artist"],
                    "Matched Title": track["matched_title"],
                    "Matched Artist": track["matched_artist"],
                    "Score": track["score"],
                    "File Path": str(source),
                    "Status": "source missing",
                }
            )
            continue

        clean_name = _sanitize_filename(
            f"{track['matched_artist']} - {track['matched_title']}{source.suffix}"
        )
        dest = _unique_filepath(event_folder / clean_name)

        if use_symlinks:
            os.symlink(source.resolve(), dest)
        else:
            shutil.copy2(source, dest)

        file_size = dest.stat().st_size
        total_size += file_size
        copied_count += 1

        # M3U entry — use relative path so the folder is self-contained
        duration = -1  # duration unknown
        m3u_entries.append(
            f"#EXTINF:{duration},{track['matched_artist']} - {track['matched_title']}\n"
            f"{dest.name}"
        )

        report_rows.append(
            {
                "Spotify Title": track["spotify_title"],
                "Spotify Artist": track["spotify_artist"],
                "Matched Title": track["matched_title"],
                "Matched Artist": track["matched_artist"],
                "Score": track["score"],
                "File Path": dest.name,
                "Status": "ok",
            }
        )

    # ------------------------------------------------------------------
    # playlist.m3u
    # ------------------------------------------------------------------
    playlist_path = event_folder / "playlist.m3u"
    playlist_path.write_text(
        "#EXTM3U\n" + "\n".join(m3u_entries) + "\n",
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # unmatched.txt
    # ------------------------------------------------------------------
    unmatched_path = event_folder / "unmatched.txt"
    lines = [f"Unmatched tracks ({len(unmatched)})\n"]
    lines.append("-" * 40 + "\n")
    for t in unmatched:
        lines.append(f"{t['spotify_artist']} - {t['spotify_title']}\n")
    unmatched_path.write_text("".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # match_report.csv
    # ------------------------------------------------------------------
    # Add unmatched entries to the report
    for t in unmatched:
        report_rows.append(
            {
                "Spotify Title": t["spotify_title"],
                "Spotify Artist": t["spotify_artist"],
                "Matched Title": "",
                "Matched Artist": "",
                "Score": "",
                "File Path": "",
                "Status": "unmatched",
            }
        )

    report_path = event_folder / "match_report.csv"
    fieldnames = [
        "Spotify Title",
        "Spotify Artist",
        "Matched Title",
        "Matched Artist",
        "Score",
        "File Path",
        "Status",
    ]
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    action = "linked" if use_symlinks else "copied"
    print(f"\nOutput folder: {event_folder}/")
    print(f"  {copied_count} music files {action} ({_human_size(total_size)})")
    print(f"  playlist.m3u")
    print(f"  unmatched.txt ({len(unmatched)} tracks)")
    print(f"  match_report.csv")

    return str(event_folder.resolve())
