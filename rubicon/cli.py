from pathlib import Path

import typer

from rubicon.classifier.config import load_config
from rubicon.crawler.scanner import scan
from rubicon.graph.builder import build_graph, graph_summary
from rubicon.graph.layered import apply_layers
from rubicon.graph.models import Severity
from rubicon.mermaid import generate_mermaid
from rubicon.reporter import report_violations
from rubicon.rules.engine import run_rules

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

    if format == "mermaid":
        mermaid_output = generate_mermaid(graph, config, violations)
        if output:
            file_content = mermaid_output
            if output.suffix == ".md":
                file_content = f"```mermaid\n{mermaid_output}```\n"
            output.write_text(file_content)
            typer.echo(f"Mermaid diagram written to {output}")
        else:
            typer.echo(mermaid_output)
        raise typer.Exit()

    report_violations(violations)

    has_errors = any(v.severity == Severity.ERROR for v in violations)
    raise typer.Exit(code=1 if has_errors else 0)
