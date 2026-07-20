"""Base types shared by every validator.

Each validator is stateless: it receives the four internal model objects and
returns a :class:`ValidationResult`.  Validators must not print to stdout;
they must only log via the ``logging`` module and return structured data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ValidationIssue:
    """One structured error or warning produced by a validator.

    Attributes:
        code: Machine-readable error code (e.g. ``CAPABILITY_MISSING``).
        message: Human-readable description.
        action_index: Global action index this issue refers to, or ``-1``.
        checkpoint_id: Parent checkpoint, or ``-1``.
        severity: ``CRITICAL`` | ``ERROR`` | ``WARNING`` | ``INFO``.
        suggestion: Optional remediation hint.
        extra: Any additional key-value metadata.
    """
    code: str
    message: str
    action_index: int = -1
    checkpoint_id: int = -1
    severity: str = "ERROR"
    suggestion: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict suitable for JSON reports."""
        return {
            "code": self.code,
            "message": self.message,
            "action_index": self.action_index,
            "checkpoint_id": self.checkpoint_id,
            "severity": self.severity,
            "suggestion": self.suggestion,
            **self.extra,
        }


@dataclass
class ValidationResult:
    """Return value from every validator.

    Attributes:
        validator_name: Display name of the validator that produced this.
        raw_score: Un-normalised count-based score (0 – 1 float).
        normalised_score: Final 0 – 1 score used in the weighted average.
        status: ``PASS`` | ``WARNING`` | ``FAIL``.
        issues: Structured list of errors / warnings.
        comments: Free-text commentary for the report.
        extra: Arbitrary extra data specific to the validator.
    """
    validator_name: str
    raw_score: float = 1.0
    normalised_score: float = 1.0
    status: str = "PASS"
    issues: List[ValidationIssue] = field(default_factory=list)
    comments: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict suitable for JSON reports."""
        return {
            "validator": self.validator_name,
            "raw_score": round(self.raw_score, 4),
            "normalised_score": round(self.normalised_score, 4),
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "comments": self.comments,
            **self.extra,
        }
