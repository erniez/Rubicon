"""Tests for snapshot store (save/load/list)."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from rubicon.snapshot.models import Snapshot, snapshot_to_dict
from rubicon.snapshot.store import (
    get_commit_hash,
    list_snapshots,
    load_latest_snapshot,
    load_snapshot,
    resolve_snapshot,
    save_snapshot,
)


def _make_snapshot(commit_hash: str | None = "abc123") -> Snapshot:
    return Snapshot(
        timestamp=datetime.now(timezone.utc),
        commit_hash=commit_hash,
        nodes=[{"id": "a.py", "file_path": "a.py", "language": "python", "layer": "domain", "symbols": []}],
        edges=[{"source": "a.py", "target": "b.py", "relationships": []}],
        violations=[],
        layer_map={"a.py": "domain"},
    )


class TestSaveSnapshot:
    def test_creates_directory_and_file(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        result = save_snapshot(tmp_path, snapshot)

        assert result.exists()
        assert result.suffix == ".json"
        assert (tmp_path / ".rubicon_data" / "snapshots").is_dir()

    def test_file_contains_valid_json(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        result = save_snapshot(tmp_path, snapshot)

        data = json.loads(result.read_text())
        assert data["commit_hash"] == "abc123"
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == "a.py"

    def test_saves_multiple_snapshots(self, tmp_path: Path) -> None:
        s1 = _make_snapshot()
        save_snapshot(tmp_path, s1)

        time.sleep(1.1)  # ensure different timestamp in filename

        s2 = _make_snapshot(commit_hash="def456")
        save_snapshot(tmp_path, s2)

        files = list((tmp_path / ".rubicon_data" / "snapshots").glob("*.json"))
        assert len(files) == 2


class TestLoadSnapshot:
    def test_round_trip(self, tmp_path: Path) -> None:
        original = _make_snapshot()
        path = save_snapshot(tmp_path, original)

        loaded = load_snapshot(path)

        assert loaded.commit_hash == original.commit_hash
        assert loaded.nodes == original.nodes
        assert loaded.edges == original.edges
        assert loaded.violations == original.violations
        assert loaded.layer_map == original.layer_map
        assert loaded.timestamp == original.timestamp


class TestLoadLatestSnapshot:
    def test_returns_none_when_no_snapshots(self, tmp_path: Path) -> None:
        result = load_latest_snapshot(tmp_path)
        assert result is None

    def test_returns_none_when_dir_missing(self, tmp_path: Path) -> None:
        result = load_latest_snapshot(tmp_path / "nonexistent")
        assert result is None

    def test_returns_most_recent(self, tmp_path: Path) -> None:
        s1 = _make_snapshot(commit_hash="first")
        save_snapshot(tmp_path, s1)

        time.sleep(1.1)

        s2 = _make_snapshot(commit_hash="second")
        save_snapshot(tmp_path, s2)

        latest = load_latest_snapshot(tmp_path)
        assert latest is not None
        assert latest.commit_hash == "second"


class TestListSnapshots:
    def test_empty_directory(self, tmp_path: Path) -> None:
        assert list_snapshots(tmp_path) == []

    def test_returns_sorted(self, tmp_path: Path) -> None:
        s1 = _make_snapshot()
        save_snapshot(tmp_path, s1)

        time.sleep(1.1)

        s2 = _make_snapshot(commit_hash="second")
        save_snapshot(tmp_path, s2)

        snapshots = list_snapshots(tmp_path)
        assert len(snapshots) == 2
        assert snapshots[0].name < snapshots[1].name


class TestResolveSnapshot:
    def test_returns_none_when_no_snapshots(self, tmp_path: Path) -> None:
        assert resolve_snapshot(tmp_path, "1") is None

    def test_positive_index(self, tmp_path: Path) -> None:
        s1 = _make_snapshot(commit_hash="first")
        save_snapshot(tmp_path, s1)

        time.sleep(1.1)

        s2 = _make_snapshot(commit_hash="second")
        save_snapshot(tmp_path, s2)

        result = resolve_snapshot(tmp_path, "1")
        assert result is not None
        assert result.commit_hash == "first"

        result = resolve_snapshot(tmp_path, "2")
        assert result is not None
        assert result.commit_hash == "second"

    def test_negative_index(self, tmp_path: Path) -> None:
        s1 = _make_snapshot(commit_hash="first")
        save_snapshot(tmp_path, s1)

        time.sleep(1.1)

        s2 = _make_snapshot(commit_hash="second")
        save_snapshot(tmp_path, s2)

        result = resolve_snapshot(tmp_path, "-1")
        assert result is not None
        assert result.commit_hash == "second"

        result = resolve_snapshot(tmp_path, "-2")
        assert result is not None
        assert result.commit_hash == "first"

    def test_by_filename(self, tmp_path: Path) -> None:
        s1 = _make_snapshot(commit_hash="target")
        path = save_snapshot(tmp_path, s1)

        result = resolve_snapshot(tmp_path, path.name)
        assert result is not None
        assert result.commit_hash == "target"

    def test_by_timestamp_prefix(self, tmp_path: Path) -> None:
        s1 = _make_snapshot(commit_hash="target")
        path = save_snapshot(tmp_path, s1)

        # Use the date portion of the filename as a prefix
        prefix = path.stem[:8]  # e.g. "20260318"
        result = resolve_snapshot(tmp_path, prefix)
        assert result is not None
        assert result.commit_hash == "target"

    def test_invalid_index_returns_none(self, tmp_path: Path) -> None:
        s1 = _make_snapshot()
        save_snapshot(tmp_path, s1)

        assert resolve_snapshot(tmp_path, "99") is None

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        s1 = _make_snapshot()
        save_snapshot(tmp_path, s1)

        assert resolve_snapshot(tmp_path, "nonexistent") is None


class TestGetCommitHash:
    def test_returns_hash_in_git_repo(self) -> None:
        # Run against Rubicon's own repo
        root = Path(__file__).parent.parent
        result = get_commit_hash(root)
        assert result is not None
        assert len(result) == 40  # full SHA

    def test_returns_none_outside_git_repo(self, tmp_path: Path) -> None:
        result = get_commit_hash(tmp_path)
        assert result is None
