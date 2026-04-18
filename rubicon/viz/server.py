"""FastAPI visualization server for Rubicon.

Serves a static single-page app at ``/`` and JSON API endpoints
under ``/api/``.  The graph, config, violations, and optional diff
are injected at startup via ``start_server()`` or ``configure()``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import networkx as nx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rubicon.models import RubiconConfig, Violation
from rubicon.snapshot.diff import SnapshotDiff
from rubicon.snapshot.store import list_snapshots, load_snapshot
from rubicon.viz.api import diff_overlay, file_level_view, layer_summary, ratsnest_view

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — populated by configure() before the server starts
# ---------------------------------------------------------------------------

_graph: nx.DiGraph | None = None
_config: RubiconConfig | None = None
_violations: list[Violation] = []
_diff: SnapshotDiff | None = None
_project_root: Path | None = None

STATIC_DIR = Path(__file__).parent / "static"


def configure(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
    diff: SnapshotDiff | None = None,
    project_root: Path | None = None,
) -> None:
    """Set the module-level state used by the API endpoints.

    Must be called before any endpoint is hit.
    """
    global _graph, _config, _violations, _diff, _project_root  # noqa: PLW0603
    _graph = graph
    _config = config
    _violations = violations
    _diff = diff
    _project_root = project_root


def _require_state() -> tuple[nx.DiGraph, RubiconConfig, list[Violation]]:
    """Return the configured state or raise if not configured."""
    if _graph is None or _config is None:
        raise RuntimeError(
            "Server not configured. Call configure() before serving requests."
        )
    return _graph, _config, _violations


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Rubicon Visualization Server")


# --- API endpoints --------------------------------------------------------

@app.get("/api/layers")
def api_layers() -> dict[str, Any]:
    """Level 1 — layer summary."""
    graph, config, violations = _require_state()
    return layer_summary(graph, config, violations)


@app.get("/api/files")
def api_files(
    layer: str | None = None,
    source_layer: str | None = None,
    target_layer: str | None = None,
) -> dict[str, Any]:
    """Level 2 — file-level view.

    Query params:
        layer — single-layer drill-down
        source_layer + target_layer — cross-layer drill-down
    """
    graph, config, violations = _require_state()
    return file_level_view(
        graph, config, violations,
        layer=layer,
        source_layer=source_layer,
        target_layer=target_layer,
    )


@app.get("/api/file/{file_id:path}")
def api_file(file_id: str) -> dict[str, Any]:
    """Level 3 — ratsnest view for a single file."""
    graph, config, violations = _require_state()
    result = ratsnest_view(graph, config, violations, file_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
    return result


@app.get("/api/diff")
def api_diff() -> dict[str, Any]:
    """Diff overlay data (empty if no diff mode)."""
    return diff_overlay(_diff, graph=_graph)


@app.get("/api/snapshots")
def api_snapshots() -> dict[str, Any]:
    """List available snapshots for the project."""
    if _project_root is None:
        return {"snapshots": []}

    snapshot_paths = list_snapshots(_project_root)
    snapshots = []
    for i, snap_path in enumerate(snapshot_paths, 1):
        snap = load_snapshot(snap_path)
        snapshots.append({
            "index": i,
            "filename": snap_path.name,
            "timestamp": snap.timestamp.isoformat(),
            "commit_hash": snap.commit_hash,
        })

    return {"snapshots": snapshots}


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    """Layer colors, layer order, and rule names."""
    _, config, _ = _require_state()

    layer_colors: dict[str, str] = {}
    for name, lc in config.layers.items():
        layer_colors[name] = lc.color if lc.color else ""

    return {
        "layer_order": config.layer_order,
        "layer_colors": layer_colors,
        "rules": config.rules,
    }


# --- Static file serving ---------------------------------------------------

# Mount static files last so API routes take priority.
# Only mount if the static directory exists (it may not during tests).
if STATIC_DIR.is_dir():
    @app.get("/")
    async def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="index.html not found")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def _find_open_port(start: int, max_attempts: int = 10) -> int | None:
    """Find an open port starting from `start`, trying up to `max_attempts` ports."""
    import socket

    for offset in range(max_attempts):
        port = start + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return None


def start_server(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
    diff: SnapshotDiff | None = None,
    port: int = 8742,
    project_root: Path | None = None,
) -> None:
    """Configure module state and start the uvicorn server.

    Tries the requested port, then falls back to the next 10 ports.
    Auto-opens the browser and prints a shutdown message on Ctrl+C.
    """
    import signal
    import webbrowser

    configure(graph, config, violations, diff, project_root=project_root)

    actual_port = _find_open_port(port)
    if actual_port is None:
        logger.error("No available port found in range %d-%d", port, port + 9)
        raise SystemExit(1)

    if actual_port != port:
        logger.info("Port %d in use, using %d instead", port, actual_port)

    url = f"http://127.0.0.1:{actual_port}"
    logger.info("Starting Rubicon visualization server at %s", url)

    # Open browser after a short delay to let the server start
    import threading
    threading.Timer(0.8, webbrowser.open, args=[url]).start()

    # Graceful shutdown on Ctrl+C
    original_sigint = signal.getsignal(signal.SIGINT)

    def _shutdown(sig: int, frame: object) -> None:
        print("\nStopping Rubicon server.")
        signal.signal(signal.SIGINT, original_sigint)
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _shutdown)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=actual_port,
        log_level="info",
    )
