"""Write playlists to djay Pro's SQLite database.

Uses a clone-based approach: copies a real playlist's TSAF blob and patches
only the UUID and name (padded to same length). Tracks are defined via
PlaylistItem rows and relationships, not the blob's itemUUIDs list.
"""

import os
import shutil
import sqlite3
import subprocess
import uuid as uuid_mod
from datetime import datetime
from pathlib import Path

from setlist_sync.djay.library import DEFAULT_DJAY_DB

BACKUPS_DIR = str(Path.home() / "Music" / "djay" / "Backups")


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
    """Find the best blob templates and top-level page key."""
    rows = conn.execute(
        "SELECT rowid, key, data FROM database2 WHERE collection='mediaItemPlaylists'"
    ).fetchall()

    # Find template with longest name for playlist blob
    best_playlist_tmpl = None
    best_name_len = 0
    for r, k, d in rows:
        # Extract name from blob
        i = d.find(b"\x08name\x00")
        if i > 0:
            # Name value is the field before \x08name\x00
            name_end = i - 1  # the \x00 before \x08name
            name_start = d.rfind(b"\x08", 0, name_end) + 1
            name = d[name_start:name_end].decode("utf-8", errors="replace")
            if len(name) > best_name_len and name != "mediaItemPlaylist-root":
                best_name_len = len(name)
                best_playlist_tmpl = (r, k, d, name)

    # Find a PlaylistItem template from a known working playlist
    item_tmpl = None
    if best_playlist_tmpl:
        # Try to find items for this playlist
        all_items = conn.execute(
            "SELECT rowid, key, data FROM database2 WHERE collection='mediaItemPlaylistItems'"
        ).fetchall()
        for ir, ik, idata in all_items:
            if best_playlist_tmpl[1].encode() in idata:
                item_tmpl = (ir, ik, idata)
                break

    # If no item found for best template, use any item
    if not item_tmpl:
        item_tmpl = conn.execute(
            "SELECT rowid, key, data FROM database2 WHERE collection='mediaItemPlaylistItems' LIMIT 1"
        ).fetchone()

    # Find top-level page key
    # Look for a playlist with parentUUID = "mediaItemPlaylist-root" and get its page
    top_level_pk = None
    for r, k, d, name in [best_playlist_tmpl] if best_playlist_tmpl else []:
        row = conn.execute(
            "SELECT pageKey FROM view_mediaItemPlaylistsView_map WHERE rowid=?", (r,)
        ).fetchone()
        if row:
            # Verify this page is top-level
            page = conn.execute(
                "SELECT \"group\" FROM view_mediaItemPlaylistsView_page WHERE pageKey=?",
                (row[0],)
            ).fetchone()
            if page and page[0] == "mediaItemPlaylist-root":
                top_level_pk = row[0]

    # Fallback: find any page with group='mediaItemPlaylist-root'
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
    if _is_djay_running():
        print("WARNING: djay Pro is running. Close it first.")
        return None

    if not matched_tracks:
        print("No tracks to add.")
        return None

    # Read templates
    conn_ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    playlist_tmpl, item_tmpl, top_level_pk = _find_templates(conn_ro)
    conn_ro.close()

    if not playlist_tmpl or not item_tmpl or not top_level_pk:
        print("ERROR: Could not find templates in djay database.")
        return None

    tmpl_rowid, tmpl_key, tmpl_blob, tmpl_name = playlist_tmpl
    _, tmpl_item_key, tmpl_item_data = item_tmpl

    # Find the playlist key referenced in the item template
    tmpl_item_playlist_key = tmpl_key
    # Check if the item actually references a different playlist
    for r, k, d, n in [playlist_tmpl]:
        if k.encode() in tmpl_item_data:
            tmpl_item_playlist_key = k
            break
    # If not, find which playlist key is in the item
    if tmpl_item_playlist_key.encode() not in tmpl_item_data:
        # Extract playlist key from item blob
        marker = b"\x08uuid\x00\x08"
        idx = tmpl_item_data.find(marker)
        if idx > 0:
            start = idx + len(marker)
            end = tmpl_item_data.find(b"\x00", start)
            tmpl_item_playlist_key = tmpl_item_data[start:end].decode("utf-8")

    # Truncate or pad name to template length
    display_name = playlist_name[:len(tmpl_name)]
    padded_name = display_name.ljust(len(tmpl_name))

    new_key = str(uuid_mod.uuid4()).upper()

    # Clone playlist blob (only change UUID and name, keep exact same size)
    new_blob = tmpl_blob.replace(tmpl_key.encode(), new_key.encode())
    new_blob = new_blob.replace(tmpl_name.encode(), padded_name.encode())

    # Clone PlaylistItems for each track
    new_items = []
    for track in matched_tracks:
        nik = str(uuid_mod.uuid4()).upper()
        nd = tmpl_item_data.replace(tmpl_item_key.encode(), nik.encode())
        nd = nd.replace(tmpl_item_playlist_key.encode(), new_key.encode())
        # Replace track key (32-char hex after \x08playlistUUID\x00\x08)
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

    # Write everything in a single transaction
    conn = sqlite3.connect(db_path)
    try:
        # 1. Playlist blob
        conn.execute(
            "INSERT INTO database2 (collection, key, data, metadata) VALUES (?,?,?,?)",
            ("mediaItemPlaylists", new_key, new_blob, None),
        )
        pl_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 2. PlaylistItem blobs
        item_rowids = []
        for ik, ib in new_items:
            conn.execute(
                "INSERT INTO database2 (collection, key, data, metadata) VALUES (?,?,?,?)",
                ("mediaItemPlaylistItems", ik, ib, None),
            )
            item_rowids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        # 3. Relationships
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

        # 4. Secondary index
        conn.execute(
            "INSERT INTO secondaryIndex_mediaItemPlaylistIndex (rowid,name) VALUES (?,?)",
            (pl_rowid, playlist_name),
        )

        # 5. Playlists view (sidebar)
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

        # 6. Playlist items view
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

        # 7. Snapshot counter
        conn.execute(
            "UPDATE yap2 SET data=data+1 WHERE extension='' AND key='snapshot'"
        )

        conn.commit()
        print(f"\nPlaylist '{display_name}' created in djay!")
        print(f"  Tracks: {len(matched_tracks)}")
        print(f"  Open djay to see the playlist.")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()

    return new_key


def restore_backup(backup_path, db_path=DEFAULT_DJAY_DB):
    if _is_djay_running():
        print("Close djay first.")
        return
    shutil.copy2(backup_path, db_path)
    print(f"Restored from: {backup_path}")
