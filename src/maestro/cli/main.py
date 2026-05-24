"""Typer CLI entry point for Maestro."""

from __future__ import annotations

from pathlib import Path

import typer

from maestro.cli import config as config_cmd
from maestro.runtime import RuntimeCompositionError, apply_cli_overrides, run_runtime

app = typer.Typer(
    name="maestro",
    help="Orchestrate coding agents to execute issue tracker work autonomously.",
    add_completion=False,
)

app.add_typer(config_cmd.app, name="config")


@app.command()
def run(
    workflow: Path | None = typer.Argument(
        None,
        help="Path to WORKFLOW.md file (default: ./WORKFLOW.md)",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="Enable HTTP dashboard on specified port",
    ),
    tracker_kind: str | None = typer.Option(
        None,
        "--tracker-kind",
        help="Override tracker.kind from workflow",
    ),
    agent_kind: str | None = typer.Option(
        None,
        "--agent-kind",
        help="Override agent.kind from workflow",
    ),
    sandbox_kind: str | None = typer.Option(
        None,
        "--sandbox-kind",
        help="Override sandbox.kind from workflow",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose logging",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate configuration without starting the service",
    ),
) -> None:
    """Start the Maestro orchestration service."""
    import logging

    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    from maestro.core.validation import validate_dispatch_config
    from maestro.core.workflow import load_workflow, resolve_config

    try:
        definition = load_workflow(workflow)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    config = apply_cli_overrides(
        resolve_config(definition),
        tracker_kind=tracker_kind,
        agent_kind=agent_kind,
        sandbox_kind=sandbox_kind,
        port=port,
    )
    result = validate_dispatch_config(config, definition)

    if not result.ok:
        typer.echo("Configuration validation failed:", err=True)
        for error in result.errors:
            typer.echo(f"  - {error}", err=True)
        raise typer.Exit(1)

    typer.echo("Configuration valid.")

    if dry_run:
        typer.echo("Dry run complete. No work dispatched.")
        raise typer.Exit(0)

    typer.echo("Starting Maestro service...")
    if config.server.port is not None:
        typer.echo(f"Starting HTTP server on 127.0.0.1:{config.server.port}...")

    import asyncio

    try:
        asyncio.run(run_runtime(definition=definition, config=config, port=config.server.port))
    except RuntimeCompositionError as e:
        typer.echo(f"Runtime composition failed: {e}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        typer.echo(f"Runtime failed: {e}", err=True)
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
