from __future__ import annotations

import unittest

from portscanner.targets import TargetError, estimate_targets, expand_targets


class ExpandTargetsTests(unittest.TestCase):
    def test_single_address(self) -> None:
        self.assertEqual(expand_targets("192.0.2.10"), ["192.0.2.10"])
        self.assertEqual(expand_targets("2001:db8::1"), ["2001:db8::1"])

    def test_network_excludes_network_and_broadcast(self) -> None:
        hosts = expand_targets("192.0.2.0/30")
        self.assertEqual(hosts, ["192.0.2.1", "192.0.2.2"])

    def test_host_network(self) -> None:
        self.assertEqual(expand_targets("192.0.2.7/32"), ["192.0.2.7"])

    def test_range_with_full_end(self) -> None:
        self.assertEqual(
            expand_targets("192.0.2.5-192.0.2.7"),
            ["192.0.2.5", "192.0.2.6", "192.0.2.7"],
        )

    def test_range_with_short_end(self) -> None:
        self.assertEqual(
            expand_targets("192.0.2.250-252"),
            ["192.0.2.250", "192.0.2.251", "192.0.2.252"],
        )

    def test_duplicates_are_removed_in_order(self) -> None:
        self.assertEqual(
            expand_targets("192.0.2.1, 192.0.2.1 192.0.2.0/31"),
            ["192.0.2.1", "192.0.2.0"],
        )

    def test_reverse_range_is_rejected(self) -> None:
        with self.assertRaises(TargetError):
            expand_targets("192.0.2.9-192.0.2.2")

    def test_invalid_range_end_is_rejected(self) -> None:
        for spec in (
            "192.0.2.5-300",
            "192.0.2.5-192.0.2.300",
            "2001:db8::1-2001:db8::ffff:ffff:ffff:ffff:ffff",
        ):
            with self.subTest(spec=spec), self.assertRaises(TargetError):
                expand_targets(spec, resolve=False)

    def test_empty_spec_is_rejected(self) -> None:
        with self.assertRaises(TargetError):
            expand_targets("   ")

    def test_invalid_network_is_rejected(self) -> None:
        with self.assertRaises(TargetError):
            expand_targets("192.0.2.0/99")

    def test_hostname_without_resolution_is_rejected(self) -> None:
        with self.assertRaises(TargetError):
            expand_targets("example.com", resolve=False)

    def test_max_hosts_is_enforced(self) -> None:
        with self.assertRaises(TargetError):
            expand_targets("10.0.0.0/24", max_hosts=10)

    def test_estimate_targets(self) -> None:
        self.assertEqual(estimate_targets("192.0.2.0/30"), 2)
        self.assertEqual(estimate_targets("192.0.2.1"), 1)
        self.assertEqual(estimate_targets("192.0.2.1-192.0.2.10"), 10)
        self.assertEqual(estimate_targets("2001:db8::1-2001:db8::5"), 5)
        self.assertEqual(estimate_targets("example.com"), 1)
        self.assertEqual(estimate_targets("192.0.2.9-192.0.2.2"), 0)
        self.assertEqual(estimate_targets("192.0.2.5-300"), 0)
        self.assertEqual(estimate_targets("not/a/network"), 0)


if __name__ == "__main__":
    unittest.main()
