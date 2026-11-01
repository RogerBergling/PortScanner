from __future__ import annotations

import contextlib
import io
import sys
import unittest
from unittest import mock

from portscanner.app import cli, main
from portscanner.build_info import version_line


class CommandLineTests(unittest.TestCase):
    def run_main(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_version(self) -> None:
        code, stdout, stderr = self.run_main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, f"{version_line()}\n")
        self.assertEqual(stderr, "")

    def test_help(self) -> None:
        code, stdout, stderr = self.run_main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("Usage:", stdout)
        self.assertIn("portscanner --version", stdout)
        self.assertEqual(stderr, "")

    def test_unknown_argument_is_rejected(self) -> None:
        code, stdout, stderr = self.run_main(["--bogus"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("unrecognized argument: --bogus", stderr)
        self.assertIn("portscanner --help", stderr)

    def test_unknown_argument_wins_over_version(self) -> None:
        code, stdout, stderr = self.run_main(["--version", "--bogus"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("--bogus", stderr)

    def test_scan_subcommand_delegates_to_cli(self) -> None:
        with mock.patch("portscanner.cli.main", return_value=7) as scan_main:
            code, stdout, stderr = self.run_main(["scan", "127.0.0.1"])
        self.assertEqual(code, 7)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        scan_main.assert_called_once_with(["127.0.0.1"])

    def test_cli_preserves_exit_status(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["portscanner", "--bogus"]),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            cli()
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--bogus", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
