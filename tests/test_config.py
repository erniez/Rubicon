"""Tests for .rubicon config loading."""

from pathlib import Path

from rubicon.classifier.config import load_config
from rubicon.models import ALL_BUILTIN_RULES

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample_project"
MALFORMED = FIXTURES / "malformed_rubicon"
CUSTOM_RULES = FIXTURES / "custom_rules_project"


class TestLoadConfig:
    def test_loads_layers(self) -> None:
        config = load_config(SAMPLE)
        assert "presentation" in config.layers
        assert "domain" in config.layers
        assert "data" in config.layers
        assert "networking" in config.layers

    def test_layer_directories(self) -> None:
        config = load_config(SAMPLE)
        assert config.layers["presentation"].directories == ["app/ui/", "app/screens/"]
        assert config.layers["domain"].directories == ["app/models/", "app/usecases/"]

    def test_layer_colors(self) -> None:
        config = load_config(SAMPLE)
        assert config.layers["presentation"].color == "#4A90D9"
        assert config.layers["data"].color == "#E8A838"

    def test_layer_order(self) -> None:
        config = load_config(SAMPLE)
        assert config.layer_order == ["presentation", "domain", "data", "networking"]

    def test_layer_index(self) -> None:
        config = load_config(SAMPLE)
        assert config.layer_index("presentation") == 0
        assert config.layer_index("domain") == 1
        assert config.layer_index("networking") == 3

    def test_layer_index_unknown(self) -> None:
        config = load_config(SAMPLE)
        assert config.layer_index("nonexistent") is None

    def test_rules(self) -> None:
        config = load_config(SAMPLE)
        assert "no_upward_dependency" in config.rules
        assert "no_layer_skipping" in config.rules
        assert "inheritance_flows_downward" in config.rules
        assert "no_circular_ownership" in config.rules

    def test_rules_only_specified(self) -> None:
        config = load_config(SAMPLE)
        # The sample config only lists 4 rules, not all 6
        assert len(config.rules) == 4
        assert "single_responsibility" not in config.rules
        assert "orphan_detection" not in config.rules

    def test_layer_map_property(self) -> None:
        config = load_config(SAMPLE)
        layer_map = config.layer_map
        assert layer_map["presentation"] == ["app/ui/", "app/screens/"]
        assert layer_map["networking"] == ["app/api/", "app/network/"]


class TestMissingConfig:
    def test_missing_file_returns_defaults(self) -> None:
        config = load_config(Path("/nonexistent/path"))
        assert config.layers == {}
        assert config.layer_order == []
        assert config.rules == ALL_BUILTIN_RULES

    def test_no_rubicon_dir_returns_defaults(self) -> None:
        # A real directory that has no .rubicon file
        config = load_config(Path(__file__).parent)
        assert config.layers == {}


class TestCustomRulesConfig:
    def test_loads_custom_rules(self) -> None:
        config = load_config(CUSTOM_RULES)
        assert len(config.custom_rules) == 2

    def test_file_layer_rule_fields(self) -> None:
        config = load_config(CUSTOM_RULES)
        rule = config.custom_rules[0]
        assert rule.name == "viewmodels_in_presentation"
        assert rule.pattern == "*ViewModel*"
        assert rule.layer == "presentation"
        assert rule.message == "ViewModels must live in the presentation layer"
        assert rule.severity == "error"

    def test_forbidden_imports_rule_fields(self) -> None:
        config = load_config(CUSTOM_RULES)
        rule = config.custom_rules[1]
        assert rule.name == "no_database_in_domain"
        assert rule.source_layer == "domain"
        assert rule.forbidden_imports == ["sqlalchemy", "django.db"]

    def test_no_custom_rules_returns_empty_list(self) -> None:
        config = load_config(SAMPLE)
        assert config.custom_rules == []


class TestIgnoreConfig:
    def test_ignore_defaults_to_empty(self) -> None:
        config = load_config(SAMPLE)
        assert config.ignore == []

    def test_ignore_parsed_from_config(self) -> None:
        config = load_config(FIXTURES / "ignore_project")
        assert config.ignore == ["tests/", "docs/", "*.generated.py"]

    def test_missing_config_ignore_empty(self) -> None:
        config = load_config(Path("/nonexistent/path"))
        assert config.ignore == []


class TestMalformedConfig:
    def test_malformed_yaml_returns_defaults(self) -> None:
        config = load_config(MALFORMED)
        assert config.layers == {}
        assert config.rules == ALL_BUILTIN_RULES
