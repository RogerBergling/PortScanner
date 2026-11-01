# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
semantic versioning.

## [1.3.0] - 2026-11-01

### Added

- Version, build number, and build timestamp in the GUI header.
- Build metadata in `--version` output and the README main page.
- Centralized release metadata in `build_info.py`.
- README screenshots captured from the real GUI and CLI.

## [1.2.0] - 2026-10-31

### Added

- MIT license.
- Validated, versioned application configuration with atomic writes.
- Security policy, contribution guide, architecture and enterprise deployment
  documentation.
- Third-party notices for the runtime and build toolchain.
- CodeQL scanning workflow and pull-request template.
- Enterprise hardening guidance and release governance.

### Changed

- Configuration is now loaded through `portscanner.config` instead of ad-hoc
  JSON handling in the GUI.
- Invalid or stale configuration values fall back to safe defaults.
- Configuration writes are atomic and user-private.

## [1.1.0] - 2026-10-31

### Added

- Headless `portscanner scan` command with text, CSV, and JSON output.
- `--fail-on-open`, `--quiet`, `--yes`, and explicit exit codes.
- `PortScannerCLI.exe` console build for Windows.
- Linux/Windows CI matrix on Python 3.11 and 3.14.
- Ruff linting and `make lint` / `make check` targets.

### Fixed

- Windows GUI subtitle no longer says the application is Linux-only.

## [1.0.3] - 2026-10-30

### Added

- SHA-256 checksums for release binaries.
- Dependency audit and Dependabot configuration.
- Windows CLI and GUI build hardening.

### Changed

- Windows runtime updated to Python 3.14.10 and Tcl/Tk 9.0.4.
- Linux zipapp rebuilt.

## [1.0.2] - 2026-10-29

### Added

- Windows 11 support and PyInstaller build workflow.
- Windows-specific `SO_LINGER` and `%APPDATA%` configuration handling.

## [1.0.1] - 2026-10-29

### Fixed

- Scan configuration validation.
- Inconsistent target estimates and malformed range errors.
- XDG configuration path handling.
- Zipapp exit-code propagation.
- Unknown CLI argument handling and stopping-status UI.

## [1.0.0] - 2026-10-23

### Added

- Initial Linux Tkinter port scanner.
- TCP/UDP connect scanning, target expansion, port presets, CSV export, and
  remembered settings.
