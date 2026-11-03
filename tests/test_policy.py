from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from portscanner.policy import (
    DEFAULT_MAX_HOSTS,
    DEFAULT_MAX_PROBES,
    PolicyError,
    ScanPolicy,
    load_policy,
)


class ScanPolicyTests(unittest.TestCase):
    def test_default_allows_targets(self) -> None:
        policy = ScanPolicy()
        policy.check_hosts(["192.0.2.1", "2001:db8::1"])
        policy.check_limits(1, 10, 1)
        self.assertEqual(policy.max_hosts, DEFAULT_MAX_HOSTS)
        self.assertEqual(policy.max_probes, DEFAULT_MAX_PROBES)

    def test_deny_takes_precedence(self) -> None:
        policy = ScanPolicy.from_mapping(
            {
                "allow_cidrs": ["10.0.0.0/8"],
                "deny_cidrs": ["10.10.0.0/16"],
            }
        )
        policy.check_hosts(["10.1.2.3"])
        with self.assertRaises(PolicyError):
            policy.check_hosts(["10.10.1.1"])

    def test_allowlist_is_enforced(self) -> None:
        policy = ScanPolicy.from_mapping({"allow_cidrs": ["10.0.0.0/8"]})
        with self.assertRaises(PolicyError):
            policy.check_hosts(["192.0.2.1"])

    def test_ipv6_zone_is_ignored_for_matching(self) -> None:
        policy = ScanPolicy.from_mapping({"allow_cidrs": ["fe80::/10"]})
        policy.check_hosts(["fe80::1%eth0"])

    def test_limits_are_enforced(self) -> None:
        policy = ScanPolicy(max_hosts=2, max_probes=10)
        with self.assertRaises(PolicyError):
            policy.check_limits(3, 1, 1)
        with self.assertRaises(PolicyError):
            policy.check_limits(1, 11, 1)
        policy.check_limits(1, 10, 1)

    def test_overrides_replace_lists_and_limits(self) -> None:
        policy = ScanPolicy().with_overrides(
            allow_cidrs=["192.0.2.0/24"],
            deny_cidrs=["192.0.2.128/25"],
            max_hosts=10,
            max_probes=100,
        )
        self.assertEqual(policy.max_hosts, 10)
        self.assertEqual(policy.max_probes, 100)
        with self.assertRaises(PolicyError):
            policy.check_hosts(["192.0.2.200"])

    def test_invalid_values_are_rejected(self) -> None:
        invalid = [
            {"allow_cidrs": ["not-a-cidr"]},
            {"allow_cidrs": "10.0.0.0/8"},
            {"max_hosts": 0},
            {"max_probes": -1},
            {"max_hosts": True},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(PolicyError):
                ScanPolicy.from_mapping(data)

    def test_missing_file_returns_default_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = load_policy(Path(directory) / "missing.json")
        self.assertEqual(policy, ScanPolicy())

    def test_json_file_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(
                json.dumps(
                    {
                        "allow_cidrs": ["192.0.2.0/24"],
                        "deny_cidrs": ["192.0.2.128/25"],
                        "max_hosts": 16,
                        "max_probes": 1000,
                    }
                ),
                encoding="utf-8",
            )
            policy = load_policy(path)
        self.assertEqual(policy.max_hosts, 16)
        self.assertEqual(policy.max_probes, 1000)
        with self.assertRaises(PolicyError):
            policy.check_hosts(["192.0.2.200"])

    def test_invalid_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(PolicyError):
                load_policy(path)


if __name__ == "__main__":
    unittest.main()
