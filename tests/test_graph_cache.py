"""Tests for the graph cache (save/load/invalidation)."""

import json
import os
import time
from pathlib import Path

import networkx as nx
import pytest

from rubicon.graph.cache import is_cache_valid, load_graph_cache, save_graph_cache
from rubicon.models import Relationship, RelationshipType, SourceFile


def _make_source_file(path: Path) -> SourceFile:
    return SourceFile(path=path, language="python", content="", hash="")


def _make_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_node("domain/model.py", file_path=Path("domain/model.py"), language="python",
               symbols=[], layer="domain")
    g.add_node("services/order.py", file_path=Path("services/order.py"), language="python",
               symbols=[], layer="services")
    rel = Relationship(
        source="Order", target="Model",
        type=RelationshipType.IMPORT,
        source_file=Path("services/order.py"),
        line_number=1,
    )
    g.add_edge("services/order.py", "domain/model.py", relationships=[rel])
    return g


class TestSaveLoadRoundTrip:
    def test_nodes_preserved(self, tmp_path: Path) -> None:
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)
        loaded = load_graph_cache(tmp_path)
        assert loaded is not None
        assert set(loaded.nodes) == {"domain/model.py", "services/order.py"}

    def test_node_layer_attribute_preserved(self, tmp_path: Path) -> None:
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)
        loaded = load_graph_cache(tmp_path)
        assert loaded is not None
        assert loaded.nodes["domain/model.py"]["layer"] == "domain"
        assert loaded.nodes["services/order.py"]["layer"] == "services"

    def test_edges_preserved(self, tmp_path: Path) -> None:
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)
        loaded = load_graph_cache(tmp_path)
        assert loaded is not None
        assert loaded.has_edge("services/order.py", "domain/model.py")

    def test_edge_relationships_reconstructed_as_relationship_objects(self, tmp_path: Path) -> None:
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)
        loaded = load_graph_cache(tmp_path)
        assert loaded is not None
        rels = loaded["services/order.py"]["domain/model.py"]["relationships"]
        assert len(rels) == 1
        # Must be a proper Relationship object, not a raw dict
        assert isinstance(rels[0], Relationship)
        assert rels[0].type == RelationshipType.IMPORT

    def test_creates_rubicon_data_directory(self, tmp_path: Path) -> None:
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)
        assert (tmp_path / ".rubicon_data" / "graph_cache.json").is_file()

    def test_load_returns_none_when_no_cache(self, tmp_path: Path) -> None:
        assert load_graph_cache(tmp_path) is None

    def test_load_returns_none_on_corrupt_file(self, tmp_path: Path) -> None:
        (tmp_path / ".rubicon_data").mkdir()
        (tmp_path / ".rubicon_data" / "graph_cache.json").write_text("NOT JSON {{{")
        assert load_graph_cache(tmp_path) is None


class TestIsCacheValid:
    def _write_source_files(self, tmp_path: Path) -> list[SourceFile]:
        (tmp_path / "domain").mkdir()
        (tmp_path / "domain" / "model.py").write_text("# model")
        (tmp_path / "services").mkdir()
        (tmp_path / "services" / "order.py").write_text("# order")
        return [
            _make_source_file(Path("domain/model.py")),
            _make_source_file(Path("services/order.py")),
        ]

    def test_valid_on_unchanged_files(self, tmp_path: Path) -> None:
        files = self._write_source_files(tmp_path)
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)
        assert is_cache_valid(tmp_path, files) is True

    def test_invalid_when_file_modified(self, tmp_path: Path) -> None:
        files = self._write_source_files(tmp_path)
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)

        # Modify mtime of one file slightly into the future
        target = tmp_path / "domain" / "model.py"
        new_mtime = target.stat().st_mtime + 1.0
        os.utime(target, (new_mtime, new_mtime))

        assert is_cache_valid(tmp_path, files) is False

    def test_invalid_when_file_added(self, tmp_path: Path) -> None:
        files = self._write_source_files(tmp_path)
        graph = _make_graph()
        save_graph_cache(graph, tmp_path)

        # Add a new source file after saving cache
        (tmp_path / "domain" / "new.py").write_text("")
        new_sf = _make_source_file(Path("domain/new.py"))
        files_with_new = files + [new_sf]

        assert is_cache_valid(tmp_path, files_with_new) is False

    def test_invalid_when_no_cache_file(self, tmp_path: Path) -> None:
        files = self._write_source_files(tmp_path)
        assert is_cache_valid(tmp_path, files) is False
