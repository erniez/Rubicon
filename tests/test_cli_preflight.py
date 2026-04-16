"""Tests for the `rubicon preflight` command."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rubicon.cli import app

runner = CliRunner()

MULTILAYER = Path(__file__).parent / "fixtures" / "multilayer_project"


# ── helpers ───────────────────────────────────────────────────────────────────


def _invoke(args: list[str]) -> tuple[int, dict]:
    """Invoke preflight and parse JSON output."""
    result = runner.invoke(app, args)
    try:
        data = json.loads(result.output)
    except json.JSONDecodeError:
        data = {}
    return result.exit_code, data


# ── single check mode ─────────────────────────────────────────────────────────


class TestPreflightSingleCheck:
    def test_clean_downward_import_exits_zero(self) -> None:
        code, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "ui/screen.py",
            "--to", "services/order.py",
        ])
        assert code == 0
        assert data["allowed"] is True
        assert data["violations"] == []

    def test_upward_import_exits_one(self) -> None:
        code, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "domain/model.py",
            "--to", "ui/screen.py",
        ])
        assert code == 1
        assert data["allowed"] is False
        rules = [v["rule"] for v in data["violations"]]
        assert "no_upward_dependency" in rules

    def test_json_output_has_required_fields(self) -> None:
        _, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "ui/screen.py",
            "--to", "services/order.py",
        ])
        for field in ("allowed", "source", "source_layer", "target", "target_layer",
                      "relationship_type", "violations", "cycle_detection_run"):
            assert field in data, f"missing field: {field}"

    def test_unclassified_source_exits_two(self, tmp_path: Path) -> None:
        (tmp_path / ".rubicon").write_text(
            "layers:\n  domain:\n    directories: [domain/]\nlayer_order: [domain]\nrules: []\n"
        )
        code, _ = _invoke([
            "preflight", str(tmp_path),
            "--from", "unknown/thing.py",
            "--to", "domain/model.py",
        ])
        assert code == 2

    def test_type_inheritance_triggers_inheritance_rule(self) -> None:
        # ui inheriting from domain — upward inheritance (violation)
        code, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "ui/screen.py",
            "--to", "domain/model.py",
            "--type", "inheritance",
        ])
        assert code == 1
        rules = [v["rule"] for v in data["violations"]]
        assert "inheritance_flows_downward" in rules

    def test_no_mode_set_exits_nonzero(self) -> None:
        result = runner.invoke(app, [
            "preflight", str(MULTILAYER),
            "--from", "ui/screen.py",
        ])
        assert result.exit_code != 0

    def test_full_flag_sets_cycle_detection_run_true(self) -> None:
        code, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "ui/screen.py",
            "--to", "services/order.py",
            "--full",
        ])
        assert code == 0
        assert data["cycle_detection_run"] is True

    def test_missing_rubicon_config_exits_three(self, tmp_path: Path) -> None:
        code, _ = _invoke([
            "preflight", str(tmp_path),
            "--from", "ui/screen.py",
            "--to", "services/order.py",
        ])
        assert code == 3


# ── --what-can-import mode ────────────────────────────────────────────────────


class TestPreflightWhatCanImport:
    def test_exits_zero(self) -> None:
        code, _ = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "services/order.py",
            "--what-can-import", "services/order.py",
        ])
        assert code == 0

    def test_output_has_required_fields(self) -> None:
        _, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "services/order.py",
            "--what-can-import", "services/order.py",
        ])
        for field in ("source", "source_layer", "allowed_layers", "forbidden_layers"):
            assert field in data

    def test_services_can_import_domain_and_foundation(self) -> None:
        _, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "services/order.py",
            "--what-can-import", "services/order.py",
        ])
        assert "domain" in data["allowed_layers"]
        assert "foundation" in data["allowed_layers"]

    def test_services_cannot_import_presentation(self) -> None:
        _, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "services/order.py",
            "--what-can-import", "services/order.py",
        ])
        forbidden_names = [f["layer"] for f in data["forbidden_layers"]]
        assert "presentation" in forbidden_names

    def test_foundation_appears_in_allowed_for_any_source(self) -> None:
        for source in ["ui/screen.py", "services/order.py", "domain/model.py"]:
            _, data = _invoke([
                "preflight", str(MULTILAYER),
                "--from", source,
                "--what-can-import", source,
            ])
            assert "foundation" in data["allowed_layers"], \
                f"foundation not in allowed_layers for source={source}"

    def test_presentation_cannot_skip_to_domain(self) -> None:
        # presentation → domain skips services; should be forbidden
        _, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "ui/screen.py",
            "--what-can-import", "ui/screen.py",
        ])
        forbidden_names = [f["layer"] for f in data["forbidden_layers"]]
        assert "domain" in forbidden_names

    def test_source_layer_populated(self) -> None:
        _, data = _invoke([
            "preflight", str(MULTILAYER),
            "--from", "services/order.py",
            "--what-can-import", "services/order.py",
        ])
        assert data["source_layer"] == "services"

    def test_unclassified_source_returns_null_layer(self, tmp_path: Path) -> None:
        (tmp_path / ".rubicon").write_text(
            "layers:\n  domain:\n    directories: [domain/]\nlayer_order: [domain]\nrules: []\n"
        )
        _, data = _invoke([
            "preflight", str(tmp_path),
            "--from", "unknown/file.py",
            "--what-can-import", "unknown/file.py",
        ])
        assert data["source_layer"] is None
