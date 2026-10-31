from __future__ import annotations

import contextlib
import csv
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path

from portscanner.cli import main


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class CliTests(unittest.TestCase):
    def test_json_output_finds_open_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]

            code, stdout, stderr = run_cli(
                [
                    "127.0.0.1",
                    "-p",
                    str(port),
                    "--timeout",
                    "0.5",
                    "--concurrency",
                    "4",
                    "--format",
                    "json",
                    "--quiet",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["open_ports"], 1)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["results"][0]["host"], "127.0.0.1")
        self.assertEqual(payload["results"][0]["port"], port)
        self.assertEqual(payload["results"][0]["protocol"], "tcp")
        self.assertEqual(payload["results"][0]["state"], "open")

    def test_csv_output_to_file(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]

            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "results.csv"
                code, stdout, stderr = run_cli(
                    [
                        "127.0.0.1",
                        "-p",
                        str(port),
                        "--timeout",
                        "0.5",
                        "--format",
                        "csv",
                        "--output",
                        str(output),
                        "--quiet",
                    ]
                )
                with output.open(encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["port"], str(port))
        self.assertEqual(rows[0]["state"], "open")

    def test_text_output_and_scan_prefix(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]

            code, stdout, stderr = run_cli(
                [
                    "scan",
                    "127.0.0.1",
                    "-p",
                    str(port),
                    "--timeout",
                    "0.5",
                    "--quiet",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn(f"127.0.0.1:{port}/tcp open", stdout)

    def test_fail_on_open(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]

            code, _stdout, _stderr = run_cli(
                [
                    "127.0.0.1",
                    "-p",
                    str(port),
                    "--timeout",
                    "0.5",
                    "--fail-on-open",
                    "--quiet",
                ]
            )

        self.assertEqual(code, 1)

    def test_no_open_ports(self) -> None:
        port = free_tcp_port()
        code, stdout, _stderr = run_cli(
            [
                "127.0.0.1",
                "-p",
                str(port),
                "--timeout",
                "0.2",
                "--format",
                "json",
                "--quiet",
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["open_ports"], 0)

    def test_invalid_ports(self) -> None:
        code, stdout, stderr = run_cli(["127.0.0.1", "-p", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("invalid ports", stderr)

    def test_invalid_target(self) -> None:
        code, stdout, stderr = run_cli(["not/a/target"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("invalid target", stderr)

    def test_large_scan_requires_confirmation(self) -> None:
        code, stdout, stderr = run_cli(
            ["127.0.0.1-32", "--all-ports", "--quiet"]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("re-run with --yes", stderr)


if __name__ == "__main__":
    unittest.main()
