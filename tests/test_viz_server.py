"""Tests for rubicon.viz.server — FastAPI endpoints using TestClient."""

from pathlib import Path

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from rubicon.classifier.config import LayerConfig, RubiconConfig
from rubicon.graph.models import Relationship, RelationshipType, Severity, Violation
from rubicon.snapshot.diff import SnapshotDiff
from rubicon.viz.server import app, configure


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config() -> RubiconConfig:
    return RubiconConfig(
        layers={
            "presentation": LayerConfig(directories=["app/ui/"], color="#4A90D9"),
            "domain": LayerConfig(directories=["app/models/"], color="#50C878"),
            "data": LayerConfig(directories=["app/db/"], color="#E8A838"),
        },
        layer_order=["presentation", "domain", "data"],
        rules=["no_upward_dependency", "orphan_detection"],
    )


def _make_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    nodes = [
        ("app/ui/screen.py", "python", "presentation", ["Screen"]),
        ("app/models/user.py", "python", "domain", ["User"]),
        ("app/db/repo.py", "python", "data", ["Repo"]),
    ]
    for node_id, lang, layer, symbols in nodes:
        g.add_node(
            node_id,
            file_path=Path(node_id),
            language=lang,
            layer=layer,
            symbols=symbols,
        )

    g.add_edge("app/ui/screen.py", "app/models/user.py", relationships=[
        Relationship("Screen", "User", RelationshipType.IMPORT, Path("app/ui/screen.py"), 1),
    ])
    g.add_edge("app/models/user.py", "app/db/repo.py", relationships=[
        Relationship("User", "Repo", RelationshipType.IMPORT, Path("app/models/user.py"), 2),
    ])

    return g


def _make_violations() -> list[Violation]:
    return [
        Violation(
            rule="no_upward_dependency",
            severity=Severity.WARNING,
            source_node_id="app/db/repo.py",
            target_node_id="app/models/user.py",
            message="data imports from domain",
        ),
    ]


@pytest.fixture(autouse=True)
def _configure_server() -> None:
    """Configure the server module state before each test."""
    graph = _make_graph()
    config = _make_config()
    violations = _make_violations()
    configure(graph, config, violations, diff=None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: GET /api/layers
# ---------------------------------------------------------------------------

class TestApiLayers:
    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/layers")
        assert response.status_code == 200

    def test_returns_json(self, client: TestClient) -> None:
        response = client.get("/api/layers")
        data = response.json()
        assert "layers" in data
        assert "edges" in data
        assert "violations" in data

    def test_contains_expected_layers(self, client: TestClient) -> None:
        data = client.get("/api/layers").json()
        layer_names = [l["name"] for l in data["layers"]]
        assert "presentation" in layer_names
        assert "domain" in layer_names
        assert "data" in layer_names

    def test_layer_file_counts(self, client: TestClient) -> None:
        data = client.get("/api/layers").json()
        counts = {l["name"]: l["file_count"] for l in data["layers"]}
        assert counts["presentation"] == 1
        assert counts["domain"] == 1
        assert counts["data"] == 1

    def test_inter_layer_edges(self, client: TestClient) -> None:
        data = client.get("/api/layers").json()
        edge_pairs = {(e["source"], e["target"]) for e in data["edges"]}
        assert ("presentation", "domain") in edge_pairs
        assert ("domain", "data") in edge_pairs


# ---------------------------------------------------------------------------
# Tests: GET /api/files
# ---------------------------------------------------------------------------

class TestApiFiles:
    def test_single_layer(self, client: TestClient) -> None:
        data = client.get("/api/files?layer=domain").json()
        node_ids = {n["id"] for n in data["nodes"]}
        assert "app/models/user.py" in node_ids

    def test_cross_layer(self, client: TestClient) -> None:
        data = client.get(
            "/api/files?source_layer=presentation&target_layer=domain"
        ).json()
        node_ids = {n["id"] for n in data["nodes"]}
        assert "app/ui/screen.py" in node_ids
        assert "app/models/user.py" in node_ids

    def test_nonexistent_layer_returns_empty(self, client: TestClient) -> None:
        data = client.get("/api/files?layer=nonexistent").json()
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_returns_200_for_nonexistent_layer(self, client: TestClient) -> None:
        response = client.get("/api/files?layer=nonexistent")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: GET /api/file/{file_id}
# ---------------------------------------------------------------------------

class TestApiFile:
    def test_returns_ratsnest_data(self, client: TestClient) -> None:
        data = client.get("/api/file/app/models/user.py").json()
        assert data["focus"]["id"] == "app/models/user.py"

    def test_includes_neighbors(self, client: TestClient) -> None:
        data = client.get("/api/file/app/models/user.py").json()
        neighbor_ids = {n["id"] for n in data["neighbors"]}
        assert "app/ui/screen.py" in neighbor_ids
        assert "app/db/repo.py" in neighbor_ids

    def test_nonexistent_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/file/nonexistent.py")
        assert response.status_code == 404

    def test_nested_path(self, client: TestClient) -> None:
        """File paths with slashes should work via the path parameter."""
        response = client.get("/api/file/app/ui/screen.py")
        assert response.status_code == 200
        data = response.json()
        assert data["focus"]["id"] == "app/ui/screen.py"


# ---------------------------------------------------------------------------
# Tests: GET /api/diff
# ---------------------------------------------------------------------------

class TestApiDiff:
    def test_no_diff_returns_disabled(self, client: TestClient) -> None:
        data = client.get("/api/diff").json()
        assert data["enabled"] is False

    def test_with_diff_returns_enabled(self, client: TestClient) -> None:
        diff = SnapshotDiff(
            added_edges=[{"source": "a.py", "target": "b.py"}],
            summary="+1 connection",
        )
        configure(_make_graph(), _make_config(), _make_violations(), diff=diff)
        data = client.get("/api/diff").json()
        assert data["enabled"] is True
        assert len(data["added_edges"]) == 1
        assert data["summary"] == "+1 connection"


# ---------------------------------------------------------------------------
# Tests: GET /api/config
# ---------------------------------------------------------------------------

class TestApiConfig:
    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/config")
        assert response.status_code == 200

    def test_contains_layer_order(self, client: TestClient) -> None:
        data = client.get("/api/config").json()
        assert "layer_order" in data
        assert data["layer_order"] == ["presentation", "domain", "data"]

    def test_contains_layer_colors(self, client: TestClient) -> None:
        data = client.get("/api/config").json()
        assert "layer_colors" in data
        assert data["layer_colors"]["presentation"] == "#4A90D9"

    def test_contains_rules(self, client: TestClient) -> None:
        data = client.get("/api/config").json()
        assert "rules" in data
        assert "no_upward_dependency" in data["rules"]


# ---------------------------------------------------------------------------
# Tests: configure() function
# ---------------------------------------------------------------------------

class TestConfigure:
    def test_state_is_set(self, client: TestClient) -> None:
        """After configure(), endpoints should return data from the provided graph."""
        graph = nx.DiGraph()
        graph.add_node("only.py", file_path=Path("only.py"), language="python", layer="solo", symbols=[])
        config = RubiconConfig(
            layers={"solo": LayerConfig(directories=[""], color="#aaa")},
            layer_order=["solo"],
        )
        configure(graph, config, [])

        data = client.get("/api/layers").json()
        assert len(data["layers"]) == 1
        assert data["layers"][0]["name"] == "solo"


# ---------------------------------------------------------------------------
# Tests: Static file serving
# ---------------------------------------------------------------------------

class TestStaticFiles:
    def test_index_returns_200(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_index_returns_html(self, client: TestClient) -> None:
        response = client.get("/")
        assert "text/html" in response.headers.get("content-type", "")

    def test_index_contains_rubicon(self, client: TestClient) -> None:
        response = client.get("/")
        assert "Rubicon" in response.text

    def test_css_returns_200(self, client: TestClient) -> None:
        response = client.get("/static/styles.css")
        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")

    def test_js_returns_200(self, client: TestClient) -> None:
        response = client.get("/static/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "")

    def test_index_references_d3(self, client: TestClient) -> None:
        """index.html should load D3.js from CDN."""
        response = client.get("/")
        assert "d3.v7" in response.text

    def test_index_references_app_js(self, client: TestClient) -> None:
        """index.html should load our app.js."""
        response = client.get("/")
        assert "app.js" in response.text

    def test_index_references_styles(self, client: TestClient) -> None:
        """index.html should load styles.css."""
        response = client.get("/")
        assert "styles.css" in response.text
