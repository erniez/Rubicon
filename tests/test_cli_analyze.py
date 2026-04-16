"""Tests for the `rubicon analyze` command."""

from pathlib import Path

from typer.testing import CliRunner

from rubicon.cli import app

runner = CliRunner()


def _write_project(tmp_path: Path, config: str = "", files: dict[str, str] | None = None) -> None:
    """Create a minimal project in tmp_path with a .rubicon config and source files."""
    src = tmp_path / "src"
    src.mkdir()
    if files is None:
        files = {"src/main.py": "x = 1\n"}
    for rel_path, content in files.items():
        p = tmp_path / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    if not config:
        config = (
            "layers:\n"
            "  domain:\n"
            "    directories:\n"
            "      - src/\n"
            "layer_order:\n"
            "  - domain\n"
            "rules:\n"
            "  - orphan_detection\n"
        )
    (tmp_path / ".rubicon").write_text(config)


class TestAnalyzeBasic:
    def test_runs_and_exits(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code in (0, 1)
        assert "Analyzing" in result.output

    def test_no_config_exits_one(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("x = 1\n")
        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 1
        assert "No .rubicon config found" in result.output


class TestCrawlOnly:
    def test_lists_files_and_exits(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path), "--crawl-only"])
        assert result.exit_code == 0
        assert "main.py" in result.output
        assert "files found" in result.output

    def test_shows_language(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path), "--crawl-only"])
        assert "python" in result.output.lower()


class TestGraphOnly:
    def test_prints_summary(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path), "--graph-only"])
        assert result.exit_code == 0
        assert "node" in result.output.lower() or "edge" in result.output.lower()


class TestMermaidFormat:
    def test_outputs_mermaid(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path), "--format", "mermaid"])
        assert result.exit_code == 0
        # Mermaid diagrams start with a graph/flowchart directive or contain ---
        assert "graph" in result.output.lower() or "flowchart" in result.output.lower() or "---" in result.output

    def test_mermaid_to_file(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        out_file = tmp_path / "arch.md"
        result = runner.invoke(
            app, ["analyze", str(tmp_path), "--format", "mermaid", "--output", str(out_file)]
        )
        assert result.exit_code == 0
        assert out_file.exists()


class TestSnapshot:
    def test_creates_snapshot_file(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path), "--snapshot"])
        assert result.exit_code in (0, 1)
        snapshots_dir = tmp_path / ".rubicon_data" / "snapshots"
        assert snapshots_dir.exists()
        snapshot_files = list(snapshots_dir.glob("*.json"))
        assert len(snapshot_files) == 1

    def test_diff_without_snapshot_fails(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path), "--diff"])
        assert result.exit_code == 1
        assert "No snapshots found" in result.output


class TestExport:
    def test_creates_svg(self, tmp_path: Path) -> None:
        _write_project(tmp_path)
        svg_path = tmp_path / "arch.svg"
        result = runner.invoke(
            app, ["analyze", str(tmp_path), "--export", "--output", str(svg_path)]
        )
        assert result.exit_code == 0
        assert svg_path.exists()
        content = svg_path.read_text()
        assert "<svg" in content

    def test_analyze_writes_graph_cache(self, tmp_path: Path) -> None:
        """Running analyze should write a graph cache for subsequent preflight use."""
        _write_project(tmp_path)
        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code in (0, 1)  # violations don't matter
        assert (tmp_path / ".rubicon_data" / "graph_cache.json").is_file()
