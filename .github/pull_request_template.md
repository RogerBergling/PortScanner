## Summary

<!-- What changed and why? -->

## Security and compatibility

<!-- Any security, exit-code, output-format, or config-schema impact? -->

## Validation

- [ ] `make test`
- [ ] `make lint`
- [ ] CI matrix is green
- [ ] GUI/CLI behavior checked manually where relevant
- [ ] Windows build workflow successful, if binaries changed

## Release checklist

- [ ] Version updated in `src/portscanner/__init__.py`
- [ ] `CHANGELOG.md` updated
- [ ] `portscanner`, `PortScanner.exe`, and `PortScannerCLI.exe` rebuilt if source changed
- [ ] `SHA256SUMS` updated and verified
- [ ] Security implications reviewed
