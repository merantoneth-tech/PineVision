"""
MediaMTX API client.
Queries the local MediaMTX control API (default :9997) to inspect stream paths.
"""

import requests

_BASE    = 'http://localhost:9997'
_TIMEOUT = 5  # seconds


def list_paths():
    """Return the full /v3/paths/list response dict from MediaMTX."""
    resp = requests.get(f'{_BASE}/v3/paths/list', timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_path(name: str) -> dict | None:
    """Return the path object for *name*, or None if not present."""
    data = list_paths()
    for item in data.get('items', []):
        if item.get('name') == name:
            return item
    return None
