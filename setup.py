#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["typer>=0.20,<1"]
# ///
"""Bootstrap the development environment with uv and prek."""

import os
import shutil

# The setup command uses fixed arguments and does not invoke a shell.
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path

import typer

PROJECT_ROOT = Path(__file__).resolve().parent
app = typer.Typer(add_completion=False)


@app.command()
def main() -> None:
    """Create the venv, sync locked dependencies, and install commit hooks.

    Raises:
        typer.Exit: If uv is missing or a setup command fails.
    """
    uv = shutil.which("uv")
    if uv is None:
        typer.echo("Install uv first: https://docs.astral.sh/uv/getting-started/installation/", err=True)
        raise typer.Exit(code=1)

    commands = []
    if not (PROJECT_ROOT / ".venv").exists():
        commands.append([uv, "venv", ".venv"])
    commands.extend([[uv, "sync", "--locked"], [uv, "run", "--locked", "prek", "install"]])

    # The PEP 723 bootstrap environment is separate from the project environment.
    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)

    for command in commands:
        typer.echo(f"Running: {' '.join(command)}")
        try:
            # The executable is resolved above; arguments are fixed and no shell is used.
            subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                command, cwd=PROJECT_ROOT, check=True, env=environment
            )
        except subprocess.CalledProcessError as exc:
            typer.echo(f"Setup failed: {' '.join(command)} (exit {exc.returncode})", err=True)
            raise typer.Exit(code=exc.returncode) from exc

    typer.echo("Development environment ready. Run checks with: uv run prek run --all-files")


if __name__ == "__main__":
    app()
