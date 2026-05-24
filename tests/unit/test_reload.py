"""Tests for dynamic reload behavior (task 5.4)."""

from __future__ import annotations

from pathlib import Path


from maestro.core.config import WorkflowConfig
from maestro.core.reload import WorkflowReloadHandler, WorkflowWatcher
from maestro.core.workflow import (
    WorkflowDefinition,
    load_workflow,
    resolve_config,
)


class TestWorkflowReloadHandler:
    """Tests for reload handler behavior."""

    def test_reload_on_valid_change(self, tmp_path: Path) -> None:
        """Valid file change triggers successful reload with callback."""
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\ntracker:\n  kind: linear\n  project_slug: test\n---\nbody")

        reload_events: list[tuple[WorkflowConfig, WorkflowDefinition]] = []

        def on_reload(config: WorkflowConfig, definition: WorkflowDefinition) -> None:
            reload_events.append((config, definition))

        handler = WorkflowReloadHandler(workflow, on_reload)

        # Simulate a file modification event
        from watchdog.events import FileModifiedEvent

        event = FileModifiedEvent(str(workflow))
        handler.on_modified(event)

        assert len(reload_events) == 1
        config, definition = reload_events[0]
        assert config.tracker.kind == "linear"
        assert config.tracker.project_slug == "test"

    def test_reload_on_invalid_change_keeps_last_good(self, tmp_path: Path) -> None:
        """Invalid file change triggers error callback, last good config preserved."""
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\ntracker:\n  kind: linear\n  project_slug: test\n---\nbody")

        reload_events: list[tuple[WorkflowConfig, WorkflowDefinition]] = []
        error_events: list[Exception] = []

        def on_reload(config: WorkflowConfig, definition: WorkflowDefinition) -> None:
            reload_events.append((config, definition))

        def on_error(exc: Exception) -> None:
            error_events.append(exc)

        handler = WorkflowReloadHandler(workflow, on_reload, on_error)

        # First, load valid config
        definition = load_workflow(workflow)
        config = resolve_config(definition)
        on_reload(config, definition)

        # Write invalid YAML to the file
        workflow.write_text("---\n- invalid: [unclosed\n---\nbody")

        # Simulate modification
        from watchdog.events import FileModifiedEvent

        event = FileModifiedEvent(str(workflow))
        handler.on_modified(event)

        # Error callback should have been triggered
        assert len(error_events) == 1
        assert isinstance(error_events[0], Exception)

        # Last good config should still be in reload_events (from initial load)
        assert len(reload_events) == 1
        assert reload_events[0][0].tracker.kind == "linear"

    def test_reload_ignores_unrelated_files(self, tmp_path: Path) -> None:
        """Handler ignores events for files other than the watched workflow."""
        workflow = tmp_path / "WORKFLOW.md"
        other_file = tmp_path / "other.txt"
        workflow.write_text("---\n---\nbody")
        other_file.write_text("other content")

        reload_count = 0

        def on_reload(config: WorkflowConfig, definition: WorkflowDefinition) -> None:
            nonlocal reload_count
            reload_count += 1

        handler = WorkflowReloadHandler(workflow, on_reload)

        from watchdog.events import FileModifiedEvent

        event = FileModifiedEvent(str(other_file))
        handler.on_modified(event)

        assert reload_count == 0


class TestWorkflowWatcher:
    """Tests for watcher lifecycle."""

    def test_start_and_stop(self, tmp_path: Path) -> None:
        """Watcher can be started and stopped without errors."""
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n---\nbody")

        def on_reload(config: WorkflowConfig, definition: WorkflowDefinition) -> None:
            pass

        watcher = WorkflowWatcher(workflow, on_reload)
        watcher.start()
        watcher.stop()

    def test_reload_now_returns_config_on_success(self, tmp_path: Path) -> None:
        """Manual reload returns config and definition on success."""
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\ntracker:\n  kind: linear\n  project_slug: test\n---\nbody")

        reload_events: list[tuple[WorkflowConfig, WorkflowDefinition]] = []

        def on_reload(config: WorkflowConfig, definition: WorkflowDefinition) -> None:
            reload_events.append((config, definition))

        watcher = WorkflowWatcher(workflow, on_reload)
        result = watcher.reload_now()

        assert result is not None
        config, definition = result
        assert config.tracker.kind == "linear"
        assert len(reload_events) == 1

    def test_reload_now_returns_none_on_failure(self, tmp_path: Path) -> None:
        """Manual reload returns None on failure."""
        workflow = tmp_path / "WORKFLOW.md"
        workflow.write_text("---\n- invalid: [unclosed\n---\nbody")

        error_events: list[Exception] = []

        def on_reload(config: WorkflowConfig, definition: WorkflowDefinition) -> None:
            pass

        def on_error(exc: Exception) -> None:
            error_events.append(exc)

        watcher = WorkflowWatcher(workflow, on_reload, on_error=on_error)
        result = watcher.reload_now()

        assert result is None
        assert len(error_events) == 1
