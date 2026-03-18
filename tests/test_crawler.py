"""Tests for the file crawler."""

from pathlib import Path

from rubicon.crawler.scanner import detect_language, scan
from rubicon.models import SourceFile

FIXTURES = Path(__file__).parent / "fixtures" / "sample_project"


class TestDetectLanguage:
    def test_python(self) -> None:
        assert detect_language(Path("app.py")) == "python"

    def test_typescript(self) -> None:
        assert detect_language(Path("index.ts")) == "typescript"

    def test_tsx(self) -> None:
        assert detect_language(Path("App.tsx")) == "tsx"

    def test_kotlin(self) -> None:
        assert detect_language(Path("Model.kt")) == "kotlin"

    def test_swift(self) -> None:
        assert detect_language(Path("View.swift")) == "swift"

    def test_unknown_extension(self) -> None:
        assert detect_language(Path("README.md")) is None

    def test_no_extension(self) -> None:
        assert detect_language(Path("Makefile")) is None


class TestScan:
    def test_finds_source_files(self) -> None:
        files = scan(FIXTURES)
        paths = {str(f.path) for f in files}
        assert "src/app.py" in paths
        assert "src/utils.py" in paths
        assert "src/index.ts" in paths
        assert "src/Model.kt" in paths
        assert "src/View.swift" in paths

    def test_detects_correct_languages(self) -> None:
        files = scan(FIXTURES)
        by_path = {str(f.path): f for f in files}
        assert by_path["src/app.py"].language == "python"
        assert by_path["src/index.ts"].language == "typescript"
        assert by_path["src/Model.kt"].language == "kotlin"
        assert by_path["src/View.swift"].language == "swift"

    def test_excludes_node_modules(self) -> None:
        files = scan(FIXTURES)
        paths = {str(f.path) for f in files}
        assert not any("node_modules" in p for p in paths)

    def test_excludes_build(self) -> None:
        files = scan(FIXTURES)
        paths = {str(f.path) for f in files}
        assert not any("build" in p for p in paths)

    def test_excludes_pycache(self) -> None:
        files = scan(FIXTURES)
        paths = {str(f.path) for f in files}
        assert not any("__pycache__" in p for p in paths)

    def test_excludes_gitignore_patterns(self) -> None:
        files = scan(FIXTURES)
        paths = {str(f.path) for f in files}
        assert not any(p.endswith(".log") for p in paths)

    def test_skips_non_source_files(self) -> None:
        files = scan(FIXTURES)
        paths = {str(f.path) for f in files}
        assert not any(p.endswith(".md") for p in paths)

    def test_file_count(self) -> None:
        files = scan(FIXTURES)
        assert len(files) == 5

    def test_content_is_populated(self) -> None:
        files = scan(FIXTURES)
        for f in files:
            assert len(f.content) > 0

    def test_hash_is_consistent(self) -> None:
        files1 = scan(FIXTURES)
        files2 = scan(FIXTURES)
        hashes1 = {str(f.path): f.hash for f in files1}
        hashes2 = {str(f.path): f.hash for f in files2}
        assert hashes1 == hashes2

    def test_paths_are_relative(self) -> None:
        files = scan(FIXTURES)
        for f in files:
            assert not f.path.is_absolute()

    def test_source_file_is_frozen(self) -> None:
        files = scan(FIXTURES)
        f = files[0]
        try:
            f.language = "go"  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass
