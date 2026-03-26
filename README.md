<p align="center">
  <img src="https://raw.githubusercontent.com/mathiassp/setlist-sync/main/logo.jpg" alt="setlist-sync" width="200">
</p>

<h1 align="center">setlist-sync</h1>

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
</p>

<p align="center">
  Match streaming playlists against your local DJ library and create playlists in your DJ software — with cues, loops, and all metadata intact.
</p>

## The Problem

You're a DJ. A client sends you a Spotify playlist with 50 song requests for their event. You need to:
1. Figure out which songs you already have
2. Find them in your library across thousands of tracks
3. Create a playlist in your DJ software
4. Download only the songs you're missing

Without this tool, you'd manually search each song, accidentally download duplicates, and lose your carefully set cue points and loops on re-downloaded tracks.

## The Solution

```bash
setlist-sync "https://open.spotify.com/playlist/..." --playlist-name "Wedding Jan & An"
```

In under a second, setlist-sync:
- Fetches the playlist from Spotify (no API key or Premium needed)
- Fuzzy-matches every track against your DJ library (4800+ tracks in 0.4s)
- Creates a playlist in your DJ software with your existing tracks — cues, loops, BPM, and all metadata preserved
- Reports which tracks you're missing so you only download what you need

```
Loaded library: 4820 tracks
Matching complete: 43/50 tracks found in library
Matched in 0.4s

Done! 43/50 tracks matched, 7 unmatched.

Unmatched tracks:
  - Rick Astley - Never Gonna Give You Up
  - Darude - Sandstorm
```

## Features

- **Spotify URL input** — paste any public playlist link, no API key required
- **CSV input** — also accepts CSV files (e.g. from Exportify)
- **Fuzzy matching** — handles spelling differences, remix tags, featured artists, etc.
- **DJ software integration** — writes playlists directly to djay Pro and Rekordbox
- **File-based output** — alternatively copies matched files to an event folder with M3U playlist
- **Smart normalization** — strips `(feat. ...)`, `(Remastered)`, `- Radio Edit` etc. before matching
- **Fast** — matches 50 tracks against 5000 in under a second using rapidfuzz

## Installation

```bash
pip install setlist-sync
```

Requires Python 3.10+.

### Windows

Python is not pre-installed on Windows. To install it:

1. Open a terminal and run `winget install Python.Python.3.13`
   (or download from [python.org](https://www.python.org/downloads/))
2. **Important:** During install, check "Add Python to PATH"
3. Restart your terminal, then run `pip install setlist-sync`

If `setlist-sync` is not recognized as a command, use:
```powershell
python -m setlist_sync init
python -m setlist_sync "https://open.spotify.com/playlist/..."
```

### Development install

```bash
git clone https://github.com/mathiassp/setlist-sync.git
cd setlist-sync
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Usage

### First-time setup

```bash
setlist-sync init
```

This walks you through choosing your DJ software (djay Pro or Rekordbox), finding your database, and setting preferences. Configuration is saved to `.env`.

### Sync a playlist

```bash
setlist-sync "https://open.spotify.com/playlist/..."
```

That's it. setlist-sync reads your DJ software from `.env` and creates the playlist directly in its database.

> [!WARNING]
> Close your DJ software before running — setlist-sync writes directly to the database.

### Custom playlist name

```bash
setlist-sync "https://open.spotify.com/playlist/..." --playlist-name "Wedding Jan & An"
```

### Rekordbox mode

If your `.env` is set to Rekordbox, it works automatically. Or override with a flag:

```bash
setlist-sync "https://open.spotify.com/playlist/..." --rekordbox
```

### File output mode

Copies matched files to an output folder with an M3U playlist.

```bash
setlist-sync "https://open.spotify.com/playlist/..." --files
```

### CSV input

```bash
setlist-sync playlist.csv --playlist-name "Birthday Party"
```

> [!TIP]
> Use `--dry-run` to preview matches without writing anything.

### Options

| Flag | Description |
|------|-------------|
| `--playlist-name` | Name for the created playlist (default: Spotify playlist name) |
| `--rekordbox [XML]` | Use Rekordbox instead of djay. Without path: reads database directly. With path: uses XML file |
| `--files` | Copy matched files to an output folder with M3U playlist |
| `--threshold` | Match sensitivity 0-100 (default: 85) |
| `--dry-run` | Show what would happen without writing |
| `--handle-duplicates` | Interactively choose between multiple library matches per track |
| `--djay-db PATH` | Custom path to djay Pro database (default: `~/Music/djay/djay Media Library.djayMediaLibrary/MediaLibrary.db`) |
| `--rekordbox-output` | Output path for Rekordbox XML mode (default: `{input}_synced.xml`) |
| `--music-dir` | Music folder path for `--files` mode (default: `~/Music`) |
| `--symlink` | Use symlinks instead of copies in `--files` mode |

## How It Works

```
Spotify URL / CSV ─→ spotify_client ─→ Track list (title + artist)
                                              │
                ┌─────────────────────────────┤
                │              │              │
  djay database │  Rekordbox   │  ~/Music     │
  (macOS only)  │  database    │  folder      │
  djay/library  │  rekordbox/  │  library_    │
                │  library     │  scanner     │
                └──────┬───────┘              │
                       │                      │
                  matcher (fuzzy match) ◄─────┘
                       │
          ┌────────────┼──────────────┐
          │            │              │
    djay/playlist  rekordbox/     output
    (djay Pro DB)  playlist       ├── playlist.m3u
                   (DB or XML)    ├── unmatched.txt
                                  └── match_report.csv
```

### Matching

Uses [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) for fuzzy string matching with weighted scoring:
- **Title similarity**: 60% weight
- **Artist similarity**: 40% weight
- Normalizes strings before matching: strips remix/edit tags, featured artists, punctuation

### DJ Software Integration

Writes directly to your DJ software's database. For djay Pro, this uses a clone-based approach to handle the proprietary TSAF format. For Rekordbox, it uses pyrekordbox to access the encrypted database. A backup is automatically created before every write.

## Supported DJ Software

| Software | Versions | Platform | Read Library | Write Playlists | Status |
|----------|----------|----------|:------------:|:---------------:|--------|
| **djay Pro** | 5.x | macOS | Yes | Yes | Supported |
| **Rekordbox** | 6.x / 7.x | macOS, Windows | Yes | Yes | Supported |
| **Serato DJ** | — | — | — | — | Coming soon |
| **Traktor** | — | — | — | — | Coming soon |

> **Note:** setlist-sync was developed and tested with djay Pro 5 and Rekordbox 7. Older versions may work but have not been tested. If you try it with a different version, please [open an issue](https://github.com/mathiassp/setlist-sync/issues) and let us know how it went!

## Supported Input Sources

- **Spotify** — public playlist URLs (no account needed)
- **CSV** — any CSV with track name and artist columns

### Planned
- Tidal
- Apple Music
- YouTube Music

## Limitations

- **djay playlist names** are limited to ~40 characters (depends on your longest existing playlist name). Names that exceed the limit are truncated with a warning.
- Your DJ software must be **closed** when writing playlists
- djay Pro integration is **macOS only**; Rekordbox works on macOS and Windows
- Matching accuracy depends on how tracks are tagged in your library
- djay integration uses a reverse-engineered database format — a backup is automatically created before every write

## Contributing

Issues and PRs welcome. If you use different DJ software and want to add support, open an issue to discuss the approach.

## License

MIT

---

If this saved you time, consider giving it a star.
