"""Interactive prompt for resolving duplicate library matches."""


def resolve_duplicates(matched: list[dict]) -> list[dict]:
    """Resolve matched tracks that have multiple candidates.

    For tracks with a single candidate, auto-accepts.
    For tracks with multiple candidates, prompts the user to choose.

    Takes matched entries with 'candidates' lists (from match_tracks collect_all=True)
    and returns flat matched entries (same format as default match_tracks output).
    """
    resolved = []

    for entry in matched:
        candidates = entry["candidates"]

        if len(candidates) == 1:
            chosen = candidates[0]
        else:
            chosen = _prompt_choice(entry, candidates)

        result = {
            "spotify_title": entry["spotify_title"],
            "spotify_artist": entry["spotify_artist"],
            "matched_title": chosen["matched_title"],
            "matched_artist": chosen["matched_artist"],
            "score": chosen["score"],
        }
        if "path" in chosen:
            result["path"] = chosen["path"]
        if "key" in chosen:
            result["key"] = chosen["key"]
        resolved.append(result)

    return resolved


def _prompt_choice(entry: dict, candidates: list[dict]) -> dict:
    """Display candidates and prompt user to pick one."""
    print(f"\nMultiple matches for \"{entry['spotify_title']}\" by {entry['spotify_artist']}:\n")

    for i, c in enumerate(candidates, 1):
        date = c.get("date_added") or "N/A"
        print(f"  {i}. {c['matched_title']} - {c['matched_artist']} (Added: {date}, Score: {c['score']:.1f})")

    raw = input(f"\nSelect [1-{len(candidates)}] (default: 1): ").strip()

    try:
        choice = int(raw)
        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]
    except ValueError:
        pass

    return candidates[0]
