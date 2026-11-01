"""Headless command-line scanning mode."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import queue
import sys
from pathlib import Path
from typing import Sequence

from .build_info import version_line
from .engine import (
    PortResult,
    ScanConfig,
    ScanEngine,
    ScanFinished,
    validate_config,
)
from .ports import PortError, parse_ports
from .targets import TargetError, expand_targets

PROTOCOLS: dict[str, tuple[str, ...]] = {
    "tcp": ("tcp",),
    "udp": ("udp",),
    "both": ("tcp", "udp"),
}

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


def _timeout(value: str) -> float:
    try:
        seconds = float(value.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return seconds


def _concurrency(value: str) -> int:
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a whole number") from None
    if not 1 <= count <= 5000:
        raise argparse.ArgumentTypeError("must be between 1 and 5000")
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portscanner scan",
        description="Run a TCP/UDP port scan without starting the GUI.",
        epilog=(
            "Only scan systems you own or are explicitly authorized to test. "
            "Exit codes: 0 success, 1 findings/error, 2 usage error, 130 interrupted."
        ),
    )
    parser.add_argument(
        "targets",
        nargs="+",
        metavar="TARGET",
        help="IP address, CIDR network, range or hostname",
    )
    parser.add_argument(
        "-p",
        "--ports",
        default="common",
        help="port list or range, or a preset keyword (default: common)",
    )
    parser.add_argument(
        "--all-ports",
        action="store_true",
        help="scan all 65,535 ports, ignoring --ports",
    )
    parser.add_argument(
        "--protocol",
        choices=tuple(PROTOCOLS),
        default="tcp",
        help="protocol to scan (default: tcp)",
    )
    parser.add_argument(
        "--timeout",
        type=_timeout,
        default=1.0,
        metavar="SECONDS",
        help="connection timeout in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--concurrency",
        type=_concurrency,
        default=1000,
        metavar="N",
        help="maximum probes in flight, 1-5000 (default: 1000)",
    )
    parser.add_argument(
        "--show-filtered",
        action="store_true",
        help="include UDP open|filtered results",
    )
    parser.add_argument(
        "--format",
        choices=("text", "csv", "json"),
        default="text",
        help="result format written to stdout or --output (default: text)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="write results to FILE instead of stdout",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress status and summary messages on stderr",
    )
    parser.add_argument(
        "--fail-on-open",
        action="store_true",
        help="return exit code 1 when at least one open port is found",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="allow scans larger than 2,000,000 probes without confirmation",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=version_line(),
    )
    return parser


def _result_dict(result: PortResult) -> dict[str, object]:
    return {
        "host": result.host,
        "port": result.port,
        "protocol": result.protocol,
        "state": result.state,
        "service": result.service or None,
    }


def _render_text(results: Sequence[PortResult]) -> str:
    lines: list[str] = []
    for result in results:
        line = f"{result.host}:{result.port}/{result.protocol} {result.state}"
        if result.service:
            line += f" {result.service}"
        lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def _render_csv(results: Sequence[PortResult]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["host", "port", "protocol", "state", "service"])
    for result in results:
        writer.writerow(
            [
                result.host,
                result.port,
                result.protocol,
                result.state,
                result.service,
            ]
        )
    return buffer.getvalue()


def _render_json(results: Sequence[PortResult], finished: ScanFinished) -> str:
    payload = {
        "scanned": finished.scanned,
        "total": finished.total,
        "open_ports": finished.open_ports,
        "elapsed": round(finished.elapsed, 6),
        "stopped": finished.stopped,
        "results": [_result_dict(result) for result in results],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _render(
    results: Sequence[PortResult], finished: ScanFinished, output_format: str
) -> str:
    if output_format == "csv":
        return _render_csv(results)
    if output_format == "json":
        return _render_json(results, finished)
    return _render_text(results)


def _write_output(text: str, output: str | None) -> None:
    if output in (None, "-"):
        sys.stdout.write(text)
        sys.stdout.flush()
        return
    Path(output).write_text(text, encoding="utf-8")


def _error(message: str) -> None:
    print(f"portscanner: {message}", file=sys.stderr)


def _plural(count: int, singular: str) -> str:
    return f"{count:,} {singular}{'' if count == 1 else 's'}"


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if len(args_list) > 1 and args_list[0] == "scan":
        args_list = args_list[1:]

    parser = build_parser()
    args = parser.parse_args(args_list)

    try:
        hosts = expand_targets(" ".join(args.targets))
    except TargetError as exc:
        _error(f"invalid target: {exc}")
        return EXIT_USAGE

    try:
        ports = parse_ports(args.ports, all_ports=args.all_ports)
    except PortError as exc:
        _error(f"invalid ports: {exc}")
        return EXIT_USAGE

    protocols = PROTOCOLS[args.protocol]
    total = len(hosts) * len(ports) * len(protocols)
    if total > 2_000_000 and not args.yes:
        _error(
            f"scan would perform {total:,} probes; re-run with --yes to allow it"
        )
        return EXIT_USAGE

    try:
        config = ScanConfig(
            hosts=hosts,
            ports=ports,
            protocols=protocols,
            timeout=args.timeout,
            concurrency=args.concurrency,
            show_filtered=args.show_filtered,
        )
        validate_config(config)
    except ValueError as exc:
        _error(str(exc))
        return EXIT_USAGE

    if not args.quiet:
        print(
            f"Scanning {_plural(len(hosts), 'host')}, {_plural(len(ports), 'port')}, "
            f"{', '.join(protocol.upper() for protocol in protocols)} "
            f"({_plural(total, 'probe')})…",
            file=sys.stderr,
        )

    events: queue.Queue[object] = queue.Queue()
    engine = ScanEngine(config, events.put)
    results: list[PortResult] = []
    finished: ScanFinished | None = None

    engine.start()
    try:
        while finished is None:
            try:
                event = events.get(timeout=0.25)
            except queue.Empty:
                continue
            if isinstance(event, PortResult):
                results.append(event)
            elif isinstance(event, ScanFinished):
                finished = event
    except KeyboardInterrupt:
        engine.stop()
        engine.join(timeout=2.0)
        _error("scan interrupted")
        return EXIT_INTERRUPTED
    finally:
        engine.join(timeout=2.0)

    if finished is None:
        _error("scan ended without a completion event")
        return EXIT_FAILURE
    if finished.error:
        _error(f"scan failed: {finished.error}")
        return EXIT_FAILURE

    text = _render(results, finished, args.format)
    try:
        _write_output(text, args.output)
    except OSError as exc:
        _error(f"could not write results: {exc}")
        return EXIT_FAILURE

    if not args.quiet:
        if finished.stopped:
            summary = (
                f"Scan stopped after {finished.elapsed:.2f}s — "
                f"{finished.scanned:,} of {_plural(finished.total, 'probe')} completed."
            )
        else:
            summary = (
                f"Scan complete in {finished.elapsed:.2f}s — "
                f"{_plural(finished.scanned, 'probe')}, "
                f"{_plural(finished.open_ports, 'open port')}."
            )
        print(summary, file=sys.stderr)

    if args.fail_on_open and any(result.state == "open" for result in results):
        return EXIT_FAILURE
    return EXIT_OK


def cli() -> None:
    """Console entry point that preserves main()'s exit status."""
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    cli()
