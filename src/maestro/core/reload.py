"""Dynamic WORKFLOW.md reload via watchdog.

Implements SPEC §6.2 (Dynamic Reload Semantics).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from maestro.core.config import WorkflowConfig
from maestro.core.workflow import (
    WorkflowDefinition,
    WorkflowLoadError,
    load_workflow,
    resolve_config,
)

logger = logging.getLogger(__name__)

ReloadCallback = Callable[[WorkflowConfig, WorkflowDefinition], None]
ErrorCallback = Callable[[Exception], None]


class WorkflowReloadHandler(FileSystemEventHandler):
    """Watchdog handler that reloads WORKFLOW.md on change."""

    def __init__(
        self,
        workflow_path: Path,
        on_reload: ReloadCallback,
        on_error: ErrorCallback | None = None,
    ) -> None:
        """Initialize the reload handler.

        Args:
            workflow_path: Absolute path to the workflow file to watch.
            on_reload: Callback invoked with new config and definition on successful reload.
            on_error: Callback invoked on reload failure. Receives the exception.
        """
        super().__init__()
        self._workflow_path = workflow_path
        self._on_reload = on_reload
        self._on_error = on_error

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.src_path != str(self._workflow_path):
            return
        self._reload()

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events (e.g., atomic writes)."""
        if event.dest_path == str(self._workflow_path):
            self._reload()

    def _reload(self) -> None:
        """Attempt to reload the workflow file."""
        try:
            definition = load_workflow(self._workflow_path)
            config = resolve_config(definition)
            logger.info("Workflow reloaded: %s", self._workflow_path)
            self._on_reload(config, definition)
        except (WorkflowLoadError, ValueError) as e:
            logger.warning("Workflow reload failed, keeping last known good config: %s", e)
            if self._on_error:
                self._on_error(e)


class WorkflowWatcher:
    """Manages the watchdog observer for WORKFLOW.md."""

    def __init__(
        self,
        workflow_path: Path,
        on_reload: ReloadCallback,
        on_error: ErrorCallback | None = None,
    ) -> None:
        """Initialize the workflow watcher.

        Args:
            workflow_path: Absolute path to the workflow file to watch.
            on_reload: Callback invoked with new config and definition on successful reload.
            on_error: Callback invoked on reload failure.
        """
        self._workflow_path = workflow_path
        self._observer = Observer()
        self._handler = WorkflowReloadHandler(workflow_path, on_reload, on_error)

    def start(self) -> None:
        """Start watching the workflow file for changes."""
        watch_dir = str(self._workflow_path.parent)
        self._observer.schedule(self._handler, watch_dir, recursive=False)
        self._observer.start()
        logger.info("Watching workflow file: %s", self._workflow_path)

    def stop(self) -> None:
        """Stop watching the workflow file."""
        self._observer.stop()
        self._observer.join()

    def reload_now(self) -> tuple[WorkflowConfig, WorkflowDefinition] | None:
        """Manually trigger a reload.

        Returns:
            Tuple of (config, definition) on success, None on failure.
        """
        try:
            definition = load_workflow(self._workflow_path)
            config = resolve_config(definition)
            self._handler._on_reload(config, definition)
            return config, definition
        except (WorkflowLoadError, ValueError) as e:
            logger.warning("Manual reload failed: %s", e)
            if self._handler._on_error:
                self._handler._on_error(e)
            return None
