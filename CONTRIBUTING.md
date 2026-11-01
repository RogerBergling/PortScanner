# Contributing

## Development setup

Requirements:

- Python 3.11 or newer with Tkinter
- `make`
- Ruff for linting

```bash
git clone https://github.com/RogerBergling/PortScanner.git
cd PortScanner
python3 -m pip install -r requirements-dev.txt
make run
```

There are no third-party runtime dependencies. Avoid adding one unless it is
essential and has been reviewed for license, maintenance, and security impact.

## Tests and checks

```bash
make test
make lint
make check      # lint + tests
```

The test suite must pass on Linux and Windows. CI also covers Python 3.11 and
3.14. New behavior needs tests; parser and CLI changes should include invalid
input and edge-case coverage.

## Code style

- Ruff configuration lives in `pyproject.toml`.
- Keep public functions typed.
- Prefer small modules and pure functions where practical.
- Do not silently swallow exceptions unless the behavior is documented.
- Preserve the no-root, connect-scan design.

## CLI and output compatibility

- Keep exit codes stable: `0` success, `1` findings/failure, `2` usage error,
  `130` interrupted.
- Treat CSV/JSON field names and text output as user-facing interfaces.
- Add new output formats or flags in a backward-compatible way.

## Windows executables

The checked-in executables are release artifacts. Rebuild them through the
`Windows build` GitHub Actions workflow, not by hand on an unverified machine.
After a rebuild:

1. Download the artifact from the workflow run.
2. Verify both executables and the generated checksums.
3. Update `PortScanner.exe`, `PortScannerCLI.exe`, and `SHA256SUMS` together.
4. Run the Windows smoke tests from the workflow.

## Versioning and changelog

- Follow semantic versioning.
- Update `src/portscanner/__init__.py`, `build_info.py`, and `CHANGELOG.md`.
- Rebuild the Linux zipapp and Windows executables for release changes.
- Update `SHA256SUMS` whenever a committed binary changes.

## Pull requests

Include:

- What changed and why
- Security or compatibility impact
- Tests run
- Version/changelog impact, if any
- Rebuilt artifact hashes, if binaries changed

Keep pull requests focused. Do not mix refactors, behavior changes, and binary
updates without a clear reason.

## Security

Do not report vulnerabilities in public issues. Follow
[SECURITY.md](SECURITY.md).

## License

PortScanner is released under the [MIT license](LICENSE). By contributing, you
agree that your contributions are provided under the same license. Ensure that
you have the right to submit any code, assets, or documentation you add.
