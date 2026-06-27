"""Rule document models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


RULE_GROUPS = [
    "morphology_rules",
    "locomotion_rules",
    "manipulation_rules",
    "perception_rules",
    "navigation_rules",
    "interaction_rules",
    "inspection_rules",
    "communication_rules",
    "environment_rules",
    "autonomy_rules",
    "power_rules",
    "quantitative_rules",
    "constraint_rules",
    "inference_rules",
]

SEMANTIC_RULE_GROUPS = [
    "morphology_rules",
    "locomotion_rules",
    "manipulation_rules",
    "perception_rules",
    "navigation_rules",
    "interaction_rules",
    "inspection_rules",
    "communication_rules",
    "environment_rules",
    "autonomy_rules",
    "power_rules",
]


@dataclass(frozen=True)
class Rule:
    """A single configurable rule loaded from JSON."""

    id: str
    description: str
    priority: int
    conditions: Dict[str, Any]
    outputs: Dict[str, Any]
    confidence: float
    group: str
    severity: str = "info"

    @classmethod
    def from_dict(cls, group: str, data: Dict[str, Any]) -> "Rule":
        return cls(
            id=str(data["id"]),
            description=str(data.get("description", "")),
            priority=int(data.get("priority", 0)),
            conditions=dict(data.get("conditions", {})),
            outputs=dict(data.get("outputs", {})),
            confidence=float(data.get("confidence", 1.0)),
            group=group,
            severity=str(data.get("severity", "info")),
        )


@dataclass(frozen=True)
class RuleSet:
    """Complete rule document."""

    version: str
    metadata: Dict[str, Any]
    vocabularies: Dict[str, Dict[str, List[str]]]
    rules_by_group: Dict[str, List[Rule]]
    conflict_resolution: Dict[str, Any] = field(default_factory=dict)
    defaults: Dict[str, Any] = field(default_factory=dict)

    def iter_rules(self, groups: Iterable[str] | None = None) -> Iterable[Rule]:
        selected_groups = groups if groups is not None else self.rules_by_group
        for group in selected_groups:
            yield from self.rules_by_group.get(group, [])
