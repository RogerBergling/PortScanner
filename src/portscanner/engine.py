"""Asynchronous TCP/UDP connect scanner.

The engine runs its own asyncio event loop in a background thread and reports
results through a callback. That keeps the GUI responsive while thousands of
connection attempts are in flight.
"""

from __future__ import annotations

import asyncio
import errno
import math
import socket
import struct
import sys
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

VALID_PROTOCOLS = frozenset({"tcp", "udp"})

UDP_PROBES: dict[int, bytes] = {
    # DNS: query for version.bind (CHAOS TXT), which many resolvers answer.
    53: (
        b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        b"\x07version\x04bind\x00"
        b"\x00\x10\x00\x03"
    ),
    # NTP: client mode version 3.
    123: b"\x1b" + b"\x00" * 47,
    # mDNS service enumeration.
    5353: (
        b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        b"\x09_services\x07_dns-sd\x04_udp\x05local\x00"
        b"\x00\x0c\x00\x01"
    ),
    # SSDP discovery.
    1900: (
        b"M-SEARCH * HTTP/1.1\r\n"
        b"HOST: 239.255.255.250:1900\r\n"
        b'MAN: "ssdp:discover"\r\n'
        b"MX: 1\r\n"
        b"ST: ssdp:all\r\n\r\n"
    ),
}

DEFAULT_PROBE = b"\x00"


def _safe_concurrency() -> int:
    """Never open more sockets than the process is allowed to hold."""
    try:
        import resource

        soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft_limit != resource.RLIM_INFINITY:
            return max(16, soft_limit - 64)
    except (ImportError, OSError, ValueError):
        pass
    return 4096


@dataclass(frozen=True, slots=True)
class ScanConfig:
    hosts: list[str]
    ports: list[int]
    protocols: tuple[str, ...] = ("tcp",)
    timeout: float = 1.0
    concurrency: int = 1000
    show_filtered: bool = False


@dataclass(frozen=True, slots=True)
class PortResult:
    host: str
    port: int
    protocol: str
    state: str
    service: str


@dataclass(frozen=True, slots=True)
class ScanProgress:
    scanned: int
    total: int
    open_ports: int
    elapsed: float
    rate: float
    current: str


@dataclass(frozen=True, slots=True)
class ScanFinished:
    scanned: int
    total: int
    open_ports: int
    elapsed: float
    stopped: bool
    error: str | None = None


def validate_config(config: ScanConfig) -> None:
    """Reject scan settings that would otherwise fail silently or strangely."""
    if not config.hosts:
        raise ValueError("A scan needs at least one host.")
    if any(
        not isinstance(host, str) or not host.strip() for host in config.hosts
    ):
        raise ValueError("Scan hosts must be non-empty strings.")

    if not config.ports:
        raise ValueError("A scan needs at least one port.")
    for port in config.ports:
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise ValueError(
                f"Invalid port {port!r}: ports must be integers between 1 and 65535."
            )

    if not config.protocols:
        raise ValueError("A scan needs at least one protocol.")
    unsupported = [p for p in config.protocols if p not in VALID_PROTOCOLS]
    if unsupported:
        raise ValueError(
            "Unsupported protocol(s): "
            + ", ".join(str(p) for p in unsupported)
            + ". Use 'tcp' and/or 'udp'."
        )
    if len(set(config.protocols)) != len(config.protocols):
        raise ValueError("Protocols must not be repeated.")

    if isinstance(config.timeout, bool) or not isinstance(
        config.timeout, (int, float)
    ):
        raise ValueError("Timeout must be a positive number of seconds.")
    timeout = float(config.timeout)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be a positive number of seconds.")

    try:
        concurrency = int(config.concurrency)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Concurrency must be a positive integer.") from None
    if concurrency < 1:
        raise ValueError("Concurrency must be a positive integer.")


@lru_cache(maxsize=4096)
def _service_name(port: int, protocol: str) -> str:
    try:
        return socket.getservbyport(port, protocol)
    except OSError:
        return ""


def _family_for(host: str) -> socket.AddressFamily:
    return socket.AF_INET6 if ":" in host else socket.AF_INET


def _rst_linger_option() -> bytes:
    """Return a SO_LINGER value that sends RST instead of FIN on close."""
    # Windows' struct linger uses two unsigned shorts; POSIX uses two ints.
    return struct.pack("hh" if sys.platform == "win32" else "ii", 1, 0)


class ScanEngine:
    """Run one scan. Create, :meth:`start`, then observe events via callback."""

    def __init__(self, config: ScanConfig, on_event: Callable[[object], None]) -> None:
        validate_config(config)
        self.config = config
        self._emit = on_event
        self._total = len(config.hosts) * len(config.ports) * len(config.protocols)
        self._scanned = 0
        self._open = 0
        self._current = ""
        self._started_at = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._producer: asyncio.Task[None] | None = None
        self._progress_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ API

    @property
    def total(self) -> int:
        return self._total

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("ScanEngine can only be started once.")
        self._started_at = time.monotonic()
        self._thread = threading.Thread(
            target=self._run, name="portscanner-engine", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._cancel)
        except RuntimeError:
            # The loop finished between the check and the call.
            pass

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -------------------------------------------------------------- runtime

    def _cancel(self) -> None:
        if self._producer is not None:
            self._producer.cancel()
        for worker in self._workers:
            worker.cancel()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        started = time.monotonic()
        error: str | None = None

        self._emit(
            ScanProgress(0, self._total, 0, 0.0, 0.0, "preparing")
        )
        try:
            loop.run_until_complete(self._scan())
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # keep the GUI informed instead of dying silently
            error = f"{type(exc).__name__}: {exc}"
        finally:
            elapsed = time.monotonic() - started
            self._emit(
                ScanFinished(
                    scanned=self._scanned,
                    total=self._total,
                    open_ports=self._open,
                    elapsed=elapsed,
                    stopped=self._stop.is_set(),
                    error=error,
                )
            )
            self._loop = None
            loop.close()

    async def _scan(self) -> None:
        concurrency = max(1, min(int(self.config.concurrency), 5000))
        concurrency = min(concurrency, _safe_concurrency())
        queue: asyncio.Queue[tuple[str, int, str] | None] = asyncio.Queue(
            maxsize=max(1024, concurrency * 4)
        )

        self._progress_task = asyncio.create_task(
            self._report_progress(), name="progress"
        )
        self._workers = [
            asyncio.create_task(self._worker(queue), name=f"worker-{index}")
            for index in range(concurrency)
        ]
        self._producer = asyncio.create_task(self._produce(queue), name="producer")

        try:
            await self._producer
        except asyncio.CancelledError:
            pass
        finally:
            if self._stop.is_set():
                # stop() may have been called before the loop existed, so make
                # sure queued workers are not left waiting for items.
                for worker in self._workers:
                    worker.cancel()
            else:
                for _ in self._workers:
                    await queue.put(None)
            await asyncio.gather(*self._workers, return_exceptions=True)
            if self._progress_task is not None:
                self._progress_task.cancel()
                await asyncio.gather(self._progress_task, return_exceptions=True)
            self._workers = []
            self._producer = None
            self._progress_task = None

    async def _produce(
        self, queue: "asyncio.Queue[tuple[str, int, str] | None]"
    ) -> None:
        for host in self.config.hosts:
            for port in self.config.ports:
                for protocol in self.config.protocols:
                    if self._stop.is_set():
                        return
                    await queue.put((host, port, protocol))

    async def _report_progress(self) -> None:
        while True:
            await asyncio.sleep(0.15)
            elapsed = max(time.monotonic() - self._started_at, 1e-9)
            self._emit(
                ScanProgress(
                    scanned=self._scanned,
                    total=self._total,
                    open_ports=self._open,
                    elapsed=elapsed,
                    rate=self._scanned / elapsed,
                    current=self._current,
                )
            )

    async def _worker(
        self, queue: "asyncio.Queue[tuple[str, int, str] | None]"
    ) -> None:
        loop = asyncio.get_running_loop()
        while True:
            item = await queue.get()
            if item is None:
                return
            if self._stop.is_set():
                continue

            host, port, protocol = item
            self._current = f"{host}:{port} ({protocol.upper()})"
            try:
                if protocol == "tcp":
                    state = await self._scan_tcp(loop, host, port)
                else:
                    state = await self._scan_udp(loop, host, port)
            except asyncio.CancelledError:
                raise
            except Exception:
                state = None

            self._scanned += 1
            if state is None:
                continue
            if state == "open" or (
                state == "open|filtered" and self.config.show_filtered
            ):
                if state == "open":
                    self._open += 1
                self._emit(
                    PortResult(
                        host=host,
                        port=port,
                        protocol=protocol,
                        state=state,
                        service=_service_name(port, protocol),
                    )
                )

    async def _scan_tcp(
        self, loop: asyncio.AbstractEventLoop, host: str, port: int
    ) -> str | None:
        try:
            sock = socket.socket(_family_for(host), socket.SOCK_STREAM)
        except OSError:
            return None

        try:
            sock.setblocking(False)
            # Send RST instead of FIN, otherwise full port scans leave tens of
            # thousands of sockets in TIME_WAIT.
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_LINGER, _rst_linger_option()
            )
            async with asyncio.timeout(self.config.timeout):
                await loop.sock_connect(sock, (host, port))
            return "open"
        except TimeoutError:
            return "filtered"
        except ConnectionRefusedError:
            return "closed"
        except OSError as exc:
            if exc.errno == errno.ETIMEDOUT:
                return "filtered"
            if exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
                return "unreachable"
            return "closed"
        finally:
            sock.close()

    async def _scan_udp(
        self, loop: asyncio.AbstractEventLoop, host: str, port: int
    ) -> str | None:
        try:
            sock = socket.socket(_family_for(host), socket.SOCK_DGRAM)
        except OSError:
            return None

        try:
            sock.setblocking(False)
            sock.connect((host, port))
            try:
                async with asyncio.timeout(self.config.timeout):
                    await loop.sock_sendall(sock, UDP_PROBES.get(port, DEFAULT_PROBE))
                    await loop.sock_recv(sock, 4096)
                return "open"
            except TimeoutError:
                # No reply: the service may be open but silent, or filtered.
                return "open|filtered"
            except ConnectionRefusedError:
                return "closed"
            except OSError as exc:
                if exc.errno == errno.ECONNREFUSED:
                    return "closed"
                if exc.errno == errno.ETIMEDOUT:
                    return "open|filtered"
                return None
        finally:
            sock.close()
