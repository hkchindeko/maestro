"""HTTP server extension.

Provides FastAPI application factory and server startup for SPEC §13.7.
"""

from maestro.web.app import create_app, start_server

__all__ = ["create_app", "start_server"]
