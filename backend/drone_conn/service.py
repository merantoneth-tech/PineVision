"""
Stream connection service.
Validates RTMP URLs, queries MediaMTX, and constructs HLS playback URLs.
"""

import re
import requests
from . import mediamtx

_RTMP_RE = re.compile(r'^rtmp://([^:/]+)(?::(\d+))?/(.+)$')


def _parse_rtmp(url: str) -> dict | None:
    m = _RTMP_RE.match(url.strip())
    if not m:
        return None
    return {
        'host':        m.group(1),
        'port':        int(m.group(2)) if m.group(2) else 1935,
        'stream_path': m.group(3).rstrip('/').split('/')[-1],
    }


def connect(rtmp_url: str) -> dict:
    """
    Full connect workflow:
      1. Validate RTMP URL format.
      2. Confirm MediaMTX is reachable.
      3. Confirm stream path exists and has an active publisher.
      4. Return the HLS playback URL.

    Returns a dict with 'ok': True/False and relevant fields.
    """
    if not isinstance(rtmp_url, str) or not _RTMP_RE.match(rtmp_url.strip()):
        return {
            'ok':      False,
            'error':   'invalid_url',
            'message': 'Invalid RTMP URL. Expected format: rtmp://HOST[:PORT]/PATH',
        }

    parsed = _parse_rtmp(rtmp_url)
    if not parsed:
        return {'ok': False, 'error': 'invalid_url', 'message': 'Could not parse RTMP URL.'}

    try:
        path_info = mediamtx.get_path(parsed['stream_path'])
    except requests.ConnectionError:
        return {
            'ok':      False,
            'error':   'mediamtx_offline',
            'message': 'MediaMTX is not reachable. Ensure mediamtx.exe is running on port 9997.',
        }
    except requests.RequestException as exc:
        return {'ok': False, 'error': 'mediamtx_error', 'message': str(exc)}

    if path_info is None:
        return {
            'ok':      False,
            'error':   'path_not_found',
            'message': f'Path "{parsed["stream_path"]}" not found in MediaMTX.',
        }

    if not path_info.get('ready', False):
        return {
            'ok':      False,
            'error':   'stream_not_ready',
            'message': 'Drone is not streaming yet. Start the live stream in DJI Fly first.',
        }

    hls_url = f'http://{parsed["host"]}:8888/{parsed["stream_path"]}/index.m3u8'
    return {
        'ok':      True,
        'hls_url': hls_url,
        'path':    parsed['stream_path'],
        'host':    parsed['host'],
    }


def status(path_name: str) -> dict:
    """
    Check whether a stream path is currently active (publisher connected).
    Used by the frontend health-poll endpoint.
    """
    try:
        path_info = mediamtx.get_path(path_name)
    except requests.ConnectionError:
        return {'ok': False, 'error': 'mediamtx_offline', 'ready': False}
    except requests.RequestException as exc:
        return {'ok': False, 'error': 'mediamtx_error', 'ready': False, 'message': str(exc)}

    if path_info is None:
        return {'ok': True, 'ready': False, 'error': 'path_not_found'}

    source = path_info.get('source') or {}
    return {
        'ok':          True,
        'ready':       bool(path_info.get('ready', False)),
        'source_type': source.get('type'),
    }
