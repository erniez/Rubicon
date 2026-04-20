"""Tests for preflight data models and JSON serialisation."""

import json

from rubicon.preflight.models import (
    AllowedImportsResult,
    BatchPreflightResult,
    PreflightResult,
    PreflightViolation,
)


class TestPreflightViolation:
    def test_to_dict_contains_all_fields(self) -> None:
        v = PreflightViolation(rule="no_upward_dependency", severity="warning", message="bad import")
        d = v.to_dict()
        assert d == {"rule": "no_upward_dependency", "severity": "warning", "message": "bad import"}

    def test_json_serialisable(self) -> None:
        v = PreflightViolation(rule="no_layer_skipping", severity="warning", message="skip")
        assert json.dumps(v.to_dict())  # must not raise


class TestPreflightResult:
    def _make(self, allowed: bool = True, violations: tuple = ()) -> PreflightResult:
        return PreflightResult(
            allowed=allowed,
            source="services/user.py",
            source_layer="services",
            target="domain/model.py",
            target_layer="domain",
            relationship_type="import",
            violations=violations,
            cycle_detection_run=False,
        )

    def test_to_dict_allowed_true(self) -> None:
        r = self._make(allowed=True)
        d = r.to_dict()
        assert d["allowed"] is True
        assert d["violations"] == []
        assert d["cycle_detection_run"] is False

    def test_to_dict_with_violations(self) -> None:
        v = PreflightViolation(rule="no_upward_dependency", severity="warning", message="upward")
        r = self._make(allowed=False, violations=(v,))
        d = r.to_dict()
        assert d["allowed"] is False
        assert len(d["violations"]) == 1
        assert d["violations"][0]["rule"] == "no_upward_dependency"

    def test_to_dict_nested_violations_json_serialisable(self) -> None:
        v = PreflightViolation(rule="no_upward_dependency", severity="warning", message="x")
        r = self._make(allowed=False, violations=(v,))
        assert json.dumps(r.to_dict())

    def test_source_layer_none(self) -> None:
        r = PreflightResult(
            allowed=False,
            source="unknown/file.py",
            source_layer=None,
            target="domain/model.py",
            target_layer="domain",
            relationship_type="import",
            violations=(),
            cycle_detection_run=False,
        )
        d = r.to_dict()
        assert d["source_layer"] is None
        assert json.dumps(d)  # None serialises to null


class TestAllowedImportsResult:
    def test_to_dict_shape(self) -> None:
        r = AllowedImportsResult(
            source="services/user.py",
            source_layer="services",
            allowed_layers=("domain", "foundation"),
            forbidden_layers=({"layer": "presentation", "reason": "no_upward_dependency"},),
        )
        d = r.to_dict()
        assert d["source_layer"] == "services"
        assert d["allowed_layers"] == ["domain", "foundation"]
        assert d["forbidden_layers"] == [{"layer": "presentation", "reason": "no_upward_dependency"}]

    def test_json_serialisable(self) -> None:
        r = AllowedImportsResult(
            source="a.py", source_layer=None, allowed_layers=(), forbidden_layers=()
        )
        assert json.dumps(r.to_dict())


class TestBatchPreflightResult:
    def test_all_allowed_true(self) -> None:
        r1 = PreflightResult(
            allowed=True, source="a.py", source_layer="s", target="b.py", target_layer="d",
            relationship_type="import", violations=(), cycle_detection_run=False,
        )
        batch = BatchPreflightResult(all_allowed=True, results=(r1,))
        d = batch.to_dict()
        assert d["all_allowed"] is True
        assert len(d["results"]) == 1

    def test_all_allowed_false_when_any_violation(self) -> None:
        v = PreflightViolation(rule="no_upward_dependency", severity="warning", message="x")
        r1 = PreflightResult(
            allowed=False, source="a.py", source_layer="d", target="b.py", target_layer="p",
            relationship_type="import", violations=(v,), cycle_detection_run=False,
        )
        batch = BatchPreflightResult(all_allowed=False, results=(r1,))
        d = batch.to_dict()
        assert d["all_allowed"] is False
        assert d["results"][0]["allowed"] is False

    def test_json_serialisable(self) -> None:
        batch = BatchPreflightResult(all_allowed=True, results=())
        assert json.dumps(batch.to_dict())
