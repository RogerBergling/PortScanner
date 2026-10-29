# PortScanner

Fast TCP/UDP port scanner for Linux with a graphical interface.

PortScanner uses asynchronous connect scans, so it needs **no root privileges**
and starts scanning immediately. Enter one or more targets, choose ports and a
protocol, and watch results appear live.

![status](https://img.shields.io/badge/platform-Linux-blue)

## Features

- Single IPs, CIDR networks, address ranges, hostnames, or a mixture
  (for example `192.168.1.0/24, 10.0.0.5-10`, `example.com`)
- TCP, UDP, or both at the same time
- Custom port lists and ranges, "common ports", "web servers",
  "well-known" and all 65,535 ports
- High concurrency (up to 5,000 probes in flight) with configurable timeout
- Live progress, scan rate, open-port counter and result table
- Sortable results, copy selected `host:port/protocol` entries with `Ctrl+C`,
  export to CSV
- Settings are remembered between runs
- Single-file executable named `portscanner`

## Requirements

- Linux with a graphical session (X11 or Wayland; Tkinter is used)
- Python **3.11+** with Tkinter
- No third-party Python packages are required

Install the Tkinter bindings if they are missing:

```bash
# Fedora
sudo dnf install python3-tkinter

# Debian / Ubuntu
sudo apt install python3-tk

# Arch
sudo pacman -S tk
```

## Build and run

```bash
make build       # creates ./portscanner
./portscanner
```

Install it system-wide:

```bash
sudo make install          # /usr/local/bin/portscanner
# or a custom prefix:
sudo make install PREFIX=/usr
```

Then start it from a terminal with `portscanner`, or from your desktop
environment's application launcher.

Run the test suite:

```bash
make test
```

The tests use only the Python standard library and do not require a display.

## Windows 11

A ready-to-run 64-bit `PortScanner.exe` is included in the repository. It is a
self-contained build, so Python and Tkinter do not need to be installed. The
executable is produced by the
[Windows build](.github/workflows/windows-build.yml) GitHub Actions workflow
using PyInstaller.

The executable is unsigned, so Windows SmartScreen may ask for confirmation the
first time it is started.

## How to use

1. **Targets** — enter an IP address, network, range or hostname. Separate
   multiple entries with commas or spaces:
   - `192.168.1.10`
   - `192.168.1.0/24` (network and broadcast addresses are skipped)
   - `10.0.0.5-10.0.0.25` or `10.0.0.5-25`
   - `example.com`
2. **Ports** — type a list (`22,80,443`), ranges (`1-1024`), use a preset, or
   tick **All 65,535**.
3. **Protocol** — choose **TCP**, **UDP**, or **TCP + UDP**.
4. Adjust **Timeout** and **Concurrency** if needed and press **Start scan**.
5. Open ports are listed while the scan runs. Use **Save CSV…** afterwards.

Keyboard shortcuts: `Enter` starts a scan, `Esc` stops it, `Ctrl+C` copies the
selected addresses.

### UDP scans

UDP has no handshake, so a UDP scan sends a small probe and waits for a reply:

- **open** — the service answered
- **open|filtered** — no answer before the timeout (enable
  *Show UDP open|filtered* to include these rows)

A UDP scan is naturally slower and less definitive than a TCP scan. A timeout
of 1 second or more is recommended.

### Large scans

The GUI warns before starting more than 2,000,000 probes. A `/24` with all
65,535 ports and both protocols is over 33 million probes and can take hours.
For quick results, start with the **Common ports** preset.

## Notes

- The scanner performs TCP connect scans and connected UDP probes. It does not
  require root and does not send raw packets or SYN scans.
- Scans are limited to 65,536 targets per run to keep the interface usable.
- Settings are stored in `$XDG_CONFIG_HOME/portscanner/config.json`
  (default: `~/.config/portscanner/config.json`).
- Only scan systems you own or are explicitly authorized to test. Unauthorized
  port scanning may be illegal in your jurisdiction.

## Project layout

```text
src/portscanner/
  app.py       Tkinter interface and result handling
  engine.py    asyncio TCP/UDP scan engine
  ports.py     port parsing and presets
  targets.py   target expansion (IP, CIDR, ranges, DNS)
packaging/
  windows_launcher.py  PyInstaller entry point for PortScanner.exe
tests/         unit and integration tests
.github/       Windows 11 build workflow
Makefile       build, test, install
```
