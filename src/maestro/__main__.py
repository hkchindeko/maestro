"""Allow running Maestro as a module: python -m maestro."""

from maestro.cli.main import app

if __name__ == "__main__":
    app()
