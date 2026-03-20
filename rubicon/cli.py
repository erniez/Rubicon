from pathlib import Path

import typer

from rubicon.classifier.config import load_config
from rubicon.crawler.scanner import scan
from rubicon.graph.builder import build_graph, graph_summary
from rubicon.graph.layered import apply_layers
from rubicon.models import Severity
from rubicon.mermaid import generate_mermaid
from rubicon.reporter import report_violations
from rubicon.rules.engine import run_rules
from rubicon.snapshot.diff import SnapshotDiff, diff_snapshots
from rubicon.snapshot.models import graph_to_snapshot
from rubicon.snapshot.store import (
    get_commit_hash,
    list_snapshots,
    load_latest_snapshot,
    resolve_snapshot,
    save_snapshot,
)

app = typer.Typer(
    name="rubicon",
    help="Language-agnostic code architecture visualization and design rule checking.",
    no_args_is_help=True,
)


@app.command()
def analyze(
    path: Path = typer.Argument(
        ...,
        help="Path to the project root to analyze.",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    format: str = typer.Option(
        "terminal",
        help="Output format: terminal, mermaid.",
    ),
    output: Path | None = typer.Option(
        None,
        help="Write output to file instead of stdout.",
    ),
    crawl_only: bool = typer.Option(
        False,
        "--crawl-only",
        help="Only crawl and list discovered files, skip parsing and analysis.",
    ),
    graph_only: bool = typer.Option(
        False,
        "--graph-only",
        help="Crawl and parse, print graph summary, skip rule checking.",
    ),
    diff: bool = typer.Option(
        False,
        "--diff",
        help="Compare against the last snapshot and show changes.",
    ),
    diff_against: str | None = typer.Option(
        None,
        "--diff-against",
        help="Compare against a specific snapshot: index (1=oldest, -2=second latest), filename, or timestamp prefix.",
    ),
    no_snapshot: bool = typer.Option(
        False,
        "--no-snapshot",
        help="Skip saving a snapshot after analysis.",
    ),
    serve: bool = typer.Option(
        False,
        "--serve",
        help="Start the visualization server and open the browser.",
    ),
    port: int = typer.Option(
        8742,
        "--port",
        help="Port for the visualization server.",
    ),
    export: bool = typer.Option(
        False,
        "--export",
        help="Export architecture diagram as SVG.",
    ),
) -> None:
    """Analyze a project's architecture."""
    typer.echo(f"Analyzing: {path}")
    files = scan(path)

    if crawl_only:
        for f in files:
            typer.echo(f"  [{f.language}] {f.path}")
        typer.echo(f"\n{len(files)} files found.")
        raise typer.Exit()

    graph = build_graph(files)

    if graph_only:
        typer.echo(graph_summary(graph))
        raise typer.Exit()

    config = load_config(path)
    apply_layers(graph, config.layer_map)

    violations = run_rules(graph, config)

    # Snapshot: diff against previous if requested
    snapshot_diff: SnapshotDiff | None = None
    if diff or diff_against is not None:
        if diff_against is not None:
            previous = resolve_snapshot(path, diff_against)
            if previous is None:
                available = list_snapshots(path)
                if not available:
                    typer.echo("No snapshots found.", err=True)
                else:
                    typer.echo(f"Snapshot '{diff_against}' not found. Available snapshots:", err=True)
                    for i, snap_path in enumerate(available, 1):
                        typer.echo(f"  {i}: {snap_path.name}", err=True)
                raise typer.Exit(code=1)
        else:
            previous = load_latest_snapshot(path)
        commit_hash = get_commit_hash(path)
        current_snapshot = graph_to_snapshot(graph, violations, config, commit_hash)
        snapshot_diff = diff_snapshots(previous, current_snapshot)

    # Snapshot: save unless suppressed
    if not no_snapshot:
        commit_hash = get_commit_hash(path)
        snapshot = graph_to_snapshot(graph, violations, config, commit_hash)
        save_snapshot(path, snapshot)

    if export:
        from rubicon.export import export_to_file

        export_path = output or Path("rubicon-architecture.svg")
        export_to_file(graph, config, violations, export_path)
        typer.echo(f"Diagram exported to {export_path}")
        raise typer.Exit()

    if format == "mermaid":
        mermaid_output = generate_mermaid(graph, config, violations, diff=snapshot_diff)
        if output:
            file_content = mermaid_output
            if output.suffix == ".md":
                file_content = f"```mermaid\n{mermaid_output}```\n"
            output.write_text(file_content)
            typer.echo(f"Mermaid diagram written to {output}")
        else:
            typer.echo(mermaid_output)
        raise typer.Exit()

    if serve:
        from rubicon.viz.server import start_server

        start_server(graph, config, violations, diff=snapshot_diff, port=port, project_root=path)
        raise typer.Exit()

    report_violations(violations, diff=snapshot_diff)

    has_errors = any(v.severity == Severity.ERROR for v in violations)
    raise typer.Exit(code=1 if has_errors else 0)


@app.command()
def check(
    path: Path = typer.Argument(
        ...,
        help="Path to the project root to check.",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    fail_on: str = typer.Option(
        "warning",
        "--fail-on",
        help="Minimum severity to fail: error, warning, info.",
    ),
) -> None:
    """Check architecture rules and exit non-zero on violations. Designed for CI pipelines.

    Produces compact output, saves no snapshots, and returns exit code 1
    if any violations at or above --fail-on severity are found.
    """
    files = scan(path)
    graph = build_graph(files)
    config = load_config(path)
    apply_layers(graph, config.layer_map)
    violations = run_rules(graph, config)

    severity_threshold = _parse_severity(fail_on)
    if severity_threshold is None:
        typer.echo(f"Unknown severity: {fail_on}. Use error, warning, or info.", err=True)
        raise typer.Exit(code=2)

    failing = [v for v in violations if _severity_rank(v.severity) >= _severity_rank(severity_threshold)]

    if not violations:
        typer.echo("rubicon: no violations found")
        raise typer.Exit(code=0)

    # Print violations in a compact, grep-friendly format
    for v in violations:
        marker = "FAIL" if v in failing else "PASS"
        target = f" -> {v.target_node_id}" if v.target_node_id else ""
        typer.echo(f"[{marker}] {v.severity.value.upper()} {v.rule}: {v.source_node_id}{target}: {v.message}")

    # Summary
    error_count = sum(1 for v in violations if v.severity == Severity.ERROR)
    warning_count = sum(1 for v in violations if v.severity == Severity.WARNING)
    info_count = sum(1 for v in violations if v.severity == Severity.INFO)
    typer.echo(f"\nrubicon: {error_count} errors, {warning_count} warnings, {info_count} info")

    raise typer.Exit(code=1 if failing else 0)


_SEVERITY_RANKS = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.ERROR: 2,
}


def _severity_rank(severity: Severity) -> int:
    return _SEVERITY_RANKS.get(severity, 0)


def _parse_severity(value: str) -> Severity | None:
    try:
        return Severity(value.lower())
    except ValueError:
        return None
