from unittest.mock import patch

from setlist_sync.duplicate_prompt import resolve_duplicates


def _make_match(title, artist, date_added, score, n_candidates):
    """Helper to build a matched entry with candidates."""
    candidates = []
    for i in range(n_candidates):
        candidates.append({
            "matched_title": f"{title} v{i+1}" if i > 0 else title,
            "matched_artist": artist,
            "date_added": date_added,
            "score": score - i,
        })
    return {
        "spotify_title": title,
        "spotify_artist": artist,
        "candidates": candidates,
    }


def test_auto_accepts_single_candidate():
    """Tracks with exactly one candidate are resolved without prompting."""
    matched = [_make_match("Gold Digger", "Kanye West", "2023-01-01", 95, 1)]
    result = resolve_duplicates(matched)
    assert len(result) == 1
    assert result[0]["matched_title"] == "Gold Digger"
    assert "candidates" not in result[0]


@patch("builtins.input", return_value="2")
def test_prompts_for_multiple_candidates(mock_input):
    """User selects second candidate from the list."""
    matched = [_make_match("Stronger", "Kanye West", "2023-01-01", 95, 3)]
    result = resolve_duplicates(matched)
    assert len(result) == 1
    assert result[0]["matched_title"] == "Stronger v2"


@patch("builtins.input", return_value="")
def test_empty_input_selects_first(mock_input):
    """Pressing enter without input selects the first (highest-scored) candidate."""
    matched = [_make_match("Stronger", "Kanye West", "2023-01-01", 95, 2)]
    result = resolve_duplicates(matched)
    assert result[0]["matched_title"] == "Stronger"


@patch("builtins.input", return_value="invalid")
def test_invalid_input_selects_first(mock_input):
    """Invalid input falls back to the first candidate."""
    matched = [_make_match("Stronger", "Kanye West", "2023-01-01", 95, 2)]
    result = resolve_duplicates(matched)
    assert result[0]["matched_title"] == "Stronger"
