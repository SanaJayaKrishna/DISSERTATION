"""Validation helpers for URDF, rules, and generated capabilities."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from .models.rule_models import RULE_GROUPS


class CapabilityExtractorError(Exception):
    """Base exception for extractor failures."""


class URDFValidationError(CapabilityExtractorError):
    """Raised when a URDF cannot be parsed."""


class RuleValidationError(CapabilityExtractorError):
    """Raised when rules are malformed."""


class CapabilityValidationError(CapabilityExtractorError):
    """Raised when generated capabilities violate the output contract."""


def validate_urdf_path(path: Path) -> None:
    if not path.exists():
        raise URDFValidationError(f"URDF file does not exist: {path}")
    if not path.is_file():
        raise URDFValidationError(f"URDF path is not a file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise URDFValidationError(f"URDF must be UTF-8 text: {path}") from exc
    if "<robot" not in text:
        raise URDFValidationError(f"URDF does not contain a <robot> root element: {path}")


def validate_json_path(path: Path) -> None:
    if not path.exists():
        raise RuleValidationError(f"Rules file does not exist: {path}")
    if not path.is_file():
        raise RuleValidationError(f"Rules path is not a file: {path}")
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuleValidationError(f"Malformed rules JSON in {path}: {exc}") from exc


def validate_rules_document(document: Dict[str, Any]) -> List[str]:
    """Validate the rules document and return non-fatal warnings."""

    warnings: List[str] = []
    required_top_level = {
        "version",
        "metadata",
        "vocabularies",
        "conflict_resolution",
        "defaults",
        *RULE_GROUPS,
    }
    missing = sorted(required_top_level - set(document))
    if missing:
        raise RuleValidationError(f"Rules file missing top-level sections: {missing}")

    if not isinstance(document.get("vocabularies"), dict):
        raise RuleValidationError("Rules section 'vocabularies' must be an object")
    if not isinstance(document.get("defaults"), dict):
        raise RuleValidationError("Rules section 'defaults' must be an object")

    seen: Dict[str, str] = {}
    duplicates: List[str] = []
    for group in RULE_GROUPS:
        rules = document.get(group)
        if not isinstance(rules, list):
            raise RuleValidationError(f"Rules section '{group}' must be a list")
        for index, rule in enumerate(rules):
            _validate_rule(group, index, rule)
            rule_id = str(rule["id"])
            if rule_id in seen:
                duplicates.append(f"{rule_id} ({seen[rule_id]} and {group})")
            seen[rule_id] = group
    if duplicates:
        raise RuleValidationError(f"Duplicate rule IDs found: {duplicates}")

    cycles = _detect_inference_cycles(document.get("inference_rules", []))
    if cycles:
        raise RuleValidationError(f"Circular inference rules detected: {cycles}")

    conflicts = _detect_same_priority_boolean_conflicts(document)
    warnings.extend(conflicts)
    return warnings


def validate_capability_document(document: Dict[str, Any]) -> None:
    robot = document.get("Robot")
    if not isinstance(robot, dict):
        raise CapabilityValidationError("Capability document must contain a Robot object")
    required_sections = {
        "Metadata",
        "Morphology",
        "Locomotion",
        "Manipulation",
        "Perception",
        "Capabilities",
        "Constraints",
    }
    missing = sorted(required_sections - set(robot))
    if missing:
        raise CapabilityValidationError(f"Capability document missing sections: {missing}")


def _validate_rule(group: str, index: int, rule: Any) -> None:
    if not isinstance(rule, dict):
        raise RuleValidationError(f"{group}[{index}] must be an object")
    for field in ("id", "conditions", "outputs"):
        if field not in rule:
            raise RuleValidationError(f"{group}[{index}] missing required field '{field}'")
    if not isinstance(rule["conditions"], dict):
        raise RuleValidationError(f"{group}[{index}].conditions must be an object")
    if not isinstance(rule["outputs"], dict):
        raise RuleValidationError(f"{group}[{index}].outputs must be an object")
    try:
        int(rule.get("priority", 0))
        float(rule.get("confidence", 1.0))
    except (TypeError, ValueError) as exc:
        raise RuleValidationError(f"{group}[{index}] has invalid priority/confidence") from exc


def _detect_inference_cycles(rules: Iterable[Dict[str, Any]]) -> List[List[str]]:
    graph: Dict[str, Set[str]] = defaultdict(set)
    for rule in rules:
        condition_caps = set(_extract_condition_capabilities(rule.get("conditions", {})))
        output_caps = {
            key for key, value in rule.get("outputs", {}).items() if isinstance(value, bool)
        }
        for source in condition_caps:
            graph[source].update(output_caps)

    cycles: List[List[str]] = []
    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node: str) -> None:
        if node in visiting:
            start = stack.index(node) if node in stack else 0
            cycles.append(stack[start:] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for child in graph.get(node, set()):
            dfs(child)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        dfs(node)
    return cycles


def _extract_condition_capabilities(conditions: Any) -> List[str]:
    found: List[str] = []
    if isinstance(conditions, dict):
        for key, value in conditions.items():
            if key in {"capability_true", "capability_false"}:
                if isinstance(value, str):
                    found.append(value)
                elif isinstance(value, list):
                    found.extend(str(item) for item in value)
            elif key == "all" and isinstance(value, list):
                for item in value:
                    found.extend(_extract_condition_capabilities(item))
            elif isinstance(value, dict):
                found.extend(_extract_condition_capabilities(value))
    return found


def _detect_same_priority_boolean_conflicts(document: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    by_field: Dict[tuple[str, int, str], Set[bool]] = defaultdict(set)
    for group in RULE_GROUPS:
        for rule in document.get(group, []):
            priority = int(rule.get("priority", 0))
            for key, value in rule.get("outputs", {}).items():
                if isinstance(value, bool):
                    by_field[(key, priority, group)].add(value)
    for (key, priority, group), values in sorted(by_field.items()):
        if values == {False, True}:
            warnings.append(
                f"Potential conflicting boolean outputs for '{key}' in {group} at priority {priority}"
            )
    return warnings
