"""Port specification parsing and built-in presets."""

from __future__ import annotations

import re

MAX_PORT = 65535
ALL_PORTS = list(range(1, MAX_PORT + 1))

_TOKEN_SPLIT = re.compile(r"[,\s]+")

# A pragmatic "top 100" list, useful for quick scans.
COMMON_PORTS = [
    7, 9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 88, 106, 110, 111, 113,
    119, 135, 139, 143, 144, 179, 199, 389, 427, 443, 444, 445, 465, 513, 514,
    515, 543, 544, 548, 554, 587, 631, 646, 873, 990, 993, 995, 1025, 1026,
    1027, 1028, 1029, 1110, 1433, 1720, 1723, 1755, 1900, 2000, 2001, 2049,
    2121, 2717, 3000, 3128, 3306, 3389, 3986, 4899, 5000, 5009, 5051, 5060,
    5101, 5190, 5357, 5432, 5631, 5666, 5800, 5900, 6000, 6001, 6646, 7070,
    8000, 8008, 8009, 8080, 8081, 8443, 8888, 9100, 9999, 10000, 32768, 49152,
    49153, 49154, 49155, 49156, 49157,
]

WEB_PORTS = [80, 443, 8080, 8443, 8000, 8888]

PRESETS: dict[str, list[int] | None] = {
    "Custom": None,
    "Common ports (top 100)": COMMON_PORTS,
    "Web servers": WEB_PORTS,
    "Well-known (1-1023)": list(range(1, 1024)),
    "All ports (1-65535)": ALL_PORTS,
}

_KEYWORDS = {
    "all": ALL_PORTS,
    "*": ALL_PORTS,
    "common": COMMON_PORTS,
    "top100": COMMON_PORTS,
    "web": WEB_PORTS,
    "well-known": list(range(1, 1024)),
    "wellknown": list(range(1, 1024)),
    "well_known": list(range(1, 1024)),
}


class PortError(ValueError):
    """Raised when a port specification is invalid."""


def parse_ports(spec: str, *, all_ports: bool = False) -> list[int]:
    """Parse ``22,80,443``, ``1-1024`` or keywords such as ``common``/``all``.

    The result is sorted and free of duplicates.
    """
    if all_ports:
        return list(ALL_PORTS)

    text = spec.strip().lower()
    if not text:
        raise PortError("Enter ports to scan, or select 'All ports'.")

    if text in _KEYWORDS:
        return list(_KEYWORDS[text])

    ports: set[int] = set()
    for token in (part for part in _TOKEN_SPLIT.split(text) if part):
        if "-" in token:
            pieces = token.split("-")
            if len(pieces) != 2 or not all(piece.isdigit() for piece in pieces):
                raise PortError(f"Invalid port range '{token}'.")
            start, end = (int(piece) for piece in pieces)
            if start > end:
                raise PortError(f"Port range '{token}' ends before it starts.")
            if start < 1 or end > MAX_PORT:
                raise PortError(f"Port range '{token}' must stay within 1-{MAX_PORT}.")
            ports.update(range(start, end + 1))
            continue

        if not token.isdigit():
            raise PortError(f"Invalid port '{token}'.")
        port = int(token)
        if not 1 <= port <= MAX_PORT:
            raise PortError(f"Port {port} is outside the valid range 1-{MAX_PORT}.")
        ports.add(port)

    if not ports:
        raise PortError("No valid ports were specified.")
    return sorted(ports)
