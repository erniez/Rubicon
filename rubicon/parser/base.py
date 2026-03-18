"""Abstract parser interface for language adapters."""

from pathlib import Path
from typing import Protocol

from rubicon.models import Relationship


class LanguageAdapter(Protocol):
    """Protocol that all language adapters must implement."""

    def extract_relationships(
        self, tree: object, source_file: Path, content: bytes
    ) -> list[Relationship]:
        """Extract all relationships from a parsed syntax tree.

        Args:
            tree: The tree-sitter parse tree.
            source_file: Relative path to the source file.
            content: Raw bytes of the source file.

        Returns:
            List of relationships found in the file.
        """
        ...
