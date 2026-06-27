"""Capability state and explainability models."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class RuleTrace:
    """Trace of a rule evaluation."""

    rule_id: str
    group: str
    matched: bool
    priority: int
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    rejected_conditions: List[str] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityResult:
    """Result returned by a rule evaluation."""

    rule_id: str
    group: str
    matched: bool
    priority: int
    confidence: float
    outputs: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    rejected_conditions: List[str] = field(default_factory=list)


@dataclass
class CapabilityState:
    """Mutable capability state built by the pipeline."""

    data: Dict[str, Any]
    traces: List[RuleTrace] = field(default_factory=list)
    evidence: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    field_scores: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    constraints: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_defaults(cls, defaults: Dict[str, Any]) -> "CapabilityState":
        return cls(data=deepcopy(defaults))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set_metric(self, key: str, value: Any, source: str = "quantitative_engine") -> None:
        self.data[key] = value
        self.evidence.setdefault(key, []).append({"source": source, "value": value})

    def record_trace(self, result: CapabilityResult) -> None:
        trace = RuleTrace(
            rule_id=result.rule_id,
            group=result.group,
            matched=result.matched,
            priority=result.priority,
            confidence=result.confidence,
            evidence=deepcopy(result.evidence),
            rejected_conditions=list(result.rejected_conditions),
            outputs=deepcopy(result.outputs) if result.matched else {},
        )
        if trace not in self.traces:
            self.traces.append(trace)

    def merge_outputs(
        self,
        outputs: Dict[str, Any],
        rule_id: str,
        group: str,
        priority: int,
        confidence: float,
        constraint: bool = False,
    ) -> bool:
        """Merge rule outputs and return True when state changed."""

        changed = False
        for key, value in outputs.items():
            before = deepcopy(self.data.get(key))
            self._merge_value(key, value, priority, confidence, constraint)
            after = self.data.get(key)
            if before != after:
                changed = True
            self._add_evidence(
                key,
                {
                    "rule_id": rule_id,
                    "group": group,
                    "priority": priority,
                    "confidence": confidence,
                    "value": deepcopy(value),
                },
            )

            if constraint and key.startswith("cannot_") and bool(value):
                positive_key = "can_" + key[len("cannot_") :]
                if self.data.get(positive_key) is True:
                    self.data[positive_key] = False
                    changed = True
                self._add_evidence(
                    positive_key,
                    {
                        "rule_id": rule_id,
                        "group": group,
                        "priority": priority,
                        "confidence": confidence,
                        "value": False,
                        "reason": key,
                    },
                )
        return changed

    def add_constraint(self, constraint: Dict[str, Any]) -> None:
        if constraint not in self.constraints:
            self.constraints.append(constraint)

    def _merge_value(
        self,
        key: str,
        value: Any,
        priority: int,
        confidence: float,
        constraint: bool,
    ) -> None:
        current = self.data.get(key)
        score = self.field_scores.get(key, {"priority": -1, "confidence": -1.0})
        incoming_score = {"priority": priority, "confidence": confidence}

        if isinstance(value, list):
            base = [] if current in (None, "unknown") else list(current)
            for item in value:
                if item == "unknown" and base:
                    continue
                if item not in base:
                    base.append(item)
            if key == "robot_types" and len(base) > 1 and "unknown" in base:
                base.remove("unknown")
            self.data[key] = base
            self.field_scores[key] = incoming_score
            return

        if isinstance(value, dict):
            base = current if isinstance(current, dict) else {}
            merged = deepcopy(base)
            merged.update(value)
            self.data[key] = merged
            self.field_scores[key] = incoming_score
            return

        if isinstance(value, bool):
            if constraint:
                self.data[key] = value
                self.field_scores[key] = incoming_score
                return
            if current is None or current is False or self._incoming_wins(score, incoming_score):
                self.data[key] = value
                self.field_scores[key] = incoming_score
            return

        if current in (None, "unknown", 0, 0.0, []) or self._incoming_wins(score, incoming_score):
            self.data[key] = value
            self.field_scores[key] = incoming_score

    def _add_evidence(self, key: str, entry: Dict[str, Any]) -> None:
        bucket = self.evidence.setdefault(key, [])
        if entry not in bucket:
            bucket.append(entry)

    @staticmethod
    def _incoming_wins(current: Dict[str, Any], incoming: Dict[str, Any]) -> bool:
        if incoming["priority"] > current.get("priority", -1):
            return True
        if incoming["priority"] == current.get("priority", -1):
            return incoming["confidence"] >= current.get("confidence", -1.0)
        return False
