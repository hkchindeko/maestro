"""CLI subcommands for config inspection and validation."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="config",
    help="Inspect and validate workflow configuration.",
)

console = Console()


@app.command("validate")
def validate(
    workflow: Path | None = typer.Argument(
        None,
        help="Path to WORKFLOW.md file (default: ./WORKFLOW.md)",
    ),
) -> None:
    """Validate a workflow file and report errors."""
    from maestro.core.validation import validate_dispatch_config
    from maestro.core.workflow import WorkflowLoadError, load_workflow, resolve_config

    try:
        definition = load_workflow(workflow)
    except WorkflowLoadError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    config = resolve_config(definition)
    result = validate_dispatch_config(config, definition)

    if result.ok:
        console.print("[green]✓ Configuration is valid[/green]")
    else:
        console.print("[red]✗ Configuration validation failed:[/red]")
        for error in result.errors:
            console.print(f"  [red]-[/red] {error}")
        raise typer.Exit(1)


@app.command("show")
def show(
    workflow: Path | None = typer.Argument(
        None,
        help="Path to WORKFLOW.md file (default: ./WORKFLOW.md)",
    ),
) -> None:
    """Show resolved workflow configuration with defaults applied."""
    from maestro.core.workflow import WorkflowLoadError, load_workflow, resolve_config

    try:
        definition = load_workflow(workflow)
    except WorkflowLoadError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    config = resolve_config(definition)

    console.print(f"[bold]Workflow:[/bold] {definition.workflow_path}")
    console.print()

    # Tracker config
    table = Table(title="Tracker Config")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("kind", config.tracker.kind or "(not set)")
    table.add_row("endpoint", config.tracker.endpoint or "(default)")
    table.add_row("api_key", "***" if config.tracker.api_key else "(not set)")
    table.add_row("project_slug", config.tracker.project_slug or "(not set)")
    table.add_row("active_states", ", ".join(config.tracker.active_states))
    table.add_row("terminal_states", ", ".join(config.tracker.terminal_states))
    console.print(table)
    console.print()

    # Polling config
    table = Table(title="Polling Config")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("interval_ms", str(config.polling.interval_ms))
    console.print(table)
    console.print()

    # Workspace config
    table = Table(title="Workspace Config")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("root", config.workspace.root or "(default: system temp)")
    console.print(table)
    console.print()

    # Agent config
    table = Table(title="Agent Config")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("kind", config.agent.kind)
    table.add_row("command", config.agent.command or "(default)")
    table.add_row("max_concurrent_agents", str(config.agent.max_concurrent_agents))
    table.add_row("max_turns", str(config.agent.max_turns))
    table.add_row("max_retry_backoff_ms", str(config.agent.max_retry_backoff_ms))
    console.print(table)
