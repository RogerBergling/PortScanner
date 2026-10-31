from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from portscanner.config import (
    AppConfig,
    CONFIG_VERSION,
    DEFAULT_PORTS,
    config_directory,
    load_config,
    save_config,
)


class ConfigDirectoryTests(unittest.TestCase):
    def test_linux_default_location(self) -> None:
        path = config_directory(
            platform="linux",
            environ={"XDG_CONFIG_HOME": ""},
            home=Path("/home/tester"),
        )
        self.assertEqual(path, Path("/home/tester/.config/portscanner"))

    def test_linux_absolute_xdg_override(self) -> None:
        path = config_directory(
            platform="linux",
            environ={"XDG_CONFIG_HOME": "/opt/config"},
            home=Path("/home/tester"),
        )
        self.assertEqual(path, Path("/opt/config/portscanner"))

    def test_linux_relative_xdg_override_is_ignored(self) -> None:
        path = config_directory(
            platform="linux",
            environ={"XDG_CONFIG_HOME": "relative/path"},
            home=Path("/home/tester"),
        )
        self.assertEqual(path, Path("/home/tester/.config/portscanner"))

    def test_windows_uses_appdata(self) -> None:
        path = config_directory(
            platform="win32",
            environ={"APPDATA": "/tmp/appdata"},
            home=Path("/home/tester"),
        )
        self.assertEqual(path, Path("/tmp/appdata") / "portscanner")

    def test_windows_falls_back_to_roaming_appdata(self) -> None:
        path = config_directory(
            platform="win32",
            environ={"APPDATA": ""},
            home=Path("/home/tester"),
        )
        self.assertEqual(
            path, Path("/home/tester") / "AppData" / "Roaming" / "portscanner"
        )


class AppConfigTests(unittest.TestCase):
    def test_defaults_are_safe(self) -> None:
        config = AppConfig()
        self.assertEqual(config.ports, DEFAULT_PORTS)
        self.assertEqual(config.protocol, "TCP")
        self.assertEqual(config.timeout, "1.0")
        self.assertEqual(config.concurrency, "1000")
        self.assertFalse(config.all_ports)
        self.assertFalse(config.show_filtered)
        self.assertEqual(config.version, CONFIG_VERSION)

    def test_invalid_values_are_normalized(self) -> None:
        config = AppConfig.from_mapping(
            {
                "targets": 123,
                "ports": "   ",
                "all_ports": "yes",
                "preset": "Not a preset",
                "protocol": "ICMP",
                "timeout": "nope",
                "concurrency": "99999",
                "show_filtered": 1,
                "version": 999,
            }
        )
        self.assertEqual(config.targets, "")
        self.assertEqual(config.ports, DEFAULT_PORTS)
        self.assertFalse(config.all_ports)
        self.assertEqual(config.preset, "Custom")
        self.assertEqual(config.protocol, "TCP")
        self.assertEqual(config.timeout, "1.0")
        self.assertEqual(config.concurrency, "1000")
        self.assertFalse(config.show_filtered)
        self.assertEqual(config.version, CONFIG_VERSION)

    def test_valid_values_are_preserved(self) -> None:
        config = AppConfig.from_mapping(
            {
                "targets": "192.0.2.1",
                "ports": "1-1024",
                "all_ports": False,
                "preset": "Custom",
                "protocol": "TCP + UDP",
                "timeout": "2,5",
                "concurrency": "2500",
                "show_filtered": True,
                "version": 1,
            }
        )
        self.assertEqual(config.targets, "192.0.2.1")
        self.assertEqual(config.ports, "1-1024")
        self.assertEqual(config.protocol, "TCP + UDP")
        self.assertEqual(config.timeout, "2,5")
        self.assertEqual(config.concurrency, "2500")
        self.assertTrue(config.show_filtered)


class ConfigPersistenceTests(unittest.TestCase):
    def test_missing_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(Path(directory) / "missing.json")
        self.assertEqual(config, AppConfig())

    def test_malformed_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{not json", encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config, AppConfig())

    def test_round_trip_and_atomic_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "config.json"
            config = AppConfig(
                targets="192.0.2.0/24",
                ports="22,80,443",
                protocol="UDP",
                timeout="0.5",
                concurrency="100",
                show_filtered=True,
            )
            save_config(path, config)
            loaded = load_config(path)
            entries = list(path.parent.iterdir())
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded, config)
        self.assertEqual(entries, [path])
        self.assertEqual(data["version"], CONFIG_VERSION)

    def test_save_replaces_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config(path, AppConfig(targets="192.0.2.1"))
            save_config(path, AppConfig(targets="192.0.2.2"))
            loaded = load_config(path)
        self.assertEqual(loaded.targets, "192.0.2.2")


if __name__ == "__main__":
    unittest.main()
