"""Persistent application settings with validation and atomic writes."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .ports import PRESETS

CONFIG_VERSION = 1
PROTOCOL_CHOICES = ("TCP", "UDP", "TCP + UDP")
DEFAULT_PORTS = "22,80,443"


def config_directory(
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user config directory for the selected platform."""
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home

    if platform == "win32":
        appdata = environ.get("APPDATA", "").strip()
        base = (
            Path(appdata).expanduser()
            if appdata
            else home / "AppData" / "Roaming"
        )
        return base / "portscanner"

    override = environ.get("XDG_CONFIG_HOME", "").strip()
    if override:
        base = Path(override).expanduser()
        if base.is_absolute():
            return base / "portscanner"
    return home / ".config" / "portscanner"


def _text(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _timeout_text(value: Any) -> str:
    text = _text(value, "1.0").strip()
    try:
        seconds = float(text.replace(",", "."))
    except ValueError:
        return "1.0"
    if not math.isfinite(seconds) or not 0.05 <= seconds <= 10.0:
        return "1.0"
    return text


def _concurrency_text(value: Any) -> str:
    text = _text(value, "1000").strip()
    try:
        count = int(text)
    except ValueError:
        return "1000"
    if not 1 <= count <= 5000:
        return "1000"
    return str(count)


@dataclass(slots=True)
class AppConfig:
    """Serializable GUI settings with defensive defaults."""

    targets: str = ""
    ports: str = DEFAULT_PORTS
    all_ports: bool = False
    preset: str = "Custom"
    protocol: str = "TCP"
    timeout: str = "1.0"
    concurrency: str = "1000"
    show_filtered: bool = False
    version: int = CONFIG_VERSION

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "AppConfig":
        version = data.get("version", CONFIG_VERSION)
        if not isinstance(version, int) or isinstance(version, bool):
            version = CONFIG_VERSION
        version = min(max(version, 1), CONFIG_VERSION)

        preset = _text(data.get("preset"), "Custom")
        if preset not in PRESETS:
            preset = "Custom"

        protocol = _text(data.get("protocol"), "TCP")
        if protocol not in PROTOCOL_CHOICES:
            protocol = "TCP"

        ports = _text(data.get("ports"), DEFAULT_PORTS).strip()
        if not ports:
            ports = DEFAULT_PORTS

        return cls(
            targets=_text(data.get("targets"), ""),
            ports=ports,
            all_ports=data.get("all_ports") is True,
            preset=preset,
            protocol=protocol,
            timeout=_timeout_text(data.get("timeout", "1.0")),
            concurrency=_concurrency_text(data.get("concurrency", "1000")),
            show_filtered=data.get("show_filtered") is True,
            version=version,
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: Path) -> AppConfig:
    """Load settings, falling back to safe defaults on any read/parse error."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AppConfig()
    if not isinstance(data, dict):
        return AppConfig()
    return AppConfig.from_mapping(data)


def save_config(path: Path, config: AppConfig) -> None:
    """Atomically persist settings so a crash cannot leave a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.to_mapping(), indent=2, ensure_ascii=False) + "\n"
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(
            file_descriptor, "w", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
