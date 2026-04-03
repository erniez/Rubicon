"""File discovery and language detection."""

from hashlib import sha256
from pathlib import Path

from rubicon.crawler.ignore import load_gitignore
from rubicon.models import SourceFile

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
}


def detect_language(path: Path) -> str | None:
    """Detect programming language from file extension. Returns None for unknown."""
    return EXTENSION_MAP.get(path.suffix.lower())


def scan(root: Path, ignore: list[str] | None = None) -> list[SourceFile]:
    """Walk the directory tree and return all recognized source files.

    Respects .gitignore, default excludes, and extra ignore patterns.
    Skips binary and unrecognized files.

    Args:
        root: Project root directory.
        ignore: Additional gitignore-style patterns from .rubicon config.
    """
    root = root.resolve()
    spec = load_gitignore(root, extra_patterns=ignore)
    results: list[SourceFile] = []

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(root)
        if spec.match_file(str(relative)):
            continue

        language = detect_language(file_path)
        if language is None:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        file_hash = sha256(content.encode()).hexdigest()
        results.append(SourceFile(
            path=relative,
            language=language,
            content=content,
            hash=file_hash,
        ))

    return results
