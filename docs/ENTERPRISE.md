# Enterprise deployment and assurance

## Deployment options

### Windows 11

- `PortScanner.exe` — graphical interface
- `PortScannerCLI.exe` — console automation
- Both are self-contained and run without Python installed.
- Run as a standard user; administrator rights are not required.
- Verify hashes in `SHA256SUMS` before deployment.

### Linux

- `portscanner` zipapp requires Python 3.11+ and Tkinter.
- Prefer distribution-managed Python and Tk packages so security updates are
  handled by the OS.
- `portscanner scan` works without a display.

## Recommended operating model

1. **Authorize scope through change control.** The tool has no built-in target
   allowlist. Use a wrapper or CI job that validates targets against an approved
   inventory before invoking the scanner.
2. **Use the CLI for automation.** Prefer JSON output and exit codes over screen
   scraping:

   ```bash
   portscanner scan 10.20.0.0/24 --ports common --format json -o scan.json
   ```

3. **Treat exit codes as policy signals:**
   - `0` scan completed and no `--fail-on-open` finding
   - `1` open port found with `--fail-on-open`, or runtime failure
   - `2` invalid target/port/config or large-scan guard
   - `130` interrupted

4. **Run from a controlled network position.** The scanner uses connect scans;
   results reflect reachability from the host and network path used.
5. **Retain scan output outside the tool.** The application does not provide
   centralized result storage, audit trails, or retention controls yet.

## Security controls present

- No runtime third-party Python packages.
- No telemetry, automatic updates, or outbound calls beyond scan probes/DNS.
- User-private, validated, atomic configuration writes.
- Bounded concurrency, bounded UDP receive buffer, explicit timeouts.
- Windows and Linux CI, Ruff, pip-audit, CodeQL, Dependabot, SHA-pinned Actions.
- Release checksums and reproducible build instructions.

## Gaps to address before regulated production use

| Gap | Risk | Recommended action |
| --- | --- | --- |
| Unsigned Windows binaries | SmartScreen warnings; tampering harder to detect | Authenticode sign both executables |
| No built-in target allowlist | User can scan any reachable target | Add scope policy or enforce in wrapper |
| No structured audit log | Hard to prove who scanned what/when | Add JSONL audit logging for CLI and GUI |
| No GUI automation tests | Rendering/interaction regressions | Add Xvfb-based GUI tests |
| No SBOM/attestation | Supply-chain review friction | Generate CycloneDX/SPDX SBOM and artifact attestations |
| Unpinned transitive build deps | Build reproducibility | Add hash-pinned lock file |
| No centralized results | Retention/compliance gap | Export to SIEM/ticketing via wrapper |
| No code signing for Linux | Distribution trust | Package and sign `.deb`/RPM/AppImage |

## Hardening checklist

- Verify `SHA256SUMS` before deployment.
- Run as a non-administrator.
- Keep Windows and Linux Python/Tk installations patched.
- Restrict egress/ingress according to the scanning role.
- Review Dependabot and CodeQL findings before each release.
- Rebuild binaries through the Windows workflow; do not accept locally built
  executables from untrusted machines.
- Restrict repository write access and require review for workflow changes.

## Support lifecycle

The current release line receives security fixes. Older lines are best-effort.
See [SECURITY.md](../SECURITY.md) for reporting and supported versions.

## Procurement notes

- Project license: MIT (see [LICENSE](../LICENSE)).
- Runtime: Python standard library + Tcl/Tk.
- Build tool: PyInstaller (GPLv2-or-later with the PyInstaller bootloader
  exception that permits distribution of non-free/commercial applications).
- GitHub Actions are CI-only and are not shipped in the binaries.
- See [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).

## Roadmap for enterprise readiness

1. Add code signing.
2. Add target allowlist/deny enforcement and structured audit logging.
3. Add GUI integration tests and coverage thresholds.
4. Add SBOM, artifact attestations, and hash-pinned build dependencies.
5. Add Linux packages (.deb/RPM/AppImage) and a Windows installer/MSIX.
6. Add centralized result export (SIEM/webhook) and scan history.
