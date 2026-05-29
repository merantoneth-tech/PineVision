"""
Network utilities — detect local IPv4 addresses for MediaMTX RTMP publishing.
"""

import socket
import logging
from typing import List

logger    = logging.getLogger(__name__)
_FALLBACK = '192.168.1.5'


def get_local_ipv4() -> str:
    """
    Return the IPv4 address the OS would route through to reach an external
    host.  Uses a UDP connect (no packets are actually sent) to let the
    kernel select the correct outbound interface.

    Falls back to _FALLBACK if detection fails for any reason.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        logger.info('IPv4 detection: found %s', ip)
        return ip
    except Exception as exc:
        logger.warning('IPv4 detection failed (%s); using fallback %s', exc, _FALLBACK)
        return _FALLBACK


def get_all_local_ipv4s() -> List[str]:
    """
    Return all non-loopback IPv4 addresses on this machine.

    DJI Fly connects from a different device (phone/tablet), which may be on
    a different network interface than the one get_local_ipv4() selects.
    Common cases:
      - WiFi adapter  → internet (get_local_ipv4 picks this)
      - USB tethering → DJI controller device (192.168.x.x / 172.x.x.x)
      - Hotspot       → DJI controller device (192.168.137.x on Windows)

    Returning all IPs lets the frontend warn the user if multiple are present,
    so they can verify which one the DJI controller can reach.
    """
    seen: set = set()
    result: List[str] = []

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.') and ip not in seen:
                seen.add(ip)
                result.append(ip)
    except Exception as exc:
        logger.warning('All-IP enumeration failed (%s)', exc)

    # Also run the outbound-interface check to catch IPs getaddrinfo misses
    primary = get_local_ipv4()
    if primary not in seen and not primary.startswith('127.'):
        result.insert(0, primary)

    if not result:
        result.append(_FALLBACK)

    logger.info('All local IPv4s: %s', result)
    return result
