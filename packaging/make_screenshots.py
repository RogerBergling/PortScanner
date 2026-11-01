"""Capture README screenshots from the real GUI and CLI.

Intended to run on Linux under Xvfb:

    xvfb-run -a -s "-screen 0 1280x900x24" \
        env PYTHONPATH=src python3 packaging/make_screenshots.py docs/screenshots
"""

from __future__ import annotations

import shlex
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import tkinter as tk  # noqa: E402

from portscanner.app import PortScannerApp  # noqa: E402
from portscanner.engine import PortResult  # noqa: E402

SAMPLES = [
    PortResult("192.168.1.10", 22, "tcp", "open", "ssh"),
    PortResult("192.168.1.10", 80, "tcp", "open", "http"),
    PortResult("192.168.1.10", 443, "tcp", "open", "https"),
    PortResult("192.168.1.10", 3306, "tcp", "open", "mysql"),
    PortResult("192.168.1.10", 5432, "tcp", "open", "postgresql"),
    PortResult("192.168.1.20", 22, "tcp", "open", "ssh"),
    PortResult("192.168.1.20", 8080, "tcp", "open", "http-alt"),
    PortResult("192.168.1.30", 443, "tcp", "open", "https"),
]


def capture_gui(path: Path) -> None:
    root = tk.Tk()
    root.geometry("1280x900+0+0")
    app = PortScannerApp(root)
    root.geometry("1280x900+0+0")
    root.attributes("-topmost", True)

    app.target_var.set("192.168.1.0/24")
    app.ports_var.set("22,80,443,3306,5432,8080")
    app.protocol_var.set("TCP")
    app._update_estimate()

    for result in SAMPLES:
        app._add_result(result)

    app.progress["value"] = 100.0
    app.percent_var.set("100%")
    app.status_var.set(
        "Scan complete in 2.4s — 1,524 probes, 8 open port(s) found."
    )
    app.stats_var.set("8 open · 2.4s · 747/s")

    root.update_idletasks()
    root.update()
    time.sleep(1.0)

    subprocess.run(["scrot", "-o", str(path)], check=True)
    root.destroy()
    time.sleep(0.5)


def _serve_port() -> tuple[socket.socket, int, threading.Event]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    server.settimeout(0.2)
    port = server.getsockname()[1]
    stop = threading.Event()

    def accept_connections() -> None:
        while not stop.is_set():
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            connection.close()

    threading.Thread(target=accept_connections, daemon=True).start()
    return server, port, stop


def capture_cli(path: Path) -> None:
    server, port, stop = _serve_port()
    command = (
        f"cd {shlex.quote(str(ROOT))} && "
        f"PYTHONPATH=src /usr/bin/python3 -m portscanner scan 127.0.0.1 "
        f"-p 80,443,8080,{port} --timeout 0.3 --concurrency 4; sleep 10"
    )
    process = subprocess.Popen(
        [
            "xterm",
            "-title",
            "PortScanner CLI",
            "-geometry",
            "100x16+0+0",
            "-bg",
            "#0f1117",
            "-fg",
            "#e8eaf0",
            "-fa",
            "DejaVu Sans Mono",
            "-fs",
            "12",
            "-e",
            "bash",
            "-lc",
            command,
        ]
    )

    try:
        window = subprocess.run(
            ["xdotool", "search", "--sync", "--name", "PortScanner CLI"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.splitlines()[0]
        time.sleep(2.5)
        subprocess.run(
            ["import", "-window", window, str(path)],
            check=True,
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        stop.set()
        server.close()


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
    output.mkdir(parents=True, exist_ok=True)
    capture_gui(output / "gui.png")
    capture_cli(output / "cli.png")
    print(f"Wrote screenshots to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
