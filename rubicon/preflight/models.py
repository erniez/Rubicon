"""Data models for pre-flight import validation results."""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PreflightViolation:
    """A single rule violation detected during pre-flight checking."""

    rule: str
    severity: str  # "error" | "warning" | "info"
    message: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class PreflightResult:
    """Result of a single pre-flight import check."""

    allowed: bool
    source: str
    source_layer: str | None
    target: str
    target_layer: str | None
    relationship_type: str
    violations: tuple[PreflightViolation, ...]
    cycle_detection_run: bool

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "source": self.source,
            "source_layer": self.source_layer,
            "target": self.target,
            "target_layer": self.target_layer,
            "relationship_type": self.relationship_type,
            "violations": [v.to_dict() for v in self.violations],
            "cycle_detection_run": self.cycle_detection_run,
        }


@dataclass(frozen=True)
class AllowedImportsResult:
    """Result of an allowlist query for a source file."""

    source: str
    source_layer: str | None
    allowed_layers: tuple[str, ...]
    forbidden_layers: tuple[dict, ...]  # [{"layer": str, "reason": str}, ...]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_layer": self.source_layer,
            "allowed_layers": list(self.allowed_layers),
            "forbidden_layers": list(self.forbidden_layers),
        }


@dataclass(frozen=True)
class BatchPreflightResult:
    """Result of a batch pre-flight check covering multiple proposed changes."""

    all_allowed: bool
    results: tuple[PreflightResult, ...]

    def to_dict(self) -> dict:
        return {
            "all_allowed": self.all_allowed,
            "results": [r.to_dict() for r in self.results],
        }
