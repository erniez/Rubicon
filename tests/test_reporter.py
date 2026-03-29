"""Tests for the terminal violation reporter."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console

from rubicon.models import Relationship, RelationshipType, Severity, Violation
from rubicon.reporter import report_violations
from rubicon.snapshot.diff import SnapshotDiff


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120, highlight=False)
    return console, buf


def _violation(
    rule: str = "test_rule",
    severity: Severity = Severity.WARNING,
    source: str = "a.py",
    target: str | None = "b.py",
    message: str = "test message",
    line_number: int | None = None,
) -> Violation:
    rel = None
    if line_number is not None:
        rel = Relationship(
            source="X",
            target="Y",
            type=RelationshipType.IMPORT,
            source_file=Path(source),
            line_number=line_number,
        )
    return Violation(
        rule=rule,
        severity=severity,
        source_node_id=source,
        target_node_id=target,
        message=message,
        relationship=rel,
    )


class TestNoViolations:
    def test_prints_no_violations_message(self) -> None:
        console, buf = _make_console()
        report_violations([], console=console)
        output = buf.getvalue()
        assert "No violations found" in output

    def test_summary_line_absent_for_empty(self) -> None:
        console, buf = _make_console()
        report_violations([], console=console)
        output = buf.getvalue()
        assert "Summary:" not in output


class TestSeverityGrouping:
    def test_groups_by_severity_in_order(self) -> None:
        violations = [
            _violation(rule="info_rule", severity=Severity.INFO),
            _violation(rule="error_rule", severity=Severity.ERROR),
            _violation(rule="warn_rule", severity=Severity.WARNING),
        ]
        console, buf = _make_console()
        report_violations(violations, console=console)
        output = buf.getvalue()

        error_pos = output.find("ERROR")
        warning_pos = output.find("WARNING")
        info_pos = output.find("INFO")
        assert error_pos < warning_pos < info_pos

    def test_counts_per_severity(self) -> None:
        violations = [
            _violation(severity=Severity.ERROR),
            _violation(severity=Severity.ERROR),
            _violation(severity=Severity.WARNING),
        ]
        console, buf = _make_console()
        report_violations(violations, console=console)
        output = buf.getvalue()
        assert "ERROR (2)" in output
        assert "WARNING (1)" in output


class TestViolationDetails:
    def test_line_number_shown(self) -> None:
        violations = [_violation(line_number=42)]
        console, buf = _make_console()
        report_violations(violations, console=console)
        output = buf.getvalue()
        assert "line 42" in output

    def test_rule_name_in_output(self) -> None:
        violations = [_violation(rule="no_upward_dependency")]
        console, buf = _make_console()
        report_violations(violations, console=console)
        output = buf.getvalue()
        assert "no_upward_dependency" in output

    def test_message_in_output(self) -> None:
        violations = [_violation(message="bad import found")]
        console, buf = _make_console()
        report_violations(violations, console=console)
        output = buf.getvalue()
        assert "bad import found" in output


class TestSummaryLine:
    def test_summary_counts_correct(self) -> None:
        violations = [
            _violation(severity=Severity.ERROR),
            _violation(severity=Severity.WARNING),
            _violation(severity=Severity.WARNING),
            _violation(severity=Severity.INFO),
        ]
        console, buf = _make_console()
        report_violations(violations, console=console)
        output = buf.getvalue()
        assert "1 error" in output
        assert "2 warnings" in output
        assert "1 info" in output

    def test_summary_singular_form(self) -> None:
        violations = [_violation(severity=Severity.ERROR)]
        console, buf = _make_console()
        report_violations(violations, console=console)
        output = buf.getvalue()
        assert "1 error" in output
        # Should not say "errors" for count of 1
        assert "1 errors" not in output


class TestDiffMode:
    def test_new_violation_tagged(self) -> None:
        v = _violation(rule="r1", source="a.py", target="b.py")
        diff = SnapshotDiff(
            new_violations=[
                {"rule": "r1", "source_node_id": "a.py", "target_node_id": "b.py", "message": "x"}
            ],
            summary="+1 new violation",
        )
        console, buf = _make_console()
        report_violations([v], console=console, diff=diff)
        output = buf.getvalue()
        assert "[NEW]" in output

    def test_resolved_violations_shown(self) -> None:
        diff = SnapshotDiff(
            resolved_violations=[
                {"rule": "old_rule", "source_node_id": "c.py", "message": "was bad"}
            ],
            summary="1 resolved violation",
        )
        console, buf = _make_console()
        report_violations([], console=console, diff=diff)
        output = buf.getvalue()
        assert "RESOLVED" in output
        assert "old_rule" in output

    def test_diff_banner_printed(self) -> None:
        diff = SnapshotDiff(summary="+2 connections, 1 new violation")
        console, buf = _make_console()
        report_violations([], console=console, diff=diff)
        output = buf.getvalue()
        assert "Since last snapshot" in output
        assert "+2 connections" in output

    def test_no_diff_no_banner(self) -> None:
        console, buf = _make_console()
        report_violations([], console=console, diff=None)
        output = buf.getvalue()
        assert "Since last snapshot" not in output
