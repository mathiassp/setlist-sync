"""Check if a newer version of setlist-sync is available on PyPI."""

import json
import urllib.request

from setlist_sync import __version__


def check_for_update():
    """Print a message if a newer version is available. Silently does nothing on failure."""
    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/setlist-sync/json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            latest = data["info"]["version"]

        if latest != __version__:
            print(f"\n  Update available: {__version__} → {latest}")
            print(f"  Run: pip install --upgrade setlist-sync\n")
    except Exception:
        pass  # network error, timeout, etc. — don't bother the user
