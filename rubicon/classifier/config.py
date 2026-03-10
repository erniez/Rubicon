"""Read and parse .rubicon YAML configuration."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

ALL_BUILTIN_RULES: list[str] = [
    "no_upward_dependency",
    "no_layer_skipping",
    "inheritance_flows_downward",
    "no_circular_ownership",
    "no_circular_imports",
    "dependency_inversion",
    "single_responsibility",
    "orphan_detection",
]


@dataclass
class LayerConfig:
    """Configuration for a single architectural layer."""

    directories: list[str] = field(default_factory=list)
    color: str = ""


@dataclass
class RubiconConfig:
    """Parsed .rubicon configuration."""

    layers: dict[str, LayerConfig] = field(default_factory=dict)
    layer_order: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=lambda: list(ALL_BUILTIN_RULES))

    @property
    def layer_map(self) -> dict[str, list[str]]:
        """Return layer name → directory list mapping for use with apply_layers."""
        return {name: lc.directories for name, lc in self.layers.items()}

    def layer_index(self, layer_name: str) -> int | None:
        """Return the position of a layer in the layer order, or None if absent."""
        try:
            return self.layer_order.index(layer_name)
        except ValueError:
            return None


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


def _parse_config(raw: dict) -> RubiconConfig:
    """Parse a raw YAML dict into a RubiconConfig."""
    config = RubiconConfig()

    # Parse layers
    raw_layers = raw.get("layers", {})
    if isinstance(raw_layers, dict):
        for name, layer_data in raw_layers.items():
            if isinstance(layer_data, dict):
                config.layers[name] = LayerConfig(
                    directories=layer_data.get("directories", []),
                    color=layer_data.get("color", ""),
                )

    # Parse layer_order
    raw_order = raw.get("layer_order", [])
    if isinstance(raw_order, list):
        config.layer_order = [str(item) for item in raw_order]

    # Parse rules (if specified, use only those; otherwise keep all defaults)
    raw_rules = raw.get("rules")
    if isinstance(raw_rules, list):
        config.rules = [str(r) for r in raw_rules]

    return config
