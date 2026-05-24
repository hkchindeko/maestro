"""Typer CLI entry point for Maestro."""

from __future__ import annotations

from pathlib import Path

import typer

from maestro.cli import config as config_cmd

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

    config = resolve_config(definition)
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

    # Resolve server port: CLI --port overrides server.port config
    effective_port = port if port is not None else config.server.port

    if effective_port is not None:
        typer.echo(f"Starting HTTP server on 127.0.0.1:{effective_port}...")
        # TODO: Start orchestrator and server as asyncio tasks
        from maestro.web.app import start_server
        import asyncio

        # Placeholder state — orchestrator will provide the real state
        from maestro.core.state import OrchestratorState
        state = OrchestratorState()

        asyncio.run(start_server(state, effective_port))
    else:
        typer.echo("Starting Maestro service...")
        # TODO: Start orchestrator event loop


if __name__ == "__main__":
    app()
