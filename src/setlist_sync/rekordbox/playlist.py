"""Create playlists in Rekordbox's database or XML files."""

import os
import xml.etree.ElementTree as ET


def create_rekordbox_playlist(
    playlist_name: str,
    matched_tracks: list[dict],
    xml_path: str | None = None,
    output_path: str | None = None,
    dry_run: bool = False,
) -> str | None:
    """Create a playlist in Rekordbox.

    If xml_path is provided, creates the playlist in an XML file.
    Otherwise, writes directly to Rekordbox's database.
    """
    if not matched_tracks:
        print("No tracks to add.")
        return None

    if dry_run:
        print(f"\n[DRY RUN] Would create Rekordbox playlist '{playlist_name}'")
        print(f"  Tracks: {len(matched_tracks)}")
        for i, t in enumerate(matched_tracks[:5]):
            print(f"    {i+1}. {t.get('matched_artist', '?')} - {t.get('matched_title', '?')}")
        if len(matched_tracks) > 5:
            print(f"    ... and {len(matched_tracks) - 5} more")
        return None

    if xml_path:
        return _create_in_xml(playlist_name, matched_tracks, xml_path, output_path)
    return _create_in_database(playlist_name, matched_tracks)


def _create_in_database(playlist_name: str, matched_tracks: list[dict]) -> str:
    """Create a playlist directly in Rekordbox's database."""
    from pyrekordbox import Rekordbox6Database

    db = Rekordbox6Database()

    # Create the playlist
    playlist = db.create_playlist(name=playlist_name)

    # Add each matched track
    for track in matched_tracks:
        content_id = int(track["key"])
        db.add_to_playlist(playlist=playlist, content=content_id)

    db.commit()
    db.close()

    print(f"\nRekordbox playlist '{playlist_name}' created!")
    print(f"  Tracks: {len(matched_tracks)}")
    print(f"  Restart Rekordbox to see the playlist.")

    return playlist_name


def _create_in_xml(
    playlist_name: str,
    matched_tracks: list[dict],
    xml_path: str,
    output_path: str | None = None,
) -> str:
    """Add a playlist to a Rekordbox XML file."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    playlists_root = root.find(".//PLAYLISTS/NODE[@Name='ROOT']")
    if playlists_root is None:
        playlists_el = root.find("PLAYLISTS")
        if playlists_el is None:
            playlists_el = ET.SubElement(root, "PLAYLISTS")
        playlists_root = ET.SubElement(playlists_el, "NODE", {
            "Type": "0", "Name": "ROOT", "Count": "0",
        })

    playlist_node = ET.SubElement(playlists_root, "NODE", {
        "Name": playlist_name,
        "Type": "1",
        "KeyType": "0",
        "Entries": str(len(matched_tracks)),
    })

    for track in matched_tracks:
        ET.SubElement(playlist_node, "TRACK", {"Key": str(track["key"])})

    current_count = int(playlists_root.get("Count", "0"))
    playlists_root.set("Count", str(current_count + 1))

    if not output_path:
        base, ext = os.path.splitext(xml_path)
        output_path = f"{base}_synced{ext}"

    tree.write(output_path, encoding="UTF-8", xml_declaration=True)

    print(f"\nRekordbox playlist '{playlist_name}' created!")
    print(f"  Tracks: {len(matched_tracks)}")
    print(f"  Output: {output_path}")
    print(f"  Import into Rekordbox: File > Import Collection")

    return output_path
