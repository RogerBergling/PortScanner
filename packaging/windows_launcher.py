"""Entry point used by PyInstaller when building the Windows executable."""

from portscanner.app import cli

if __name__ == "__main__":
    cli()
