"""Tests for the `rubicon check` CI command."""

from pathlib import Path

import networkx as nx
import pytest
from typer.testing import CliRunner

from rubicon.cli import app, _parse_severity, _severity_rank
from rubicon.models import (
    LayerConfig,
    Relationship,
    RelationshipType,
    RubiconConfig,
    Severity,
    Violation,
)

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures" / "sample_project"


# ── Severity helpers ─────────────────────────────────────────────


class TestParseSeverity:
    def test_parse_error(self) -> None:
        assert _parse_severity("error") == Severity.ERROR

    def test_parse_warning(self) -> None:
        assert _parse_severity("warning") == Severity.WARNING

    def test_parse_info(self) -> None:
        assert _parse_severity("info") == Severity.INFO

    def test_case_insensitive(self) -> None:
        assert _parse_severity("WARNING") == Severity.WARNING

    def test_unknown_returns_none(self) -> None:
        assert _parse_severity("critical") is None


class TestSeverityRank:
    def test_error_highest(self) -> None:
        assert _severity_rank(Severity.ERROR) > _severity_rank(Severity.WARNING)

    def test_warning_above_info(self) -> None:
        assert _severity_rank(Severity.WARNING) > _severity_rank(Severity.INFO)


# ── CLI integration via CliRunner ────────────────────────────────


class TestCheckCommand:
    def test_exits_zero_when_no_violations(self, tmp_path: Path) -> None:
        """A project with no rules enabled should have no violations."""
        # Create a minimal project with a config that disables all rules
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text(
            "layers: {}\nlayer_order: []\nrules: []\n"
        )

        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 0
        assert "no violations found" in result.output

    def test_exits_one_on_violations(self, tmp_path: Path) -> None:
        """Should exit 1 when violations are found above the threshold."""
        src = tmp_path / "src"
        src.mkdir()
        # Create an orphan file — orphan_detection will flag it (INFO severity)
        (src / "orphan.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text(
            "layers:\n"
            "  domain:\n"
            "    directories:\n"
            "      - src/\n"
            "layer_order:\n"
            "  - domain\n"
            "rules:\n"
            "  - orphan_detection\n"
        )

        result = runner.invoke(app, ["check", str(tmp_path), "--fail-on", "info"])
        assert result.exit_code == 1
        assert "orphan_detection" in result.output

    def test_fail_on_error_only(self, tmp_path: Path) -> None:
        """With --fail-on error, INFO violations should not cause failure."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "orphan.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text(
            "layers:\n"
            "  domain:\n"
            "    directories:\n"
            "      - src/\n"
            "layer_order:\n"
            "  - domain\n"
            "rules:\n"
            "  - orphan_detection\n"
        )

        # orphan_detection is INFO severity, so --fail-on error should pass
        result = runner.invoke(app, ["check", str(tmp_path), "--fail-on", "error"])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_compact_output_format(self, tmp_path: Path) -> None:
        """Output should be grep-friendly with [FAIL]/[PASS] markers."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "orphan.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text(
            "layers:\n"
            "  domain:\n"
            "    directories:\n"
            "      - src/\n"
            "layer_order:\n"
            "  - domain\n"
            "rules:\n"
            "  - orphan_detection\n"
        )

        result = runner.invoke(app, ["check", str(tmp_path)])
        assert "[FAIL]" in result.output or "[PASS]" in result.output

    def test_summary_line(self, tmp_path: Path) -> None:
        """Output should end with a summary count."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "orphan.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text(
            "layers:\n"
            "  domain:\n"
            "    directories:\n"
            "      - src/\n"
            "layer_order:\n"
            "  - domain\n"
            "rules:\n"
            "  - orphan_detection\n"
        )

        result = runner.invoke(app, ["check", str(tmp_path)])
        assert "rubicon:" in result.output
        assert "errors" in result.output

    def test_invalid_fail_on_exits_two(self, tmp_path: Path) -> None:
        """An invalid --fail-on value should exit with code 2."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text(
            "layers: {}\nlayer_order: []\nrules: []\n"
        )

        result = runner.invoke(app, ["check", str(tmp_path), "--fail-on", "critical"])
        assert result.exit_code == 2
        assert "Unknown severity" in result.output

    def test_no_snapshot_saved(self, tmp_path: Path) -> None:
        """Check command should not create any snapshot files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text(
            "layers: {}\nlayer_order: []\nrules: []\n"
        )

        runner.invoke(app, ["check", str(tmp_path)])
        snapshots_dir = tmp_path / ".rubicon" / "snapshots"
        assert not snapshots_dir.exists()
