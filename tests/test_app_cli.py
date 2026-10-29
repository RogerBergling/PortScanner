from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from portscanner import __version__
from portscanner.app import _config_directory, cli, main


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
        self.assertEqual(stdout, f"portscanner {__version__}\n")
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


class ConfigDirectoryTests(unittest.TestCase):
    def test_default_location(self) -> None:
        with (
            mock.patch("portscanner.app.sys.platform", "linux"),
            mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}),
        ):
            self.assertEqual(
                _config_directory(),
                Path.home() / ".config" / "portscanner",
            )

    def test_absolute_xdg_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch("portscanner.app.sys.platform", "linux"),
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}),
            ):
                self.assertEqual(
                    _config_directory(),
                    Path(directory) / "portscanner",
                )

    def test_relative_xdg_override_is_ignored(self) -> None:
        with (
            mock.patch("portscanner.app.sys.platform", "linux"),
            mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative/path"}),
        ):
            self.assertEqual(
                _config_directory(),
                Path.home() / ".config" / "portscanner",
            )

    def test_windows_uses_appdata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch("portscanner.app.sys.platform", "win32"),
                mock.patch.dict(os.environ, {"APPDATA": directory}),
            ):
                self.assertEqual(
                    _config_directory(),
                    Path(directory) / "portscanner",
                )

    def test_windows_falls_back_to_roaming_appdata(self) -> None:
        with (
            mock.patch("portscanner.app.sys.platform", "win32"),
            mock.patch.dict(os.environ, {"APPDATA": ""}),
        ):
            self.assertEqual(
                _config_directory(),
                Path.home() / "AppData" / "Roaming" / "portscanner",
            )


if __name__ == "__main__":
    unittest.main()
