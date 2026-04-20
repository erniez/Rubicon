"""Tests for preflight path classifier and import resolver."""

from pathlib import Path

import pytest

from rubicon.models import LayerConfig, RubiconConfig
from rubicon.preflight.resolver import classify_path, resolve_import_target


def _make_config() -> RubiconConfig:
    return RubiconConfig(
        layers={
            "presentation": LayerConfig(directories=["ui/"], patterns=[]),
            "services": LayerConfig(directories=["services/"], patterns=[]),
            "domain": LayerConfig(directories=["domain/"], patterns=[]),
            "foundation": LayerConfig(directories=["foundation/"], patterns=[]),
        },
        layer_order=["presentation", "services", "domain", "foundation"],
    )


def _make_config_with_patterns() -> RubiconConfig:
    return RubiconConfig(
        layers={
            "domain": LayerConfig(
                directories=["domain/"],
                patterns=["*Interactor*", "*UseCase*"],
            ),
        },
        layer_order=["domain"],
    )


# ── classify_path ─────────────────────────────────────────────────────────────


class TestClassifyPath:
    def test_classifies_by_directory_prefix(self) -> None:
        config = _make_config()
        assert classify_path("services/user.py", config) == "services"

    def test_classifies_file_that_does_not_exist_on_disk(self) -> None:
        # File need not exist — classification is path-only
        config = _make_config()
        assert classify_path("domain/brand_new_model.py", config) == "domain"

    def test_returns_none_for_unclassified_path(self) -> None:
        config = _make_config()
        assert classify_path("unknown/thing.py", config) is None

    def test_accepts_path_object(self) -> None:
        config = _make_config()
        assert classify_path(Path("ui/screen.py"), config) == "presentation"

    def test_classifies_by_filename_pattern(self) -> None:
        config = _make_config_with_patterns()
        assert classify_path("some/dir/UserInteractor.py", config) == "domain"

    def test_pattern_takes_priority_over_directory(self) -> None:
        # File is in services/ dir but matches domain pattern
        config = RubiconConfig(
            layers={
                "services": LayerConfig(directories=["services/"], patterns=[]),
                "domain": LayerConfig(directories=["domain/"], patterns=["*UseCase*"]),
            },
            layer_order=["services", "domain"],
        )
        assert classify_path("services/CreateOrderUseCase.py", config) == "domain"

    def test_nested_path_within_layer_directory(self) -> None:
        config = _make_config()
        assert classify_path("domain/user/profile/model.py", config) == "domain"


# ── resolve_import_target ──────────────────────────────────────────────────────


class TestResolveImportTarget:
    def test_python_dotted_import_resolves_to_file_on_disk(self, tmp_path: Path) -> None:
        config = _make_config()
        (tmp_path / "domain").mkdir()
        (tmp_path / "domain" / "models.py").write_text("")

        path, layer = resolve_import_target("domain.models", tmp_path, config)
        assert layer == "domain"
        assert path is not None and "domain" in path

    def test_typescript_at_alias_resolves(self, tmp_path: Path) -> None:
        # @/ alias maps to src/ — config must recognise src/domain/ as domain layer
        config = RubiconConfig(
            layers={
                "domain": LayerConfig(directories=["src/domain/"], patterns=[]),
            },
            layer_order=["domain"],
        )
        (tmp_path / "src" / "domain").mkdir(parents=True)
        (tmp_path / "src" / "domain" / "models.ts").write_text("")

        path, layer = resolve_import_target("@/domain/models", tmp_path, config)
        assert layer == "domain"

    def test_package_path_strips_prefix_and_resolves(self, tmp_path: Path) -> None:
        # Tests the "strip leading segments" logic: com.example.domain.models
        # tries candidates including domain/models.py after stripping com/example
        config = _make_config()
        (tmp_path / "domain").mkdir()
        (tmp_path / "domain" / "models.py").write_text("")

        path, layer = resolve_import_target(
            "com.example.domain.models", tmp_path, config
        )
        assert layer == "domain"

    def test_init_py_variant_resolves(self, tmp_path: Path) -> None:
        config = _make_config()
        (tmp_path / "domain").mkdir()
        (tmp_path / "domain" / "__init__.py").write_text("")

        path, layer = resolve_import_target("domain", tmp_path, config)
        assert layer == "domain"

    def test_relative_import_resolves(self, tmp_path: Path) -> None:
        config = _make_config()
        (tmp_path / "domain").mkdir()
        (tmp_path / "domain" / "models.py").write_text("")

        path, layer = resolve_import_target("./models", tmp_path, config)
        # Relative import can't be rooted without knowing caller location.
        # "models" alone won't match any layer directory prefix, so falls back to (None, None).
        assert (path, layer) == (None, None)

    def test_fallback_to_raw_path_classification(self) -> None:
        # No files on disk at all — resolve_import_target falls back to
        # classifying the import string as a path
        config = _make_config()
        path, layer = resolve_import_target("domain/model.py", Path("/nonexistent"), config)
        assert layer == "domain"
        assert path == "domain/model.py"

    def test_unresolvable_returns_none_none(self, tmp_path: Path) -> None:
        config = _make_config()
        path, layer = resolve_import_target("third_party.requests", tmp_path, config)
        assert path is None
        assert layer is None
