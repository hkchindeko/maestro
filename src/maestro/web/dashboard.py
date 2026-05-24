"""Server-rendered HTML dashboard.

Implements SPEC §13.7.1: Human-readable dashboard at /.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from maestro.observability.snapshot import SnapshotBuilder

dashboard_router = APIRouter()

# Jinja2 environment pointing at the templates directory
_templates_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_templates_dir)), autoescape=True)


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Serve the human-readable dashboard.

    Per SPEC §13.7.1.
    """
    state = request.app.state.maestro_state
    builder = SnapshotBuilder()

    snapshot = builder.build(
        state=state,
        running=state.running,
        retrying=state.retry_attempts,
        totals=state.codex_totals,
        rate_limits=state.codex_rate_limits,
    )

    template = _jinja_env.get_template("dashboard.html")
    html = template.render(
        running=snapshot.running,
        retrying=snapshot.retrying,
        codex_totals=snapshot.codex_totals,
        rate_limits=snapshot.rate_limits,
        running_count=len(snapshot.running),
        retrying_count=len(snapshot.retrying),
    )

    return HTMLResponse(content=html)