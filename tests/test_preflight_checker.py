"""Tests for the pre-flight checker — fast path and full path."""

from pathlib import Path

import pytest

from rubicon.models import CustomRuleConfig, LayerConfig, RubiconConfig
from rubicon.preflight.checker import check_fast
from rubicon.preflight.models import PreflightResult


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_config(
    orchestrator_layers: list[str] | None = None,
    foundation_layers: list[str] | None = None,
    custom_rules: list[CustomRuleConfig] | None = None,
) -> RubiconConfig:
    return RubiconConfig(
        layers={
            "presentation": LayerConfig(directories=["ui/"], patterns=[]),
            "services": LayerConfig(directories=["services/"], patterns=[]),
            "domain": LayerConfig(directories=["domain/"], patterns=[]),
            "foundation": LayerConfig(directories=["foundation/"], patterns=[]),
        },
        layer_order=["presentation", "services", "domain", "foundation"],
        orchestrator_layers=orchestrator_layers or [],
        foundation_layers=foundation_layers or [],
        custom_rules=custom_rules or [],
    )


ROOT = Path("/nonexistent")  # no files on disk; tests rely on path-based classification


# ── TestCheckFast ─────────────────────────────────────────────────────────────


class TestCheckFast:
    def test_downward_import_is_allowed(self) -> None:
        result = check_fast("ui/screen.py", "services/order.py", "import", _make_config(), ROOT)
        assert result.allowed is True
        assert result.cycle_detection_run is False
        assert result.source_layer == "presentation"
        assert result.target_layer == "services"

    def test_upward_import_is_violation(self) -> None:
        result = check_fast("domain/model.py", "ui/screen.py", "import", _make_config(), ROOT)
        assert result.allowed is False
        rules = [v.rule for v in result.violations]
        assert "no_upward_dependency" in rules
        severities = [v.severity for v in result.violations if v.rule == "no_upward_dependency"]
        assert severities[0] == "warning"

    def test_layer_skip_is_violation(self) -> None:
        # presentation → domain skips services
        result = check_fast("ui/screen.py", "domain/model.py", "import", _make_config(), ROOT)
        assert result.allowed is False
        rules = [v.rule for v in result.violations]
        assert "no_layer_skipping" in rules

    def test_foundation_layer_exempt_from_skipping(self) -> None:
        config = _make_config(foundation_layers=["foundation"])
        # presentation → foundation: skips services and domain, but foundation is exempt
        result = check_fast("ui/screen.py", "foundation/utils.py", "import", config, ROOT)
        assert result.allowed is True

    def test_orchestrator_layer_exempt_from_skipping(self) -> None:
        config = _make_config(orchestrator_layers=["presentation"])
        # presentation (orchestrator) → domain: normally a skip, but exempt
        result = check_fast("ui/screen.py", "domain/model.py", "import", config, ROOT)
        assert result.allowed is True

    def test_same_layer_import_is_allowed(self) -> None:
        result = check_fast("domain/model.py", "domain/repo.py", "import", _make_config(), ROOT)
        assert result.allowed is True

    def test_inheritance_upward_is_error(self) -> None:
        result = check_fast(
            "ui/screen.py", "domain/model.py", "inheritance", _make_config(), ROOT
        )
        assert result.allowed is False
        rules = [v.rule for v in result.violations]
        assert "inheritance_flows_downward" in rules
        severities = [v.severity for v in result.violations if v.rule == "inheritance_flows_downward"]
        assert severities[0] == "error"

    def test_cross_layer_inheritance_to_concrete_is_info(self) -> None:
        # domain → foundation with concrete-looking target
        result = check_fast(
            "domain/model.py", "foundation/utils.py", "inheritance", _make_config(), ROOT
        )
        rules = [v.rule for v in result.violations]
        assert "dependency_inversion" in rules
        severities = [v.severity for v in result.violations if v.rule == "dependency_inversion"]
        assert severities[0] == "info"

    def test_cross_layer_inheritance_to_abstract_target_is_allowed(self) -> None:
        # "AbstractUtils" in path looks like abstraction — no dependency_inversion
        result = check_fast(
            "domain/model.py", "foundation/AbstractUtils.py", "inheritance",
            _make_config(), ROOT,
        )
        di_violations = [v for v in result.violations if v.rule == "dependency_inversion"]
        assert len(di_violations) == 0

    def test_custom_forbidden_import_is_violation(self) -> None:
        rule = CustomRuleConfig(
            name="no_ui_in_services",
            source_layer="services",
            forbidden_imports=["ui/*"],
            message="services must not import from ui",
            severity="warning",
        )
        config = _make_config(custom_rules=[rule])
        result = check_fast("services/order.py", "ui/screen.py", "import", config, ROOT)
        assert result.allowed is False
        rules = [v.rule for v in result.violations]
        assert "no_ui_in_services" in rules

    def test_unclassified_source_returns_false_with_message(self) -> None:
        result = check_fast("unknown/thing.py", "domain/model.py", "import", _make_config(), ROOT)
        assert result.allowed is False
        assert result.source_layer is None
        assert any("unclassifiable" in v.message.lower() for v in result.violations)

    def test_unclassified_target_returns_false_with_message(self) -> None:
        result = check_fast("domain/model.py", "third_party/lib.py", "import", _make_config(), ROOT)
        assert result.allowed is False
        assert result.target_layer is None
        assert any("unclassifiable" in v.message.lower() for v in result.violations)
