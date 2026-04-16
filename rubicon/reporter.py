"""Terminal violation reporter with color-coded output."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from rubicon.models import Severity, Violation
from rubicon.snapshot.diff import SnapshotDiff

_SEVERITY_ORDER = [Severity.ERROR, Severity.WARNING, Severity.INFO]

_SEVERITY_STYLE = {
    Severity.ERROR: ("bold red", "✗"),
    Severity.WARNING: ("yellow", "⚠"),
    Severity.INFO: ("cyan", "ℹ"),
}


def report_violations(
    violations: list[Violation],
    console: Console | None = None,
    diff: SnapshotDiff | None = None,
) -> None:
    """Print violations to the terminal, grouped by severity."""
    console = console or Console()

    if diff is not None:
        _print_diff_banner(diff, console)

    # Build a set of new violation keys for tagging
    new_viol_keys: set[tuple[str, str, str | None]] = set()
    if diff is not None:
        for vd in diff.new_violations:
            new_viol_keys.add((vd["rule"], vd["source_node_id"], vd.get("target_node_id")))

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
            if (v.rule, v.source_node_id, v.target_node_id) in new_viol_keys:
                line.append(" [NEW]", style="bold red")
            console.print(line)

    # Show resolved violations if in diff mode
    if diff is not None and diff.resolved_violations:
        console.print(Text(f"\nRESOLVED ({len(diff.resolved_violations)})", style="bold green"))
        for vd in diff.resolved_violations:
            line = Text("  ✓ ", style="green")
            line.append(f"{vd['rule']}", style="bold")
            line.append(f": {vd['message']}")
            line.append(" [RESOLVED]", style="bold green")
            console.print(line)

    console.print()
    _print_summary(grouped, console)


def _print_diff_banner(diff: SnapshotDiff, console: Console) -> None:
    """Print the diff summary banner at the top."""
    banner = Text(f"\nSince last snapshot: {diff.summary}", style="bold")
    console.print(banner)


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
