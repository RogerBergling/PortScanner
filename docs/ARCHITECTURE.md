# Architecture

## Goals

PortScanner is a no-root TCP/UDP connectivity scanner with a desktop GUI and a
headless automation mode. It favors simplicity, predictable resource use, and a
small supply chain over raw-packet features.

## Components

```text
app.py        Tkinter GUI, event polling, result table, CSV export
cli.py        Headless argument parsing, scan orchestration, text/CSV/JSON
config.py     Versioned settings, validation, atomic persistence
engine.py     asyncio TCP/UDP probes and scan lifecycle events
ports.py      Port specification parsing and presets
targets.py    Address, CIDR, range, and DNS target expansion
```

## Runtime flow

1. The GUI or CLI parses targets and ports.
2. `targets.expand_targets()` resolves and de-duplicates hosts.
3. `ScanConfig` is validated by `engine.validate_config()`.
4. `ScanEngine` starts a daemon thread with its own asyncio event loop.
5. A producer places `(host, port, protocol)` probes on a bounded queue.
6. Worker coroutines perform TCP connect or connected UDP probes.
7. Results and progress are emitted through a thread-safe callback.
8. The GUI polls a `queue.Queue`; the CLI blocks on the same event stream.

The bounded queue and worker count limit memory and socket usage. TCP probes use
non-blocking sockets, an `asyncio.timeout`, and `SO_LINGER` with a zero timeout
to send RST instead of leaving large numbers of sockets in TIME_WAIT.

## Configuration

`config.py` owns the schema. The current schema version is `1`. Reads tolerate
missing files, malformed JSON, unknown fields, and invalid values by falling
back to safe defaults. Writes use a temporary file in the destination directory,
`fsync`, and `os.replace` so a crash cannot leave a partial configuration.

## Trust boundaries

- **User input:** targets, ports, timeout, concurrency, and config values are
  validated before use.
- **DNS:** hostnames are resolved through the operating system resolver. DNS is
  currently synchronous in the GUI path and can block the interface.
- **Remote hosts:** probe responses and UDP payloads are treated as untrusted.
  UDP reads are bounded to 4096 bytes.
- **Local config:** in the user profile; other local users should not be able to
  modify it. Atomic temp files are created with user-private permissions.
- **No raw packets:** the application does not require root and does not send
  SYN, ICMP, or ARP probes.

## Failure model

- Individual probe failures are treated as closed, filtered, or unknown
  depending on the exception.
- A scan-level exception is reported through `ScanFinished.error`.
- Stopping a scan cancels the producer and workers, then emits a completion
  event with `stopped=True`.
- Settings failures never block a scan.

## Build and release

- Linux: `make build` creates a Python zipapp from `src/`.
- Windows: GitHub Actions runs PyInstaller twice, producing a windowed GUI
  executable and a console CLI executable.
- Build dependencies are pinned in `requirements-build.txt`.
- Tests, Ruff, pip-audit, CodeQL, and checksums are part of the release process.

## Testing strategy

- Unit tests for ports, targets, configuration, and CLI formatting.
- Integration tests against local TCP and UDP servers.
- CI matrix across Linux/Windows and Python 3.11/3.14.
- Remaining gap: no automated Tkinter GUI rendering or interaction tests.

## Extension points

- Add protocol probes in `engine.py`.
- Add output formats in `cli.py`.
- Add presets in `ports.py`.
- Add target syntax in `targets.py`.
- Add policy/authorization layers before `expand_targets()` or `ScanEngine`.
