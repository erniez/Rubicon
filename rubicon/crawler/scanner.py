"""File discovery and language detection."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from rubicon.crawler.ignore import load_gitignore

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
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


@dataclass(frozen=True)
class SourceFile:
    """A discovered source file with language and content."""

    path: Path
    language: str
    content: str
    hash: str


def detect_language(path: Path) -> str | None:
    """Detect programming language from file extension. Returns None for unknown."""
    return EXTENSION_MAP.get(path.suffix.lower())


def scan(root: Path) -> list[SourceFile]:
    """Walk the directory tree and return all recognized source files.

    Respects .gitignore and default excludes. Skips binary and
    unrecognized files.
    """
    root = root.resolve()
    spec = load_gitignore(root)
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
