# Third-party notices

PortScanner itself is licensed under the [MIT license](LICENSE). It has no
third-party Python runtime packages. The distributed binaries include the
following components:

## CPython

- Project: https://www.python.org/
- License: Python Software Foundation License Agreement
- Included in: `portscanner` (indirectly, via the host interpreter),
  `PortScanner.exe`, `PortScannerCLI.exe`

## Tcl/Tk

- Project: https://www.tcl-lang.org/
- License: BSD-style Tcl/Tk license
- Included in: `PortScanner.exe` through Tkinter and the Python Windows runtime

## PyInstaller

- Project: https://pyinstaller.org/
- License: GPLv2-or-later with the PyInstaller bootloader exception, which
  permits building and distributing non-free and commercial applications
- Included in: `PortScanner.exe`, `PortScannerCLI.exe` (bootloader and build
  tooling)

## GitHub Actions

GitHub Actions used by CI are build-time infrastructure and are not shipped in
the binaries. The workflows pin action revisions by commit SHA.

## Runtime package inventory

Declared runtime dependencies: **none** beyond CPython and Tcl/Tk.

Build dependencies are listed in `requirements-build.txt`; CI-only tooling is
listed in `requirements-dev.txt`.

## Legal review

This notice is provided for engineering transparency and is not legal advice.
Review the upstream license texts and your distribution obligations with legal
counsel before commercial redistribution.
