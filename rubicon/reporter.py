"""Terminal violation reporter with color-coded output."""

from rich.console import Console
from rich.text import Text

from rubicon.graph.models import Severity, Violation

_SEVERITY_ORDER = [Severity.ERROR, Severity.WARNING, Severity.INFO]

_SEVERITY_STYLE = {
    Severity.ERROR: ("bold red", "✗"),
    Severity.WARNING: ("yellow", "⚠"),
    Severity.INFO: ("cyan", "ℹ"),
}


def report_violations(violations: list[Violation], console: Console | None = None) -> None:
    """Print violations to the terminal, grouped by severity."""
    console = console or Console()

    grouped: dict[Severity, list[Violation]] = {s: [] for s in _SEVERITY_ORDER}
    for v in violations:
        grouped[v.severity].append(v)

    for severity in _SEVERITY_ORDER:
        group = grouped[severity]
        if not group:
            continue

        style, icon = _SEVERITY_STYLE[severity]
        header = Text(f"\n{severity.value.upper()} ({len(group)})", style=style)
        console.print(header)

        for v in group:
            line = Text(f"  {icon} ", style=style)
            line.append(f"{v.rule}", style="bold")
            line.append(f": {v.message}")
            if v.relationship and v.relationship.line_number:
                line.append(f" (line {v.relationship.line_number})", style="dim")
            console.print(line)

    console.print()
    _print_summary(grouped, console)


def _print_summary(
    grouped: dict[Severity, list[Violation]], console: Console
) -> None:
    """Print the summary line."""
    parts: list[str] = []
    for severity in _SEVERITY_ORDER:
        count = len(grouped[severity])
        if count > 0:
            parts.append(f"{count} {severity.value}{'s' if count != 1 else ''}")

    if parts:
        console.print(f"Summary: {', '.join(parts)}")
    else:
        console.print("[green]No violations found.[/green]")
