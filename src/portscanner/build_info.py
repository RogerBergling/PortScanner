"""Release build metadata displayed in the GUI, CLI, and README."""

from __future__ import annotations

BUILD_NUMBER = "20261101.1"
BUILD_TIMESTAMP = "2026-11-01 11:14 UTC"


def build_label() -> str:
    return f"Build {BUILD_NUMBER} · {BUILD_TIMESTAMP}"


def version_line() -> str:
    from . import __version__

    return f"portscanner {__version__} (build {BUILD_NUMBER}, {BUILD_TIMESTAMP})"
