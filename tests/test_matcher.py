from setlist_sync.matcher import match_tracks


def test_match_tracks_returns_single_best_by_default():
    """Default behavior: one best match per Spotify track."""
    spotify = [{"title": "Stronger", "artist": "Kanye West"}]
    library = [
        {"title": "Stronger", "artist": "Kanye West", "date_added": "2023-01-01",
         "norm_title": "stronger", "norm_artist": "kanye west"},
        {"title": "Stronger (Remastered)", "artist": "Kanye West", "date_added": "2024-06-15",
         "norm_title": "stronger", "norm_artist": "kanye west"},
    ]
    matched, unmatched = match_tracks(spotify, library, threshold=80)
    assert len(matched) == 1
    assert len(unmatched) == 0


def test_match_tracks_collect_all_returns_all_candidates():
    """With collect_all=True, returns all candidates above threshold."""
    spotify = [{"title": "Stronger", "artist": "Kanye West"}]
    library = [
        {"title": "Stronger", "artist": "Kanye West", "date_added": "2023-01-01",
         "norm_title": "stronger", "norm_artist": "kanye west"},
        {"title": "Stronger (Remastered)", "artist": "Kanye West", "date_added": "2024-06-15",
         "norm_title": "stronger", "norm_artist": "kanye west"},
        {"title": "Totally Different Song", "artist": "Other Artist", "date_added": "2022-01-01",
         "norm_title": "totally different song", "norm_artist": "other artist"},
    ]
    matched, unmatched = match_tracks(spotify, library, threshold=80, collect_all=True)
    assert len(matched) == 1  # Still one entry per Spotify track
    assert "candidates" in matched[0]
    assert len(matched[0]["candidates"]) == 2  # Two library tracks match
    assert matched[0]["candidates"][0]["score"] >= matched[0]["candidates"][1]["score"]  # Sorted desc


def test_match_tracks_collect_all_single_match_has_one_candidate():
    """With collect_all=True, unique matches still work."""
    spotify = [{"title": "Gold Digger", "artist": "Kanye West"}]
    library = [
        {"title": "Gold Digger", "artist": "Kanye West", "date_added": "2023-01-01",
         "norm_title": "gold digger", "norm_artist": "kanye west"},
    ]
    matched, unmatched = match_tracks(spotify, library, threshold=80, collect_all=True)
    assert len(matched) == 1
    assert len(matched[0]["candidates"]) == 1
