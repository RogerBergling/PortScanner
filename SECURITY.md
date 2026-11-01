# Security Policy

## Supported versions

| Version | Support |
| --- | --- |
| 1.3.x | Current release line; security fixes |
| 1.2.x | Security fixes only |
| < 1.2 | Unsupported |

Only the official binaries published in this repository and builds from tagged
source are supported. Linux builds use the host's Python and Tk packages, so
their security also depends on the operating system vendor.

## Reporting a vulnerability

Do **not** open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting:

1. Open the repository's **Security** tab.
2. Select **Advisories** → **Report a vulnerability**.
3. Include:
   - Affected version and operating system
   - Whether you used the GUI, `portscanner scan`, or the Windows executables
   - Reproduction steps or a minimal proof of concept
   - Impact and any known mitigations

If private reporting is unavailable, contact the repository owner through
GitHub and request a private channel before sharing details.

## Response targets

- Initial acknowledgement: 3 business days
- Triage and severity assessment: 7 business days
- Fix or mitigation: based on severity and exploitability

These are targets, not a commercial service-level agreement. No bug bounty is
currently offered.

## Scope

In scope:

- The Python source in `src/portscanner/`
- The Linux `portscanner` zipapp
- `PortScanner.exe` and `PortScannerCLI.exe`
- Build, release, and CI configuration in `.github/`

Out of scope:

- Vulnerabilities in the host operating system, Python, Tcl/Tk, or network
  infrastructure
- Findings that require running the scanner with administrator/root privileges
- Social engineering or physical access
- Unauthorized scanning of third-party systems

## Binary verification and signing

Release checksums are published in [`SHA256SUMS`](SHA256SUMS). The Windows
executables are currently **unsigned**, so Windows SmartScreen may warn. Verify
the SHA-256 hash before execution.

## Security posture

- No third-party Python packages are used at runtime.
- The Windows executables are built with a pinned, currently supported Python
  runtime and PyInstaller version.
- Build dependencies are pinned and audited with `pip-audit` in CI.
- GitHub Actions are pinned to commit SHAs and checked by Dependabot.
- Configuration writes are validated and atomic.
- The application does not contain telemetry or automatic update calls.

See [`docs/ENTERPRISE.md`](docs/ENTERPRISE.md) for deployment and compliance
considerations.

## Legal use

Only scan systems you own or are explicitly authorized to test. Unauthorized
port scanning may be illegal. The maintainers are not responsible for misuse.
