"""Path classification and import resolution for pre-flight checking.

These functions work without requiring source files to exist on disk,
making them suitable for validating proposed changes before they are written.
"""

from pathlib import Path

from rubicon.graph.builder import import_path_candidates
from rubicon.graph.layered import classify_path as _classify_layered
from rubicon.models import RubiconConfig


def classify_path(path: str | Path, config: RubiconConfig) -> str | None:
    """Classify any file path into its architectural layer.

    The file does not need to exist on disk. Classification is based solely
    on directory prefixes and filename patterns in the .rubicon config.

    Returns the layer name, or None if the path does not match any layer.
    """
    result = _classify_layered(str(path), config.layer_map, config.layer_patterns)
    return None if result == "unclassified" else result


def resolve_import_target(
    import_str: str,
    root: Path,
    config: RubiconConfig,
) -> tuple[str | None, str | None]:
    """Resolve an import string to a (file_path, layer) pair.

    Accepts any import form that might appear in source code:
      - File paths:          "domain/models.py"
      - Python modules:      "domain.models"
      - TypeScript aliases:  "@/domain/models"
      - Java packages:       "com.example.domain.models.User"
      - Relative imports:    "./models"

    Resolution strategy:
    1. Generate candidate file paths via import_path_candidates().
    2. Check each candidate against disk (relative to root).
    3. If a file is found, classify it and return (path, layer).
    4. If no file found, try classifying the raw import_str as a path directly
       (handles cases where the caller already has a relative file path).

    Returns (resolved_path_or_None, layer_or_None).
    """
    # Try to resolve to an existing file on disk
    for candidate in import_path_candidates(import_str):
        full_path = root / candidate
        if full_path.is_file():
            layer = classify_path(candidate, config)
            return candidate, layer

    # Fall back: treat the import string itself as a path for layer classification
    # This handles unresolved imports where the agent provides a file path directly
    layer = classify_path(import_str, config)
    if layer is not None:
        return import_str, layer

    return None, None
