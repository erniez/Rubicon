"""Regex-based fallback parser for languages without tree-sitter adapters.

This module provides best-effort import extraction using regular expressions.
It is a **fallback only** -- it cannot extract inheritance or ownership
relationships, and its accuracy is inherently lower than a proper tree-sitter
adapter.

To remove this fallback entirely:
  1. Delete this file (rubicon/parser/regex_fallback.py)
  2. Remove the import + call in rubicon/parser/treesitter.py (search for
     "regex fallback")
"""

import logging
import re
from pathlib import Path

from rubicon.models import Relationship, RelationshipType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language-specific patterns
# ---------------------------------------------------------------------------
# Each value is a list of compiled regexes.  Every regex MUST contain a named
# group called ``target`` that captures the imported module/package name.

_LANGUAGE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "perl": [
        re.compile(r"use\s+(?P<target>[\w:]+)"),
        re.compile(r"require\s+(?P<target>[\w:]+)"),
    ],
    "lua": [
        re.compile(r"require\s*\(?['\"](?P<target>[^'\"]+)['\"]\)?"),
    ],
    "elixir": [
        re.compile(r"(?:import|alias|use|require)\s+(?P<target>[\w.]+)"),
    ],
    "scala": [
        re.compile(r"import\s+(?P<target>[\w.]+)"),
    ],
    "php": [
        # ``use Namespace\Class;``
        re.compile(r"use\s+(?P<target>[\w\\]+)"),
        # ``require 'file.php';``, ``require_once "file.php";``
        re.compile(r"(?:require|require_once|include|include_once)\s+['\"](?P<target>[^'\"]+)['\"]"),
    ],
    "dart": [
        re.compile(r"import\s+['\"](?P<target>[^'\"]+)['\"]"),
    ],
    "haskell": [
        re.compile(r"import\s+(?:qualified\s+)?(?P<target>[\w.]+)"),
    ],
}

# ---------------------------------------------------------------------------
# Generic patterns (tried when the language has no specific entry)
# ---------------------------------------------------------------------------

_GENERIC_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*import\s+['\"]?(?P<target>[\w./]+)['\"]?"),
    re.compile(r"^\s*(?:require|require_relative)\s+['\"](?P<target>[^'\"]+)['\"]"),
    re.compile(r"^\s*#include\s+[<\"](?P<target>[^>\"]+)[>\"]"),
    re.compile(r"^\s*use\s+(?P<target>[\w:]+)"),
    re.compile(r"^\s*from\s+(?P<target>[\w.]+)\s+import"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_imports(
    source_file: Path, language: str, content: str
) -> list[Relationship]:
    """Extract import relationships from *content* using regex patterns.

    Args:
        source_file: Relative path to the file being parsed.
        language: Language identifier (e.g. ``"perl"``).
        content: Full file content as a string.

    Returns:
        A list of :class:`Relationship` objects of type IMPORT.
        Returns an empty list when no imports are found or if an error occurs.
    """
    try:
        return _scan(source_file, language, content)
    except Exception:
        logger.warning(
            "Regex fallback failed for %s (%s)", source_file, language,
            exc_info=True,
        )
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scan(
    source_file: Path, language: str, content: str
) -> list[Relationship]:
    patterns = _LANGUAGE_PATTERNS.get(language, _GENERIC_PATTERNS)
    results: list[Relationship] = []

    for line_number, line in enumerate(content.splitlines(), start=1):
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                target = match.group("target")
                if target:
                    results.append(Relationship(
                        source=str(source_file),
                        target=target,
                        type=RelationshipType.IMPORT,
                        source_file=source_file,
                        line_number=line_number,
                    ))
                    break  # one import per line is enough

    return results
