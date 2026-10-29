"""Turn user supplied target specifications into concrete IP addresses."""

from __future__ import annotations

import ipaddress
import re
import socket

MAX_HOSTS = 65536

_TOKEN_SPLIT = re.compile(r"[,\s]+")
_RANGE_RE = re.compile(r"^([0-9A-Fa-f:.]+)-([0-9A-Fa-f:.]+|\d+)$")
_IPV4_LITERAL_RE = re.compile(r"^\d+(?:\.\d+){3}$")


class TargetError(ValueError):
    """Raised when a target specification cannot be parsed."""


def _range_from_token(
    token: str,
) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ipaddress.IPv4Address | ipaddress.IPv6Address] | None:
    """Parse ``start-end`` (including the short ``10.0.0.5-20`` form)."""
    match = _RANGE_RE.fullmatch(token)
    if match is None:
        return None

    left, right = match.groups()
    try:
        start = ipaddress.ip_address(left)
    except ValueError:
        return None

    try:
        end = ipaddress.ip_address(right)
    except ValueError:
        # Short IPv4 form: 192.168.0.10-20
        if start.version == 4 and right.isdigit():
            prefix = str(start).rsplit(".", 1)[0]
            try:
                end = ipaddress.ip_address(f"{prefix}.{right}")
            except ValueError:
                raise TargetError(
                    f"Range '{token}' has an invalid IPv4 end address."
                ) from None
        elif start.version == 4 and _IPV4_LITERAL_RE.fullmatch(right):
            raise TargetError(f"Range '{token}' has an invalid IPv4 end address.")
        elif start.version == 6 and ":" in right:
            raise TargetError(f"Range '{token}' has an invalid IPv6 end address.")
        else:
            return None

    if start.version != end.version:
        raise TargetError(f"Range '{token}' mixes IPv4 and IPv6 addresses.")
    if int(end) < int(start):
        raise TargetError(f"Range '{token}' ends before it starts.")
    return start, end


def _count_network(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> int:
    if network.version == 4 and network.prefixlen < 31:
        return network.num_addresses - 2
    return network.num_addresses


def estimate_targets(spec: str) -> int:
    """Rough host count for the GUI, without doing any DNS lookups.

    Hostnames count as a single host. Invalid tokens are ignored.
    """
    count = 0
    for token in (part for part in _TOKEN_SPLIT.split(spec.strip()) if part):
        if "/" in token:
            try:
                count += _count_network(ipaddress.ip_network(token, strict=False))
            except ValueError:
                continue
            continue

        try:
            parsed_range = _range_from_token(token)
        except TargetError:
            # Invalid ranges are ignored, matching expand_targets()' rejection.
            continue
        if parsed_range is not None:
            start, end = parsed_range
            count += int(end) - int(start) + 1
        else:
            count += 1
    return max(count, 0)


def expand_targets(
    spec: str,
    *,
    resolve: bool = True,
    max_hosts: int = MAX_HOSTS,
) -> list[str]:
    """Expand a target specification into a de-duplicated list of IP strings.

    Supported forms (comma or whitespace separated):

    * single address: ``192.168.1.10`` / ``fd00::1``
    * network: ``192.168.1.0/24``
    * range: ``192.168.1.10-192.168.1.20`` or ``192.168.1.10-20``
    * hostname: ``example.com`` (when ``resolve`` is true)
    """
    tokens = [part for part in _TOKEN_SPLIT.split(spec.strip()) if part]
    if not tokens:
        raise TargetError("Enter at least one IP address, network or hostname.")

    hosts: list[str] = []
    seen: set[str] = set()

    def add(address: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        text = str(address)
        if text in seen:
            return
        if len(hosts) >= max_hosts:
            raise TargetError(
                f"Target expands to more than {max_hosts:,} hosts. "
                "Split the scan into smaller networks or ranges."
            )
        seen.add(text)
        hosts.append(text)

    for token in tokens:
        if "/" in token:
            try:
                network = ipaddress.ip_network(token, strict=False)
            except ValueError as exc:
                raise TargetError(f"Invalid network '{token}': {exc}") from exc

            if network.version == 4 and network.prefixlen < 31:
                if network.num_addresses - 2 > max_hosts:
                    raise TargetError(
                        f"Network '{token}' contains more than {max_hosts:,} hosts. "
                        "Split it into smaller networks."
                    )
                for address in network.hosts():
                    add(address)
            else:
                if network.num_addresses > max_hosts:
                    raise TargetError(
                        f"Network '{token}' contains more than {max_hosts:,} hosts. "
                        "Split it into smaller networks."
                    )
                for address in network:
                    add(address)
            continue

        parsed_range = _range_from_token(token)
        if parsed_range is not None:
            start, end = parsed_range
            size = int(end) - int(start) + 1
            if size > max_hosts:
                raise TargetError(
                    f"Range '{token}' contains more than {max_hosts:,} hosts. "
                    "Split it into smaller ranges."
                )
            current = int(start)
            while current <= int(end):
                add(ipaddress.ip_address(current))
                current += 1
            continue

        try:
            add(ipaddress.ip_address(token))
            continue
        except ValueError:
            pass

        if not resolve:
            raise TargetError(f"'{token}' is not an IP address, network or range.")

        try:
            infos = socket.getaddrinfo(token, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise TargetError(f"Cannot resolve '{token}': {exc}") from exc

        resolved_any = False
        for family, _, _, _, sockaddr in infos:
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue
            address, _, zone = sockaddr[0].partition("%")
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            add(f"{ip}%{zone}" if zone else ip)
            resolved_any = True

        if not resolved_any:
            raise TargetError(f"'{token}' did not resolve to an IP address.")

    if not hosts:
        raise TargetError("The target specification did not contain any hosts.")
    return hosts
