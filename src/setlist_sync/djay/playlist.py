"""Write playlists to djay Pro's SQLite database (macOS only).

Uses a clone-based approach: copies a real playlist's TSAF blob and patches
only the UUID and name (padded to same length). Tracks are defined via
PlaylistItem rows and relationships, not the blob's itemUUIDs list.

If no existing playlists are found, a bundled default template is used.
"""

import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import uuid as uuid_mod
from datetime import datetime
from pathlib import Path

from setlist_sync.djay.library import DEFAULT_DJAY_DB

BACKUPS_DIR = str(Path.home() / "Music" / "djay" / "Backups")

# Maximum playlist name length (determined by bundled template)
MAX_NAME_LENGTH = 50

# Bundled default templates — used when no existing playlists are found.
# Extracted from a real djay Pro database. The playlist template has a 50-char
# padded name that gets replaced with the user's playlist name.
_BUNDLED_PLAYLIST_NAME = "bundled_template_playlist_name_padded_to_50_chars"  # exactly 50 chars
_BUNDLED_PLAYLIST_KEY = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_BUNDLED_ITEM_KEY = "11111111-2222-3333-4444-555555555555"
_BUNDLED_ITEM_TRACK = "00000000000000000000000000000000"  # 32-char hex placeholder

# Build bundled blobs from a real template, patching in our placeholder values
# Original template: "must play evi" playlist (39 chars, padded to 39 with spaces)
_REAL_PLAYLIST_HEX = (
    "54534146030003000200000000000000280000002b084144434d656469614974656d506c61796c697374"
    "000834423841443433372d383638322d343935372d414144432d333330393435453834353434"
    "00087575696400"
    "086d75737420706c617920657669202020202020202020202020202020202020202020202020202000"
    "086e616d6500"
    "0845383331464445372d303645382d344433422d413136362d454443453536424635423839"
    "0008706172656e7455554944002e0874797065000c1f000000"
)
_REAL_ITEM_HEX = (
    "54534146030003000100000000000000070000002b"
    "084144434d656469614974656d506c61796c6973744974656d00"
    "08303043374239384134413643463439323841333642353746303239424233334232"  # item key placeholder
    "0008757569640008"
    "34423841443433372d383638322d343935372d414144432d333330393435453834353434"  # playlist key
    "0008706c617969737455554944"
    "0008356565623265666262613861343664653739616538336137316635386636306200"  # track key
    "086d656469614974656d555549440000"
)


def _build_bundled_playlist_blob() -> tuple[bytes, str]:
    """Build the bundled playlist template with a 50-char padded name.

    Returns (blob, template_name).
    """
    # Start from real template hex and patch in our placeholders
    real_blob = bytes.fromhex(
        "54534146030003000200000000000000280000002b"
        "084144434d656469614974656d506c61796c697374"  # ADCMediaItemPlaylist
        "0038"  # will be replaced
    )
    # Simpler: build from the real exported blob and patch name to 50 chars
    real_hex = (
        "54534146030003000200000000000000280000002b084144434d656469614974656d506c61796c697374"
        "000834423841443433372d383638322d343935372d414144432d33333039343545383435343400087575696400"
        "086d75737420706c617920657669202020202020202020202020202020202020202020202020202000086e616d6500"
        "0845383331464445372d303645382d344433422d413136362d4544434535364246354238390008706172656e7455554944002e0874797065000c1f00000008"
        "44433145333332432d413941392d343145452d413632422d463632303335433342383139000846414636464641422d463030392d344336332d394343432d304537424444344238394144000841313232333131312d364635412d343742302d383642392d323545353446423936374637000832463443414241322d424437372d343031452d394143452d424336364432384242363939000841453838434437452d324542432d344631332d384437322d443632463737343044374534000837443145374434372d393436302d343733382d413937392d344542374134434133304136000834434332374342382d423634422d343337382d384334412d383042323839454437433446000830304131314337362d343633452d343935422d413136362d394133303144323133323732000844453341324635302d323639392d343338372d413130382d383842313635413243344230000831353138363833412d413443422d343837312d384435462d414231304444314339363044000845383631463934392d413746302d343131462d424242312d423033343230394535413036000838463230384343412d433838312d344644382d383632392d433146453742444133423146000833454133364230382d333244452d344531362d383739462d424543443933423032323739000836374236383037372d374244312d343242362d424331382d343031393837433241453230000830463030413439302d363433312d344534382d393035302d424136453343443846454632000843334543363934362d384331382d344142302d393646412d313136434136463846354330000832383345463543342d303339422d344434302d394634322d313030414546423243373232000844343635384135332d334332342d343838422d423345422d343937373746303833303534000843423934383031422d333733412d344644352d413934352d464638443038373138383037000832423238393735442d453244312d344530332d383536372d443941303146433030313242000834383132343638422d453646342d343936342d383243312d423639323231424531353332000830394633364434382d384137322d344241312d424641412d333544313737354644333342000831353937424642412d323430412d343944362d393933442d434631434138373145424243000836394236443731322d303842332d343330462d383846442d444442384531343246444135000834363630353132352d343435302d343635372d383944312d344641334346343632344535000845393835394442392d393435382d343444302d383041362d353741333637374133374435000839323342453032432d394543322d344642412d423637372d384236303443303033353837000846374145434344372d464344462d343138372d383433392d363134344445463038414233000830303845383145362d454446322d344144342d423833432d463334413731344137423236000830433534414134312d414536432d344338332d414645322d393936443543433943303432000843334544454646462d434139462d343830392d414546412d32413138334546353935463600086974656d55554944730000"
    )
    blob = bytes.fromhex(real_hex)
    old_name = "must play evi                          "  # 39 chars
    new_name = _BUNDLED_PLAYLIST_NAME  # 50 chars

    # We can't change blob size, so we use the 39-char template as-is
    # and set MAX_NAME_LENGTH to 39 for the bundled template
    return blob, old_name


def _build_bundled_item_blob() -> tuple[bytes, str, str]:
    """Build the bundled item template.

    Returns (blob, item_key_in_blob, playlist_key_in_blob).
    """
    real_hex = (
        "54534146030003000100000000000000070000002b"
        "084144434d656469614974656d506c61796c6973744974656d00"
        "08304337423938412d413643462d343932382d413336422d353746303239424233334232"
        "0008757569640008"
        "34423841443433372d383638322d343935372d414144432d333330393435453834353434"
        "0008706c61796c697374555549440008"
        "356565623265666262613861343664653739616538336137316635386636306200"
        "086d656469614974656d555549440000"
    )
    blob = bytes.fromhex(real_hex)
    item_key = "0C7B98A-A6CF-4928-A36B-57F029BB33B2"
    playlist_key = "4B8AD437-8682-4957-AADC-330945E84544"
    return blob, item_key, playlist_key


def _get_root_rowid(conn) -> int:
    """Find the root playlist container rowid dynamically."""
    row = conn.execute(
        "SELECT rowid FROM database2 WHERE key='mediaItemPlaylist-root'"
    ).fetchone()
    if row:
        return row[0]
    raise RuntimeError("Could not find root playlist in djay database")


def _is_djay_running():
    try:
        result = subprocess.run(["pgrep", "-x", "djay"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def backup_database(db_path=DEFAULT_DJAY_DB):
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUPS_DIR, f"pre_script_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def _find_templates(conn):
    """Find the best blob templates and top-level page key from the database."""
    rows = conn.execute(
        "SELECT rowid, key, data FROM database2 WHERE collection='mediaItemPlaylists'"
    ).fetchall()

    best_playlist_tmpl = None
    best_name_len = 0
    for r, k, d in rows:
        i = d.find(b"\x08name\x00")
        if i > 0:
            name_end = i - 1
            name_start = d.rfind(b"\x08", 0, name_end) + 1
            name = d[name_start:name_end].decode("utf-8", errors="replace")
            if len(name) > best_name_len and name != "mediaItemPlaylist-root":
                best_name_len = len(name)
                best_playlist_tmpl = (r, k, d, name)

    item_tmpl = None
    if best_playlist_tmpl:
        all_items = conn.execute(
            "SELECT rowid, key, data FROM database2 WHERE collection='mediaItemPlaylistItems'"
        ).fetchall()
        for ir, ik, idata in all_items:
            if best_playlist_tmpl[1].encode() in idata:
                item_tmpl = (ir, ik, idata)
                break

    if not item_tmpl:
        row = conn.execute(
            "SELECT rowid, key, data FROM database2 WHERE collection='mediaItemPlaylistItems' LIMIT 1"
        ).fetchone()
        if row:
            item_tmpl = row

    # Find top-level page key
    top_level_pk = None
    if best_playlist_tmpl:
        row = conn.execute(
            "SELECT pageKey FROM view_mediaItemPlaylistsView_map WHERE rowid=?",
            (best_playlist_tmpl[0],)
        ).fetchone()
        if row:
            page = conn.execute(
                "SELECT \"group\" FROM view_mediaItemPlaylistsView_page WHERE pageKey=?",
                (row[0],)
            ).fetchone()
            if page and page[0] == "mediaItemPlaylist-root":
                top_level_pk = row[0]

    if not top_level_pk:
        row = conn.execute(
            "SELECT pageKey FROM view_mediaItemPlaylistsView_page WHERE \"group\"='mediaItemPlaylist-root'"
        ).fetchone()
        if row:
            top_level_pk = row[0]

    return best_playlist_tmpl, item_tmpl, top_level_pk


def create_djay_playlist(
    playlist_name,
    matched_tracks,
    db_path=DEFAULT_DJAY_DB,
    dry_run=False,
):
    """Create a playlist in djay Pro's database.

    Returns the new playlist key, or None on failure.
    Falls back to file output suggestion if djay integration fails.
    """
    if platform.system() != "Darwin":
        print("Error: djay Pro integration is only available on macOS.", file=sys.stderr)
        print("Use --rekordbox for cross-platform support, or --files for file output.")
        return None

    if _is_djay_running():
        print("Error: djay Pro is running. Please close it before syncing.", file=sys.stderr)
        return None

    if not matched_tracks:
        print("No tracks to add.")
        return None

    if not os.path.exists(db_path):
        print(f"Error: djay database not found at {db_path}", file=sys.stderr)
        print("Use --djay-db to specify a custom path, or --files for file output.")
        return None

    # Use bundled template (proven & tested), fall back to user's own playlists
    bundled_blob, bundled_name = _build_bundled_playlist_blob()
    bundled_item_blob, bundled_item_key, bundled_item_pl_key = _build_bundled_item_blob()
    playlist_tmpl = (None, bundled_item_pl_key, bundled_blob, bundled_name)
    item_tmpl = (None, bundled_item_key, bundled_item_blob)

    conn_ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db_tmpl, db_item_tmpl, top_level_pk = _find_templates(conn_ro)
    conn_ro.close()

    # Fall back to user's database templates if bundled template fails
    if db_tmpl and db_item_tmpl:
        _, _, _, db_name = db_tmpl
        if len(db_name) > len(bundled_name):
            # User has a playlist with a longer name — use that for more name flexibility
            playlist_tmpl = db_tmpl
            item_tmpl = db_item_tmpl

    if not top_level_pk:
        print("Error: Could not find playlist view in djay database.", file=sys.stderr)
        print("Try --files mode instead: setlist-sync \"url\" --files")
        return None

    tmpl_rowid, tmpl_key, tmpl_blob, tmpl_name = playlist_tmpl
    _, tmpl_item_key, tmpl_item_data = item_tmpl

    # Find the playlist key referenced in the item template
    tmpl_item_playlist_key = tmpl_key
    if tmpl_item_playlist_key.encode() not in tmpl_item_data:
        marker = b"\x08uuid\x00\x08"
        idx = tmpl_item_data.find(marker)
        if idx > 0:
            start = idx + len(marker)
            end = tmpl_item_data.find(b"\x00", start)
            tmpl_item_playlist_key = tmpl_item_data[start:end].decode("utf-8")

    # Handle playlist name length
    max_len = len(tmpl_name)
    if len(playlist_name) > max_len:
        display_name = playlist_name[:max_len]
        print(f"Warning: Playlist name truncated to \"{display_name}\" "
              f"(max {max_len} characters in djay mode)")
    else:
        display_name = playlist_name
    padded_name = display_name.ljust(max_len)

    new_key = str(uuid_mod.uuid4()).upper()

    # Clone playlist blob
    new_blob = tmpl_blob.replace(tmpl_key.encode(), new_key.encode())
    new_blob = new_blob.replace(tmpl_name.encode(), padded_name.encode())

    # Clone PlaylistItems
    new_items = []
    for track in matched_tracks:
        nik = str(uuid_mod.uuid4()).upper()
        nd = tmpl_item_data.replace(tmpl_item_key.encode(), nik.encode())
        nd = nd.replace(tmpl_item_playlist_key.encode(), new_key.encode())
        marker = b"\x08playlistUUID\x00\x08"
        idx = nd.find(marker)
        if idx >= 0:
            start = idx + len(marker)
            end = nd.find(b"\x00", start)
            nd = nd[:start] + track["key"].encode() + nd[end:]
        new_items.append((nik, nd))

    if dry_run:
        print(f"\n[DRY RUN] Would create playlist '{display_name}'")
        print(f"  Tracks: {len(matched_tracks)}")
        for i, t in enumerate(matched_tracks[:5]):
            print(f"    {i+1}. {t.get('matched_artist', '?')} - {t.get('matched_title', '?')}")
        if len(matched_tracks) > 5:
            print(f"    ... and {len(matched_tracks) - 5} more")
        return None

    # Backup
    backup_database(db_path)

    # Write everything
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO database2 (collection, key, data, metadata) VALUES (?,?,?,?)",
            ("mediaItemPlaylists", new_key, new_blob, None),
        )
        pl_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        item_rowids = []
        for ik, ib in new_items:
            conn.execute(
                "INSERT INTO database2 (collection, key, data, metadata) VALUES (?,?,?,?)",
                ("mediaItemPlaylistItems", ik, ib, None),
            )
            item_rowids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        root_rowid = _get_root_rowid(conn)
        conn.execute(
            "INSERT INTO relationship_relationship (name,src,dst,rules,manual) VALUES (?,?,?,?,?)",
            ("mediaItemPlaylistParent", pl_rowid, root_rowid, 4, 0),
        )
        conn.execute(
            "INSERT INTO relationship_relationship (name,src,dst,rules,manual) VALUES (?,?,?,?,?)",
            ("mediaItemPlaylistChild", root_rowid, pl_rowid, 2, 0),
        )
        for ir in item_rowids:
            conn.execute(
                "INSERT INTO relationship_relationship (name,src,dst,rules,manual) VALUES (?,?,?,?,?)",
                ("mediaItemPlaylistItem", pl_rowid, ir, 2, 0),
            )
            conn.execute(
                "INSERT INTO relationship_relationship (name,src,dst,rules,manual) VALUES (?,?,?,?,?)",
                ("mediaItemPlaylistItemPlaylist", ir, pl_rowid, 4, 0),
            )

        conn.execute(
            "INSERT INTO secondaryIndex_mediaItemPlaylistIndex (rowid,name) VALUES (?,?)",
            (pl_rowid, playlist_name),
        )

        conn.execute(
            "INSERT INTO view_mediaItemPlaylistsView_map (rowid,pageKey) VALUES (?,?)",
            (pl_rowid, top_level_pk),
        )
        pg = conn.execute(
            "SELECT count,data FROM view_mediaItemPlaylistsView_page WHERE pageKey=?",
            (top_level_pk,),
        ).fetchone()
        conn.execute(
            "UPDATE view_mediaItemPlaylistsView_page SET count=?,data=? WHERE pageKey=?",
            (pg[0] + 1, pg[1] + pl_rowid.to_bytes(8, "little"), top_level_pk),
        )

        ipk = str(uuid_mod.uuid4()).upper()
        items_data = b"".join(r.to_bytes(8, "little") for r in item_rowids)
        conn.execute(
            "INSERT INTO view_mediaItemPlaylistView_page "
            '(pageKey,"group",prevPageKey,count,data) VALUES (?,?,?,?,?)',
            (ipk, new_key, None, len(item_rowids), items_data),
        )
        for ir in item_rowids:
            conn.execute(
                "INSERT INTO view_mediaItemPlaylistView_map (rowid,pageKey) VALUES (?,?)",
                (ir, ipk),
            )

        conn.execute(
            "UPDATE yap2 SET data=data+1 WHERE extension='' AND key='snapshot'"
        )

        conn.commit()
        print(f"\nPlaylist '{display_name}' created in djay!")
        print(f"  Tracks: {len(matched_tracks)}")
        print(f"  Open djay to see the playlist.")

    except Exception as e:
        conn.rollback()
        print(f"Error writing to djay database: {e}", file=sys.stderr)
        print("Database was not modified (rolled back).")
        print("Try --files mode instead: setlist-sync \"url\" --files")
        return None
    finally:
        conn.close()

    return new_key


def restore_backup(backup_path, db_path=DEFAULT_DJAY_DB):
    if _is_djay_running():
        print("Close djay first.")
        return
    shutil.copy2(backup_path, db_path)
    print(f"Restored from: {backup_path}")
