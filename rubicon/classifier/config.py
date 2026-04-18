"""Read and parse .rubicon YAML configuration."""

import logging
from pathlib import Path
from typing import Any

import yaml

from rubicon.models import ALL_BUILTIN_RULES, CustomRuleConfig, LayerConfig, RubiconConfig

logger = logging.getLogger(__name__)


def load_config(root: Path) -> RubiconConfig:
    """Load .rubicon config from the project root.

    Returns sensible defaults if the file is missing.
    Logs a warning and returns defaults if the file is malformed.
    """
    config_path = root / ".rubicon"
    if not config_path.is_file():
        return RubiconConfig()

    try:
        raw = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as e:
        logger.warning("Malformed .rubicon config: %s", e)
        return RubiconConfig()

    if not isinstance(raw, dict):
        logger.warning(".rubicon config is not a YAML mapping")
        return RubiconConfig()

    return _parse_config(raw)


def _parse_config(raw: dict[str, Any]) -> RubiconConfig:
    """Parse a raw YAML dict into a RubiconConfig."""
    config = RubiconConfig()

    # Parse layers
    raw_layers = raw.get("layers", {})
    if isinstance(raw_layers, dict):
        for name, layer_data in raw_layers.items():
            if isinstance(layer_data, dict):
                config.layers[name] = LayerConfig(
                    directories=layer_data.get("directories", []),
                    patterns=layer_data.get("patterns", []),
                    color=layer_data.get("color", ""),
                )

    # Parse layer_order — items can be strings or lists of strings (groups)
    raw_order = raw.get("layer_order", [])
    if isinstance(raw_order, list):
        parsed_order: list[str | list[str]] = []
        for item in raw_order:
            if isinstance(item, list):
                parsed_order.append([str(s) for s in item])
            else:
                parsed_order.append(str(item))
        config.layer_order = parsed_order

    # Parse foundation_layers
    raw_foundation = raw.get("foundation_layers", [])
    if isinstance(raw_foundation, list):
        config.foundation_layers = [str(item) for item in raw_foundation]

    # Parse orchestrator_layers
    raw_orchestrator = raw.get("orchestrator_layers", [])
    if isinstance(raw_orchestrator, list):
        config.orchestrator_layers = [str(item) for item in raw_orchestrator]

    # Parse rules (if specified, use only those; otherwise keep all defaults)
    raw_rules = raw.get("rules")
    if isinstance(raw_rules, list):
        config.rules = [str(r) for r in raw_rules]

    # Parse custom_rules
    raw_custom = raw.get("custom_rules", [])
    if isinstance(raw_custom, list):
        for entry in raw_custom:
            if isinstance(entry, dict):
                config.custom_rules.append(CustomRuleConfig(
                    name=str(entry.get("name", "")),
                    pattern=str(entry.get("pattern", "")),
                    layer=str(entry.get("layer", "")),
                    source_layer=str(entry.get("source_layer", "")),
                    forbidden_imports=entry.get("forbidden_imports", []),
                    message=str(entry.get("message", "")),
                    severity=str(entry.get("severity", "warning")),
                ))

    # Parse ignore patterns (gitignore-style)
    raw_ignore = raw.get("ignore", [])
    if isinstance(raw_ignore, list):
        config.ignore = [str(p) for p in raw_ignore]

    return config
