"""Tests for the `rubicon init` command."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from rubicon.cli import app, _parse_layer_order

runner = CliRunner()


class TestParseLayerOrder:
    def test_simple_list(self) -> None:
        assert _parse_layer_order("a, b, c") == ["a", "b", "c"]

    def test_with_group(self) -> None:
        assert _parse_layer_order("a, b, [c, d]") == ["a", "b", ["c", "d"]]

    def test_multiple_groups(self) -> None:
        assert _parse_layer_order("[a, b], c, [d, e]") == [["a", "b"], "c", ["d", "e"]]

    def test_single_item(self) -> None:
        assert _parse_layer_order("solo") == ["solo"]

    def test_extra_spaces(self) -> None:
        assert _parse_layer_order("  a ,  b  , [ c , d ]  ") == ["a", "b", ["c", "d"]]


class TestInitCommand:
    def test_creates_rubicon_file(self, tmp_path: Path) -> None:
        src = tmp_path / "ui"
        src.mkdir()
        (src / "app.py").write_text("import os\n")
        models = tmp_path / "models"
        models.mkdir()
        (models / "user.py").write_text("class User: pass\n")

        # Simulate input: assign ui->presentation, models->domain, then order
        input_text = "presentation\ndomain\npresentation, domain\n"
        result = runner.invoke(app, ["init", str(tmp_path)], input=input_text)

        assert result.exit_code == 0
        config_path = tmp_path / ".rubicon"
        assert config_path.exists()

    def test_config_contains_layers(self, tmp_path: Path) -> None:
        src = tmp_path / "ui"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n")

        input_text = "presentation\npresentation\n"
        runner.invoke(app, ["init", str(tmp_path)], input=input_text)

        config = yaml.safe_load((tmp_path / ".rubicon").read_text())
        assert "presentation" in config["layers"]
        assert config["layers"]["presentation"]["directories"] == ["ui/"]

    def test_config_contains_layer_order(self, tmp_path: Path) -> None:
        src = tmp_path / "ui"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n")
        data = tmp_path / "data"
        data.mkdir()
        (data / "repo.py").write_text("x = 1\n")

        input_text = "presentation\ndata\npresentation, data\n"
        runner.invoke(app, ["init", str(tmp_path)], input=input_text)

        config = yaml.safe_load((tmp_path / ".rubicon").read_text())
        assert config["layer_order"] == ["presentation", "data"]

    def test_config_contains_rules(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("x = 1\n")

        input_text = "domain\ndomain\n"
        runner.invoke(app, ["init", str(tmp_path)], input=input_text)

        config = yaml.safe_load((tmp_path / ".rubicon").read_text())
        assert "no_upward_dependency" in config["rules"]

    def test_skipped_directories(self, tmp_path: Path) -> None:
        ui = tmp_path / "ui"
        ui.mkdir()
        (ui / "app.py").write_text("x = 1\n")
        utils = tmp_path / "utils"
        utils.mkdir()
        (utils / "helpers.py").write_text("x = 1\n")

        # Skip utils (empty input), assign ui only
        input_text = "presentation\n\npresentation\n"
        runner.invoke(app, ["init", str(tmp_path)], input=input_text)

        config = yaml.safe_load((tmp_path / ".rubicon").read_text())
        assert "presentation" in config["layers"]
        assert len(config["layers"]) == 1

    def test_no_source_files_exits(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("hello\n")

        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 1
        assert "No source files" in result.output

    def test_no_layers_assigned_exits(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("x = 1\n")

        # Skip all directories
        input_text = "\n"
        result = runner.invoke(app, ["init", str(tmp_path)], input=input_text)
        assert result.exit_code == 1

    def test_existing_config_no_overwrite(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("x = 1\n")
        (tmp_path / ".rubicon").write_text("existing: true\n")

        # Decline overwrite
        result = runner.invoke(app, ["init", str(tmp_path)], input="n\n")
        assert result.exit_code == 0
        assert "existing: true" in (tmp_path / ".rubicon").read_text()

    def test_grouped_layer_order(self, tmp_path: Path) -> None:
        for d in ["ui", "api", "utils"]:
            p = tmp_path / d
            p.mkdir()
            (p / "main.py").write_text("x = 1\n")

        input_text = "presentation\nnetworking\nutilities\npresentation, [networking, utilities]\n"
        runner.invoke(app, ["init", str(tmp_path)], input=input_text)

        config = yaml.safe_load((tmp_path / ".rubicon").read_text())
        assert config["layer_order"] == ["presentation", ["networking", "utilities"]]
