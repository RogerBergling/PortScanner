"""Entry point used by PyInstaller when building the Windows CLI executable."""

from portscanner.cli import cli

if __name__ == "__main__":
    cli()
