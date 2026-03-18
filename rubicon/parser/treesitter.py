"""Tree-sitter based parsing driver."""

import logging
from pathlib import Path
from typing import Any, Callable

from tree_sitter import Language, Parser

from rubicon.models import Relationship

logger = logging.getLogger(__name__)

# Registry mapping language names to (tree-sitter language capsule, adapter extract function)
_ADAPTERS: dict[str, tuple[Callable[[], Any], Callable[..., list[Relationship]]]] = {}


def _register_adapters() -> None:
    """Lazily register all available language adapters."""
    if _ADAPTERS:
        return

    try:
        import tree_sitter_python as tsp
        from rubicon.parser.adapters.python import extract_relationships as py_extract
        _ADAPTERS["python"] = (tsp.language, py_extract)
    except ImportError:
        logger.debug("tree-sitter-python not available")

    try:
        import tree_sitter_typescript as tst
        from rubicon.parser.adapters.typescript import extract_relationships as ts_extract
        _ADAPTERS["typescript"] = (tst.language_typescript, ts_extract)
        _ADAPTERS["tsx"] = (tst.language_tsx, ts_extract)
    except ImportError:
        logger.debug("tree-sitter-typescript not available")

    try:
        import tree_sitter_kotlin as tsk
        from rubicon.parser.adapters.kotlin import extract_relationships as kt_extract
        _ADAPTERS["kotlin"] = (tsk.language, kt_extract)
    except ImportError:
        logger.debug("tree-sitter-kotlin not available")

    try:
        import tree_sitter_swift as tss
        from rubicon.parser.adapters.swift import extract_relationships as sw_extract
        _ADAPTERS["swift"] = (tss.language, sw_extract)
    except ImportError:
        logger.debug("tree-sitter-swift not available")


def parse_file(
    source_file: Path, language: str, content: str
) -> list[Relationship]:
    """Parse a single file and extract all relationships.

    Args:
        source_file: Relative path to the file.
        language: Language identifier (e.g. "python").
        content: File content as a string.

    Returns:
        List of extracted relationships. Empty list if language
        is unsupported or parsing fails.
    """
    _register_adapters()

    adapter = _ADAPTERS.get(language)
    if adapter is None:
        logger.debug("No adapter for language: %s", language)
        return []

    lang_fn, extract_fn = adapter
    ts_language = Language(lang_fn())
    parser = Parser(ts_language)

    content_bytes = content.encode("utf-8")
    try:
        tree = parser.parse(content_bytes)
    except Exception:
        logger.warning("Failed to parse %s", source_file, exc_info=True)
        return []

    if tree.root_node.has_error:
        logger.warning("Parse errors in %s", source_file)

    try:
        return extract_fn(tree, source_file, content_bytes)
    except Exception:
        logger.warning(
            "Failed to extract relationships from %s", source_file, exc_info=True
        )
        return []
