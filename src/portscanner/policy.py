"""Target scope policy and hard scan limits."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_MAX_HOSTS = 65_536
DEFAULT_MAX_PROBES = 10_000_000

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


class PolicyError(ValueError):
    """Raised when a target violates the configured scan policy."""


def _networks(values: Sequence[str], field: str) -> tuple[Network, ...]:
    networks: list[Network] = []
    for value in values:
        if not isinstance(value, str):
            raise PolicyError(f"{field} entries must be CIDR strings.")
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise PolicyError(f"Invalid {field} entry '{value}': {exc}") from exc
    return tuple(networks)


def _positive_int(value: Any, field: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise PolicyError(f"{field} must be a positive integer.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise PolicyError(f"{field} must be a positive integer.") from None
    if number < 1:
        raise PolicyError(f"{field} must be a positive integer.")
    return number


@dataclass(frozen=True, slots=True)
class ScanPolicy:
    """Allow/deny CIDRs plus hard limits applied before a scan starts."""

    allow_cidrs: tuple[Network, ...] = ()
    deny_cidrs: tuple[Network, ...] = ()
    max_hosts: int = DEFAULT_MAX_HOSTS
    max_probes: int = DEFAULT_MAX_PROBES

    def __post_init__(self) -> None:
        if self.max_hosts < 1:
            raise PolicyError("max_hosts must be a positive integer.")
        if self.max_probes < 1:
            raise PolicyError("max_probes must be a positive integer.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ScanPolicy":
        allow = data.get("allow_cidrs", [])
        deny = data.get("deny_cidrs", [])
        if not isinstance(allow, list):
            raise PolicyError("allow_cidrs must be a JSON array.")
        if not isinstance(deny, list):
            raise PolicyError("deny_cidrs must be a JSON array.")
        return cls(
            allow_cidrs=_networks(allow, "allow_cidrs"),
            deny_cidrs=_networks(deny, "deny_cidrs"),
            max_hosts=_positive_int(
                data.get("max_hosts"), "max_hosts", DEFAULT_MAX_HOSTS
            ),
            max_probes=_positive_int(
                data.get("max_probes"), "max_probes", DEFAULT_MAX_PROBES
            ),
        )

    def with_overrides(
        self,
        *,
        allow_cidrs: Sequence[str] | None = None,
        deny_cidrs: Sequence[str] | None = None,
        max_hosts: int | None = None,
        max_probes: int | None = None,
    ) -> "ScanPolicy":
        return ScanPolicy(
            allow_cidrs=(
                self.allow_cidrs
                if allow_cidrs is None
                else _networks(allow_cidrs, "allow_cidrs")
            ),
            deny_cidrs=(
                self.deny_cidrs
                if deny_cidrs is None
                else _networks(deny_cidrs, "deny_cidrs")
            ),
            max_hosts=(
                self.max_hosts
                if max_hosts is None
                else _positive_int(max_hosts, "max_hosts", self.max_hosts)
            ),
            max_probes=(
                self.max_probes
                if max_probes is None
                else _positive_int(max_probes, "max_probes", self.max_probes)
            ),
        )

    def check_hosts(self, hosts: Sequence[str]) -> None:
        for host in hosts:
            address = ipaddress.ip_address(host.partition("%")[0])
            if any(
                address.version == network.version and address in network
                for network in self.deny_cidrs
            ):
                raise PolicyError(f"Target {host} is denied by policy.")
            if self.allow_cidrs and not any(
                address.version == network.version and address in network
                for network in self.allow_cidrs
            ):
                raise PolicyError(f"Target {host} is not in the allowed CIDR list.")

    def check_limits(
        self, host_count: int, port_count: int, protocol_count: int
    ) -> None:
        if host_count > self.max_hosts:
            raise PolicyError(
                f"Scan uses {host_count:,} hosts, above policy max_hosts="
                f"{self.max_hosts:,}."
            )
        total = host_count * port_count * protocol_count
        if total > self.max_probes:
            raise PolicyError(
                f"Scan would perform {total:,} probes, above policy max_probes="
                f"{self.max_probes:,}."
            )


def load_policy(path: Path | None = None) -> ScanPolicy:
    """Load a JSON policy; a missing path returns the public default policy."""
    if path is None or not path.exists():
        return ScanPolicy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PolicyError(f"Could not read policy file '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyError(f"Policy file '{path}' must contain a JSON object.")
    return ScanPolicy.from_mapping(data)
