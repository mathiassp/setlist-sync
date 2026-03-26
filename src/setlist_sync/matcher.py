from rapidfuzz.fuzz import token_sort_ratio

from setlist_sync.config import normalize_string, TITLE_WEIGHT, ARTIST_WEIGHT


def match_tracks(
    spotify_tracks: list[dict],
    library_tracks: list[dict],
    threshold: int = 85,
    collect_all: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Match Spotify tracks against local library tracks using fuzzy string matching.

    When collect_all is True, each matched entry includes a 'candidates' list
    with all library tracks scoring above the threshold, sorted by score descending.
    """
    matched = []
    unmatched = []
    total = len(spotify_tracks)

    for spotify_track in spotify_tracks:
        norm_title = normalize_string(spotify_track["title"])
        norm_artist = normalize_string(spotify_track["artist"])

        if collect_all:
            candidates = []
            for lib_track in library_tracks:
                score = (
                    token_sort_ratio(norm_title, lib_track["norm_title"]) * TITLE_WEIGHT
                    + token_sort_ratio(norm_artist, lib_track["norm_artist"]) * ARTIST_WEIGHT
                )
                if score >= threshold:
                    candidate = {
                        "matched_title": lib_track["title"],
                        "matched_artist": lib_track["artist"],
                        "date_added": lib_track.get("date_added", ""),
                        "score": score,
                    }
                    if "path" in lib_track:
                        candidate["path"] = lib_track["path"]
                    if "key" in lib_track:
                        candidate["key"] = lib_track["key"]
                    candidates.append(candidate)

            if candidates:
                candidates.sort(key=lambda c: c["score"], reverse=True)
                matched.append({
                    "spotify_title": spotify_track["title"],
                    "spotify_artist": spotify_track["artist"],
                    "candidates": candidates,
                })
            else:
                unmatched.append({
                    "spotify_title": spotify_track["title"],
                    "spotify_artist": spotify_track["artist"],
                })
        else:
            best_score = 0
            best_match = None

            for lib_track in library_tracks:
                score = (
                    token_sort_ratio(norm_title, lib_track["norm_title"]) * TITLE_WEIGHT
                    + token_sort_ratio(norm_artist, lib_track["norm_artist"]) * ARTIST_WEIGHT
                )

                if score > best_score:
                    best_score = score
                    best_match = lib_track

                if score == 100:
                    break

            if best_score >= threshold and best_match is not None:
                result = {
                    "spotify_title": spotify_track["title"],
                    "spotify_artist": spotify_track["artist"],
                    "matched_title": best_match["title"],
                    "matched_artist": best_match["artist"],
                    "score": best_score,
                }
                # Include path if available (file-based library)
                if "path" in best_match:
                    result["path"] = best_match["path"]
                # Include key if available (djay library)
                if "key" in best_match:
                    result["key"] = best_match["key"]
                matched.append(result)
            else:
                unmatched.append({
                    "spotify_title": spotify_track["title"],
                    "spotify_artist": spotify_track["artist"],
                })

    print(f"Matching complete: {len(matched)}/{total} tracks found in library")

    return matched, unmatched
