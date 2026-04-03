"""Ignore pattern handling: .gitignore + default excludes."""

from pathlib import Path

from pathspec import PathSpec

DEFAULT_EXCLUDES: list[str] = [
    ".git",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".gradle",
    "Pods",
    ".eggs",
    "*.egg-info",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
]


def load_gitignore(root: Path, extra_patterns: list[str] | None = None) -> PathSpec:
    """Load .gitignore patterns from the project root.

    Args:
        root: Project root directory.
        extra_patterns: Additional gitignore-style patterns (e.g. from .rubicon ignore config).
    """
    gitignore_path = root / ".gitignore"
    patterns = list(DEFAULT_EXCLUDES)
    if gitignore_path.is_file():
        patterns.extend(
            line
            for line in gitignore_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    if extra_patterns:
        patterns.extend(extra_patterns)
    return PathSpec.from_lines("gitignore", patterns)
