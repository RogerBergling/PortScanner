from __future__ import annotations

import queue
import socket
import threading
import unittest
from unittest import mock

from portscanner.engine import (
    PortResult,
    ScanConfig,
    ScanEngine,
    ScanFinished,
    ScanProgress,
    _rst_linger_option,
    validate_config,
)


def run_scan(config: ScanConfig, timeout: float = 15.0) -> list[object]:
    events: list[object] = []
    event_queue: queue.Queue[object] = queue.Queue()
    engine = ScanEngine(config, event_queue.put)
    engine.start()
    try:
        while True:
            event = event_queue.get(timeout=timeout)
            events.append(event)
            if isinstance(event, ScanFinished):
                break
    finally:
        engine.join(timeout=2.0)
    return events


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ScanConfigValidationTests(unittest.TestCase):
    def test_valid_config_is_accepted(self) -> None:
        validate_config(
            ScanConfig(
                hosts=["127.0.0.1"],
                ports=[22, 80],
                protocols=("tcp", "udp"),
                timeout=0.5,
                concurrency=10,
            )
        )

    def test_invalid_configs_are_rejected(self) -> None:
        invalid: list[dict[str, object]] = [
            {"hosts": []},
            {"hosts": [""]},
            {"hosts": ["   "]},
            {"ports": []},
            {"ports": [0]},
            {"ports": [65536]},
            {"ports": [True]},
            {"protocols": ()},
            {"protocols": ("icmp",)},
            {"protocols": ("tcp", "tcp")},
            {"timeout": 0},
            {"timeout": -1},
            {"timeout": float("nan")},
            {"timeout": float("inf")},
            {"timeout": "1.0"},
            {"concurrency": 0},
            {"concurrency": "many"},
            {"concurrency": float("inf")},
        ]
        for overrides in invalid:
            values: dict[str, object] = {"hosts": ["127.0.0.1"], "ports": [80]}
            values.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                validate_config(ScanConfig(**values))  # type: ignore[arg-type]

    def test_engine_uses_the_same_validation(self) -> None:
        with self.assertRaises(ValueError):
            ScanEngine(
                ScanConfig(hosts=["127.0.0.1"], ports=[0]),
                lambda _event: None,
            )


class PlatformOptionTests(unittest.TestCase):
    def test_linger_payload_layout(self) -> None:
        with mock.patch("portscanner.engine.sys.platform", "win32"):
            self.assertEqual(len(_rst_linger_option()), 4)
        with mock.patch("portscanner.engine.sys.platform", "linux"):
            self.assertEqual(len(_rst_linger_option()), 8)


class EngineTests(unittest.TestCase):
    def test_tcp_scan_finds_open_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            open_port = server.getsockname()[1]
            closed_port = free_tcp_port()

            events = run_scan(
                ScanConfig(
                    hosts=["127.0.0.1"],
                    ports=[open_port, closed_port],
                    protocols=("tcp",),
                    timeout=0.5,
                    concurrency=8,
                )
            )

        results = [event for event in events if isinstance(event, PortResult)]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].port, open_port)
        self.assertEqual(results[0].state, "open")
        self.assertEqual(results[0].protocol, "tcp")

        finished = events[-1]
        self.assertIsInstance(finished, ScanFinished)
        assert isinstance(finished, ScanFinished)
        self.assertEqual(finished.scanned, 2)
        self.assertEqual(finished.open_ports, 1)
        self.assertFalse(finished.stopped)
        self.assertIsNone(finished.error)

    def test_udp_scan_finds_responding_service(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(("127.0.0.1", 0))
        server.settimeout(5.0)
        port = server.getsockname()[1]
        stop = threading.Event()

        def responder() -> None:
            try:
                while not stop.is_set():
                    try:
                        data, address = server.recvfrom(1024)
                    except socket.timeout:
                        return
                    server.sendto(b"pong", address)
            finally:
                server.close()

        thread = threading.Thread(target=responder, daemon=True)
        thread.start()
        try:
            events = run_scan(
                ScanConfig(
                    hosts=["127.0.0.1"],
                    ports=[port],
                    protocols=("udp",),
                    timeout=1.0,
                    concurrency=4,
                )
            )
        finally:
            stop.set()
            thread.join(timeout=5.0)

        results = [event for event in events if isinstance(event, PortResult)]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].state, "open")
        self.assertEqual(results[0].protocol, "udp")

    def test_progress_events_are_emitted(self) -> None:
        events = run_scan(
            ScanConfig(
                hosts=["127.0.0.1"],
                ports=[free_tcp_port()],
                protocols=("tcp",),
                timeout=0.2,
                concurrency=1,
            )
        )
        progress = [event for event in events if isinstance(event, ScanProgress)]
        self.assertGreaterEqual(len(progress), 1)
        self.assertEqual(events[-1].total, 1)

    def test_stop_ends_scan(self) -> None:
        # A non-routable address keeps connection attempts pending, so the scan
        # is still running when stop() is called.
        event_queue: queue.Queue[object] = queue.Queue()
        engine = ScanEngine(
            ScanConfig(
                hosts=["192.0.2.1"],
                ports=list(range(1, 200)),
                protocols=("tcp",),
                timeout=5.0,
                concurrency=8,
            ),
            event_queue.put,
        )
        engine.start()
        engine.stop()

        finished: ScanFinished | None = None
        for _ in range(100):
            try:
                event = event_queue.get(timeout=5.0)
            except queue.Empty:
                break
            if isinstance(event, ScanFinished):
                finished = event
                break

        engine.join(timeout=3.0)
        self.assertIsNotNone(finished)
        assert finished is not None
        self.assertTrue(finished.stopped)
        self.assertFalse(engine.is_running())


if __name__ == "__main__":
    unittest.main()
