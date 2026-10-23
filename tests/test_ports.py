from __future__ import annotations

import unittest

from portscanner.ports import ALL_PORTS, COMMON_PORTS, PortError, parse_ports


class ParsePortsTests(unittest.TestCase):
    def test_single_and_list(self) -> None:
        self.assertEqual(parse_ports("22"), [22])
        self.assertEqual(parse_ports("80, 22,443"), [22, 80, 443])

    def test_ranges_and_overlaps(self) -> None:
        self.assertEqual(parse_ports("1-3,3-5"), [1, 2, 3, 4, 5])
        self.assertEqual(parse_ports("8000-8002, 80"), [80, 8000, 8001, 8002])

    def test_all_ports(self) -> None:
        self.assertEqual(len(parse_ports("all")), 65535)
        self.assertEqual(parse_ports("all"), ALL_PORTS)
        self.assertEqual(parse_ports("", all_ports=True), ALL_PORTS)

    def test_keywords(self) -> None:
        self.assertEqual(parse_ports("common"), COMMON_PORTS)
        self.assertEqual(parse_ports("web"), [80, 443, 8080, 8443, 8000, 8888])
        self.assertEqual(parse_ports("well-known"), list(range(1, 1024)))

    def test_invalid_values(self) -> None:
        for spec in ("0", "65536", "10-5", "abc", "1-70000", "", "80-" ):
            with self.subTest(spec=spec), self.assertRaises(PortError):
                parse_ports(spec)

    def test_empty_after_checkbox(self) -> None:
        with self.assertRaises(PortError):
            parse_ports("   ")


if __name__ == "__main__":
    unittest.main()
