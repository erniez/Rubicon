"""Tests for snapshot diff engine."""

import json
from pathlib import Path

from rubicon.snapshot.diff import SnapshotDiff, diff_snapshots
from rubicon.snapshot.models import dict_to_snapshot

FIXTURES = Path(__file__).parent / "fixtures" / "snapshots"


def _load(name: str):
    return dict_to_snapshot(json.loads((FIXTURES / name).read_text()))


class TestDiffEdges:
    def test_added_edge(self) -> None:
        baseline = _load("baseline.json")
        current = _load("added_edge.json")

        diff = diff_snapshots(baseline, current)

        assert len(diff.added_edges) == 1
        added = diff.added_edges[0]
        assert added["source"] == "ui/widget.py"
        assert added["target"] == "db/repo.py"
        assert len(diff.removed_edges) == 0

    def test_removed_edge(self) -> None:
        baseline = _load("baseline.json")
        current = _load("removed_edge.json")

        diff = diff_snapshots(baseline, current)

        assert len(diff.removed_edges) == 1
        removed = diff.removed_edges[0]
        assert removed["source"] == "models/order.py"
        assert removed["target"] == "db/repo.py"
        assert len(diff.added_edges) == 0

    def test_identical_no_edge_changes(self) -> None:
        baseline = _load("baseline.json")
        identical = _load("identical.json")

        diff = diff_snapshots(baseline, identical)

        assert diff.added_edges == []
        assert diff.removed_edges == []


class TestDiffViolations:
    def test_new_violation(self) -> None:
        baseline = _load("baseline.json")
        current = _load("new_violation.json")

        diff = diff_snapshots(baseline, current)

        assert len(diff.new_violations) == 1
        new_v = diff.new_violations[0]
        assert new_v["rule"] == "no_layer_skipping"
        assert len(diff.resolved_violations) == 0

    def test_resolved_violation(self) -> None:
        baseline = _load("baseline.json")
        current = _load("resolved_violation.json")

        diff = diff_snapshots(baseline, current)

        assert len(diff.resolved_violations) == 1
        resolved = diff.resolved_violations[0]
        assert resolved["rule"] == "no_upward_dependency"
        assert len(diff.new_violations) == 0

    def test_identical_no_violation_changes(self) -> None:
        baseline = _load("baseline.json")
        identical = _load("identical.json")

        diff = diff_snapshots(baseline, identical)

        assert diff.new_violations == []
        assert diff.resolved_violations == []


class TestDiffNodes:
    def test_identical_no_node_changes(self) -> None:
        baseline = _load("baseline.json")
        identical = _load("identical.json")

        diff = diff_snapshots(baseline, identical)

        assert diff.added_nodes == []
        assert diff.removed_nodes == []


class TestDiffFromNothing:
    def test_none_previous_treats_all_as_added(self) -> None:
        current = _load("baseline.json")

        diff = diff_snapshots(None, current)

        assert len(diff.added_nodes) == 5
        assert len(diff.added_edges) == 6
        assert len(diff.new_violations) == 1
        assert diff.removed_edges == []
        assert diff.removed_nodes == []
        assert diff.resolved_violations == []


class TestSummary:
    def test_no_changes(self) -> None:
        baseline = _load("baseline.json")
        identical = _load("identical.json")

        diff = diff_snapshots(baseline, identical)

        assert diff.summary == "No changes"

    def test_added_edge_summary(self) -> None:
        baseline = _load("baseline.json")
        current = _load("added_edge.json")

        diff = diff_snapshots(baseline, current)

        assert "+1 connection" in diff.summary

    def test_removed_edge_summary(self) -> None:
        baseline = _load("baseline.json")
        current = _load("removed_edge.json")

        diff = diff_snapshots(baseline, current)

        assert "-1 connection" in diff.summary

    def test_new_violation_summary(self) -> None:
        baseline = _load("baseline.json")
        current = _load("new_violation.json")

        diff = diff_snapshots(baseline, current)

        assert "1 new violation" in diff.summary

    def test_resolved_violation_summary(self) -> None:
        baseline = _load("baseline.json")
        current = _load("resolved_violation.json")

        diff = diff_snapshots(baseline, current)

        assert "1 resolved violation" in diff.summary

    def test_first_run_summary(self) -> None:
        current = _load("baseline.json")

        diff = diff_snapshots(None, current)

        assert "+6 connections" in diff.summary
        assert "+5 files" in diff.summary
        assert "1 new violation" in diff.summary
