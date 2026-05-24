"""FastAPI application factory for the HTTP dashboard extension.

Implements SPEC §13.7 OPTIONAL HTTP server extension.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from maestro.core.state import OrchestratorState

RefreshCallback = Callable[[], Awaitable[None] | None]


def _error_envelope(code: str, message: str) -> dict:
    """Build a SPEC §13.7 error envelope."""
    return {"error": {"code": code, "message": message}}


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Custom handler that wraps HTTPException in SPEC-conformant error envelope."""
    if not isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=500,
            content=_error_envelope("internal_error", str(exc) if exc else ""),
        )

    # Map status codes to error codes
    code_map = {404: "issue_not_found", 405: "method_not_allowed", 422: "validation_error"}
    error_code = code_map.get(exc.status_code, "error")

    # If detail is already an error dict, use it directly
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(error_code, str(detail) if detail else ""),
    )


class ErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    """Middleware that ensures 405 and other error responses use SPEC-conformant envelopes.

    Starlette's built-in 405 handling returns a plain dict, bypassing the
    custom HTTPException handler. This middleware catches those and rewraps them.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code >= 400 and response.status_code < 500:
            # Check if the response needs rewrapping
            try:
                body = response.body
                if body:
                    import json
                    data = json.loads(body)
                    # If it's a Starlette-style error (has "detail" but no "error"), rew wrap
                    if "detail" in data and "error" not in data:
                        code_map = {
                            404: "issue_not_found",
                            405: "method_not_allowed",
                            422: "validation_error",
                        }
                        error_code = code_map.get(response.status_code, "error")
                        new_content = _error_envelope(error_code, str(data["detail"]))
                        return JSONResponse(
                            status_code=response.status_code,
                            content=new_content,
                        )
            except Exception:
                pass
        return response


def create_app(
    state: OrchestratorState,
    refresh_callback: RefreshCallback | None = None,
) -> FastAPI:
    """Create a FastAPI application wired to an orchestrator state.

    Args:
        state: The orchestrator's runtime state for building snapshots.
        refresh_callback: Optional callback invoked by POST /api/v1/refresh.

    Returns:
        A configured FastAPI application instance.
    """
    app = FastAPI(
        title="Maestro Dashboard",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    # Register custom error envelope handlers
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_middleware(ErrorEnvelopeMiddleware)

    # Store state reference on the app for route handlers to access
    app.state.maestro_state = state
    app.state.refresh_callback = refresh_callback
    app.state.refresh_pending = False
    app.state.refresh_task = None

    # Import and register routes
    from maestro.web.routes import router

    app.include_router(router)

    # Import and register dashboard route
    from maestro.web.dashboard import dashboard_router

    app.include_router(dashboard_router)

    return app


async def start_server(
    state: OrchestratorState,
    port: int,
    refresh_callback: RefreshCallback | None = None,
) -> None:
    """Start the uvicorn HTTP server as an asyncio task.

    Binds to loopback (127.0.0.1) by default per SPEC §13.7.

    Args:
        state: The orchestrator's runtime state.
        port: The port to bind to. 0 requests an ephemeral port.
        refresh_callback: Optional callback invoked by POST /api/v1/refresh.
    """
    app = create_app(state, refresh_callback=refresh_callback)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
