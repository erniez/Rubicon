from collections import Counter
from pathlib import Path

import typer
import yaml

from rubicon.classifier.config import load_config
from rubicon.crawler.scanner import scan
from rubicon.graph.builder import build_graph, graph_summary
from rubicon.graph.layered import apply_layers
from rubicon.models import ALL_BUILTIN_RULES, Severity
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
    help="Deterministic structural integrity validation and architecture visualization for any codebase.",
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    help: bool = typer.Option(False, "--help", "-h", is_eager=True, help="Show this message and exit."),
) -> None:
    """Deterministic structural integrity validation and architecture visualization for any codebase."""
    if help or ctx.invoked_subcommand is None:
        from rich.console import Console
        from rich.text import Text

        console = Console()
        console.print()
        console.print("[bold]Usage:[/bold] rubicon [bold cyan]<command>[/bold cyan] [dim]\\[options] <path>[/dim]")
        console.print()
        console.print(Text("Deterministic structural integrity validation and architecture visualization for any codebase.", style="dim"))
        console.print()

        console.print("[bold]Commands:[/bold]")
        console.print()

        console.print("  [bold cyan]rubicon init[/bold cyan] [dim]\\[path][/dim]")
        console.print("    Interactive setup — scans for source files, prompts for layer")
        console.print("    assignments, generates .rubicon.")
        console.print()

        console.print("  [bold cyan]rubicon analyze[/bold cyan] [dim]<path>[/dim]")
        console.print("    Analyze architecture and report violations.")
        console.print()
        console.print("    [bold]Output[/bold]")
        console.print("      --format [dim]<fmt>[/dim]          Output format: terminal (default) or mermaid")
        console.print("      --output [dim]<file>[/dim]         Write to file instead of stdout")
        console.print("    [bold]Visualization[/bold]")
        console.print("      --serve                 Open interactive diagram in browser")
        console.print("      --port [dim]<int>[/dim]            Server port (default: 8742)")
        console.print("      --export                Export diagram as SVG")
        console.print("    [bold]Snapshots & Diff[/bold]")
        console.print("      --snapshot              Save a snapshot for future diffs")
        console.print("      --diff                  Compare against last snapshot")
        console.print("      --diff-against [dim]<ref>[/dim]    Compare against a specific snapshot")
        console.print("    [bold]Debug[/bold]")
        console.print("      --crawl-only            List discovered files only")
        console.print("      --graph-only            Print graph summary, skip rules")
        console.print()

        console.print("  [bold cyan]rubicon check[/bold cyan] [dim]<path>[/dim]")
        console.print("    CI-friendly mode — compact output, non-zero exit on violations.")
        console.print()
        console.print("      --fail-on [dim]<severity>[/dim]    Minimum severity to fail: error, warning (default), info")
        console.print()

        raise typer.Exit()


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
        rich_help_panel="Output",
    ),
    output: Path | None = typer.Option(
        None,
        help="Write output to file instead of stdout.",
        rich_help_panel="Output",
    ),
    crawl_only: bool = typer.Option(
        False,
        "--crawl-only",
        help="Only crawl and list discovered files, skip parsing and analysis.",
        rich_help_panel="Debug",
    ),
    graph_only: bool = typer.Option(
        False,
        "--graph-only",
        help="Crawl and parse, print graph summary, skip rule checking.",
        rich_help_panel="Debug",
    ),
    diff: bool = typer.Option(
        False,
        "--diff",
        help="Compare against the last snapshot and show changes.",
        rich_help_panel="Snapshots & Diff",
    ),
    diff_against: str | None = typer.Option(
        None,
        "--diff-against",
        help="Compare against a specific snapshot: index (1=oldest, -2=second latest), filename, or timestamp prefix.",
        rich_help_panel="Snapshots & Diff",
    ),
    snapshot: bool = typer.Option(
        False,
        "--snapshot",
        help="Save a snapshot of the architecture for future diffs.",
        rich_help_panel="Snapshots & Diff",
    ),
    serve: bool = typer.Option(
        False,
        "--serve",
        help="Start the visualization server and open the browser.",
        rich_help_panel="Visualization",
    ),
    port: int = typer.Option(
        8742,
        "--port",
        help="Port for the visualization server.",
        rich_help_panel="Visualization",
    ),
    export: bool = typer.Option(
        False,
        "--export",
        help="Export architecture diagram as SVG.",
        rich_help_panel="Visualization",
    ),
) -> None:
    """Analyze a project's architecture."""
    typer.echo(f"Analyzing: {path}")
    config = load_config(path)
    files = scan(path, ignore=config.ignore)

    if crawl_only:
        for f in files:
            typer.echo(f"  [{f.language}] {f.path}")
        typer.echo(f"\n{len(files)} files found.")
        raise typer.Exit()

    graph = build_graph(files)

    if graph_only:
        typer.echo(graph_summary(graph))
        raise typer.Exit()

    if not config.layers and not (path / ".rubicon").is_file():
        typer.echo("No .rubicon config found. Run 'rubicon init' to get started.", err=True)
        raise typer.Exit(code=1)

    apply_layers(graph, config.layer_map, config.layer_patterns)

    from rubicon.graph.cache import save_graph_cache
    save_graph_cache(graph, path)

    violations = run_rules(graph, config)

    # Snapshot: diff against previous if requested
    snapshot_diff: SnapshotDiff | None = None
    if diff or diff_against is not None:
        if diff_against is not None:
            previous = resolve_snapshot(path, diff_against)
            if previous is None:
                available = list_snapshots(path)
                if not available:
                    typer.echo("No snapshots found. Use --snapshot to save one first.", err=True)
                else:
                    typer.echo(f"Snapshot '{diff_against}' not found. Available snapshots:", err=True)
                    for i, snap_path in enumerate(available, 1):
                        typer.echo(f"  {i}: {snap_path.name}", err=True)
                raise typer.Exit(code=1)
        else:
            previous = load_latest_snapshot(path)
            if previous is None:
                typer.echo("No snapshots found. Use --snapshot to save one first.", err=True)
                raise typer.Exit(code=1)
        commit_hash = get_commit_hash(path)
        current_snapshot = graph_to_snapshot(graph, violations, config, commit_hash)
        snapshot_diff = diff_snapshots(previous, current_snapshot)

    # Snapshot: save only when explicitly requested
    if snapshot:
        commit_hash = get_commit_hash(path)
        snap = graph_to_snapshot(graph, violations, config, commit_hash)
        save_snapshot(path, snap)

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
    config = load_config(path)
    files = scan(path, ignore=config.ignore)
    graph = build_graph(files)
    if not config.layers and not (path / ".rubicon").is_file():
        typer.echo("No .rubicon config found. Run 'rubicon init' to get started.", err=True)
        raise typer.Exit(code=1)

    apply_layers(graph, config.layer_map, config.layer_patterns)

    from rubicon.graph.cache import save_graph_cache
    save_graph_cache(graph, path)

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

    exit_code = 1 if failing else 0
    typer.echo(f"exit {exit_code}")

    raise typer.Exit(code=exit_code)


@app.command()
def init(
    path: Path = typer.Argument(
        ".",
        help="Path to the project root.",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Generate a .rubicon config by scanning the project and prompting for layer assignments."""
    config_path = path / ".rubicon"
    if config_path.exists():
        overwrite = typer.confirm(f"{config_path} already exists. Overwrite?", default=False)
        if not overwrite:
            raise typer.Exit()

    typer.echo(f"Scanning {path} for source files...")
    files = scan(path)

    if not files:
        typer.echo("No source files found.", err=True)
        raise typer.Exit(code=1)

    # Discover top-level directories that contain source files
    dir_counts: Counter[str] = Counter()
    for f in files:
        parts = f.path.parts
        top_dir = parts[0] if len(parts) > 1 else "."
        dir_counts[top_dir] += 1

    typer.echo(f"\nFound {len(files)} source files in {len(dir_counts)} directories:\n")
    sorted_dirs = sorted(dir_counts.items(), key=lambda x: -x[1])
    for i, (d, count) in enumerate(sorted_dirs, 1):
        typer.echo(f"  {i}. {d}/ ({count} files)")

    # Prompt for layer assignments
    typer.echo("\n--- Layer Assignment ---")
    typer.echo("For each directory, enter a layer name (e.g. presentation, domain, data).")
    typer.echo("Press Enter to skip a directory.\n")

    layers: dict[str, list[str]] = {}
    for d, count in sorted_dirs:
        layer = typer.prompt(f"  {d}/ ({count} files) -> layer", default="", show_default=False).strip()
        if layer:
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(f"{d}/")

    if not layers:
        typer.echo("No layers assigned. Aborting.", err=True)
        raise typer.Exit(code=1)

    # Prompt for layer order
    layer_names = list(layers.keys())
    typer.echo(f"\n--- Layer Order (top to bottom) ---")
    typer.echo(f"Layers found: {', '.join(layer_names)}")
    typer.echo("Enter layer names in order from top (presentation) to bottom (infrastructure).")
    typer.echo("Separate with commas. Group adjacent layers with brackets: a, b, [c, d]\n")

    order_input = typer.prompt("  Layer order", default=", ".join(layer_names))
    layer_order = _parse_layer_order(order_input)

    # Default colors
    default_colors = [
        "#4A90D9", "#50C878", "#E8A838", "#D94A4A", "#9B59B6",
        "#1ABC9C", "#E74C3C", "#3498DB", "#F39C12", "#2ECC71",
    ]

    # Build config dict
    config: dict = {"layers": {}}
    for i, (name, dirs) in enumerate(layers.items()):
        config["layers"][name] = {
            "directories": dirs,
            "color": default_colors[i % len(default_colors)],
        }

    config["layer_order"] = layer_order
    config["rules"] = list(ALL_BUILTIN_RULES)

    # Write config
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    typer.echo(f"\nConfig written to {config_path}")
    typer.echo("Run 'rubicon analyze .' to see your architecture.")


def _parse_layer_order(raw: str) -> list[str | list[str]]:
    """Parse a layer order string like 'a, b, [c, d]' into a list."""
    result: list[str | list[str]] = []
    raw = raw.strip()
    i = 0
    while i < len(raw):
        if raw[i] == "[":
            # Find matching bracket
            end = raw.index("]", i)
            group = [s.strip() for s in raw[i + 1:end].split(",") if s.strip()]
            if group:
                result.append(group)
            i = end + 1
        elif raw[i] == ",":
            i += 1
        elif raw[i].strip():
            # Read until comma or bracket
            end = i
            while end < len(raw) and raw[end] not in ",[]":
                end += 1
            token = raw[i:end].strip()
            if token:
                result.append(token)
            i = end
        else:
            i += 1
    return result


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
