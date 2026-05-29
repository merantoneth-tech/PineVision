"""
MediaMTX process manager.

Ensures a single MediaMTX instance is running for the lifetime of the
Flask server.  If the control API is already reachable (e.g. MediaMTX
was started manually), we reuse it without spawning a duplicate process.
"""

import os
import subprocess
import threading
import time
import logging

import requests

logger = logging.getLogger(__name__)

_lock  = threading.Lock()
_proc  = None   # subprocess.Popen we launched, or None

_MEDIAMTX_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'mediamtx')
)
_MEDIAMTX_EXE = os.path.join(_MEDIAMTX_DIR, 'mediamtx.exe')
_MEDIAMTX_YML = os.path.join(_MEDIAMTX_DIR, 'mediamtx.yml')
_CONTROL_URL  = 'http://localhost:9997/v3/paths/list'
_STARTUP_SECS = 6   # max seconds to wait for API after launch


def _api_reachable() -> bool:
    """Return True if the MediaMTX control API responds with HTTP 200."""
    try:
        r = requests.get(_CONTROL_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def ensure_running() -> dict:
    """
    Ensure MediaMTX is running.

    * If the control API is already reachable, return immediately (no-op).
    * Otherwise launch mediamtx.exe and wait up to _STARTUP_SECS for it
      to become ready.

    Returns:
        {'ok': True,  'started': bool}                        on success
        {'ok': False, 'error': str, 'message': str}           on failure
    """
    global _proc

    with _lock:
        if _api_reachable():
            logger.info('MediaMTX: already running, reusing existing instance.')
            return {'ok': True, 'started': False}

        if not os.path.isfile(_MEDIAMTX_EXE):
            logger.error('MediaMTX executable not found: %s', _MEDIAMTX_EXE)
            return {
                'ok':      False,
                'error':   'mediamtx_not_found',
                'message': f'mediamtx.exe not found at: {_MEDIAMTX_EXE}',
            }

        logger.info('MediaMTX: launching from %s', _MEDIAMTX_DIR)
        try:
            _proc = subprocess.Popen(
                [_MEDIAMTX_EXE, _MEDIAMTX_YML],
                cwd=_MEDIAMTX_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            logger.error('MediaMTX: launch failed — %s', exc)
            return {
                'ok':      False,
                'error':   'launch_failed',
                'message': f'Failed to start mediamtx.exe: {exc}',
            }

        deadline = time.monotonic() + _STARTUP_SECS
        while time.monotonic() < deadline:
            if _api_reachable():
                logger.info('MediaMTX: ready (PID %d).', _proc.pid)
                return {'ok': True, 'started': True}
            time.sleep(0.4)

        # Timed out — kill the process we started
        _proc.kill()
        _proc = None
        logger.error('MediaMTX: did not become ready within %ds.', _STARTUP_SECS)
        return {
            'ok':      False,
            'error':   'startup_timeout',
            'message': (
                f'MediaMTX did not respond within {_STARTUP_SECS} seconds. '
                'Check mediamtx.yml configuration.'
            ),
        }


def stop() -> None:
    """Terminate the MediaMTX process if we started it (no-op otherwise)."""
    global _proc
    with _lock:
        if _proc is not None and _proc.poll() is None:
            _proc.terminate()
            logger.info('MediaMTX: process terminated.')
        _proc = None
