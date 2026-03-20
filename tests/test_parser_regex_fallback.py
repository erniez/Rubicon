"""Tests for the regex fallback parser."""

from pathlib import Path

from rubicon.models import RelationshipType
from rubicon.parser.treesitter import parse_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _targets(rels: list) -> set[str]:
    return {r.target for r in rels}


# ---------------------------------------------------------------------------
# Language-specific fallback patterns
# ---------------------------------------------------------------------------

class TestFallbackImports:
    """Verify that language-specific regex patterns fire for unknown adapters."""

    def test_perl_use(self) -> None:
        content = "use Moose;\nuse Data::Dumper;"
        rels = parse_file(Path("app.pl"), "perl", content)
        targets = _targets(rels)
        assert "Moose" in targets
        assert "Data::Dumper" in targets

    def test_lua_require(self) -> None:
        content = "require('socket')\nrequire 'json'"
        rels = parse_file(Path("main.lua"), "lua", content)
        targets = _targets(rels)
        assert "socket" in targets
        assert "json" in targets

    def test_dart_import(self) -> None:
        content = "import 'package:flutter/material.dart';"
        rels = parse_file(Path("main.dart"), "dart", content)
        targets = _targets(rels)
        assert "package:flutter/material.dart" in targets

    def test_scala_import(self) -> None:
        content = "import scala.collection.mutable\nimport com.example.Foo"
        rels = parse_file(Path("App.scala"), "scala", content)
        targets = _targets(rels)
        assert "scala.collection.mutable" in targets
        assert "com.example.Foo" in targets

    def test_elixir_import(self) -> None:
        content = "import Ecto.Query\nalias MyApp.Repo\nuse GenServer"
        rels = parse_file(Path("my_app.ex"), "elixir", content)
        targets = _targets(rels)
        assert "Ecto.Query" in targets
        assert "MyApp.Repo" in targets
        assert "GenServer" in targets


# ---------------------------------------------------------------------------
# Generic fallback patterns (language not in the dict)
# ---------------------------------------------------------------------------

class TestGenericFallback:
    """Verify that totally unknown languages still get generic matching."""

    def test_generic_import(self) -> None:
        rels = parse_file(Path("file.x"), "unknown_lang", "import foo.bar")
        targets = _targets(rels)
        assert "foo.bar" in targets

    def test_generic_require(self) -> None:
        rels = parse_file(Path("file.x"), "unknown_lang", "require 'some_lib'")
        targets = _targets(rels)
        assert "some_lib" in targets

    def test_generic_include(self) -> None:
        rels = parse_file(Path("file.x"), "unknown_lang", "#include <myheader.h>")
        targets = _targets(rels)
        assert "myheader.h" in targets

    def test_no_matches_returns_empty(self) -> None:
        rels = parse_file(Path("file.x"), "unknown_lang", "x = 1 + 2")
        assert rels == []


# ---------------------------------------------------------------------------
# Tree-sitter priority over regex
# ---------------------------------------------------------------------------

class TestTreeSitterTakesPriority:
    """Languages with tree-sitter adapters must NOT use the regex fallback."""

    def test_python_uses_treesitter(self) -> None:
        content = "class Dog(Animal):\n    pass\n"
        rels = parse_file(Path("animals.py"), "python", content)
        inheritance = [r for r in rels if r.type == RelationshipType.INHERITANCE]
        # Regex cannot produce inheritance -- tree-sitter can.
        assert len(inheritance) >= 1
        pairs = {(r.source, r.target) for r in inheritance}
        assert ("Dog", "Animal") in pairs


# ---------------------------------------------------------------------------
# Relationship field correctness
# ---------------------------------------------------------------------------

class TestRelationshipFields:
    """Verify the Relationship objects returned by the fallback are correct."""

    def test_source_is_file_path(self) -> None:
        src = Path("lib/utils.pl")
        rels = parse_file(src, "perl", "use Carp;")
        assert len(rels) == 1
        assert rels[0].source == str(src)

    def test_type_is_import(self) -> None:
        rels = parse_file(Path("f.lua"), "lua", "require('json')")
        for r in rels:
            assert r.type == RelationshipType.IMPORT

    def test_line_numbers(self) -> None:
        content = "-- comment\nrequire('a')\n\nrequire('b')"
        rels = parse_file(Path("f.lua"), "lua", content)
        lines = sorted(r.line_number for r in rels)
        assert lines == [2, 4]
