"""Graph cache for fast pre-flight cycle detection.

Serialises a NetworkX DiGraph to .rubicon_data/graph_cache.json alongside a
file-mtime fingerprint. On subsequent runs the cache is loaded instead of
rebuilding the full graph from scratch, reducing pre-flight latency from
seconds to milliseconds on warm paths.
"""

import json
import logging
from pathlib import Path

import networkx as nx

from rubicon.models import Relationship, RelationshipType, SourceFile

logger = logging.getLogger(__name__)

CACHE_FILE = ".rubicon_data/graph_cache.json"


def save_graph_cache(graph: nx.DiGraph, root: Path) -> None:
    """Serialise graph and file-mtime fingerprint to .rubicon_data/graph_cache.json.

    Creates .rubicon_data/ if it does not exist.
    """
    cache_path = root / CACHE_FILE
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    nodes = {
        node_id: {
            "layer": data.get("layer", "unclassified"),
            "language": data.get("language", ""),
        }
        for node_id, data in graph.nodes(data=True)
    }

    edges = []
    for src, tgt, data in graph.edges(data=True):
        rels = [
            {"type": rel.type.value}
            for rel in data.get("relationships", [])
        ]
        edges.append([src, tgt, rels])

    # Build fingerprint: path → mtime for all nodes that exist on disk
    fingerprint: dict[str, float] = {}
    for node_id in graph.nodes:
        p = root / node_id
        if p.is_file():
            fingerprint[node_id] = p.stat().st_mtime

    payload = {"fingerprint": fingerprint, "nodes": nodes, "edges": edges}
    cache_path.write_text(json.dumps(payload))


def load_graph_cache(root: Path) -> nx.DiGraph | None:
    """Deserialise a cached graph. Returns None if the cache is missing or corrupt."""
    cache_path = root / CACHE_FILE
    if not cache_path.is_file():
        return None

    try:
        payload = json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Could not load graph cache: %s", exc)
        return None

    graph = nx.DiGraph()

    for node_id, attrs in payload.get("nodes", {}).items():
        graph.add_node(
            node_id,
            file_path=Path(node_id),
            language=attrs.get("language", ""),
            symbols=[],
            layer=attrs.get("layer", "unclassified"),
        )

    for src, tgt, rel_dicts in payload.get("edges", []):
        relationships = [
            Relationship(
                source="",
                target="",
                type=RelationshipType(r["type"]),
                source_file=Path("."),
                line_number=0,
            )
            for r in rel_dicts
        ]
        if src in graph and tgt in graph:
            graph.add_edge(src, tgt, relationships=relationships)

    return graph


def is_cache_valid(root: Path, files: list[SourceFile]) -> bool:
    """Return True if the on-disk cache matches the current file set.

    Compares the stored mtime fingerprint against the current files list.
    Returns False if the cache is missing, corrupt, or any file has been
    added, removed, or modified since the cache was written.
    """
    cache_path = root / CACHE_FILE
    if not cache_path.is_file():
        return False

    try:
        payload = json.loads(cache_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    fingerprint: dict[str, float] = payload.get("fingerprint", {})

    current_paths = {str(f.path) for f in files}

    # Check for added or modified files
    for path_str in current_paths:
        cached_mtime = fingerprint.get(path_str)
        if cached_mtime is None:
            return False  # new file not in cache
        try:
            if (root / path_str).stat().st_mtime != cached_mtime:
                return False  # file was modified
        except OSError:
            return False

    # Check for removed files
    if set(fingerprint.keys()) != current_paths:
        return False

    return True
