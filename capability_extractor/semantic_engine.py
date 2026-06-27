"""Stage 2 configurable semantic rule engine."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .models.capability_model import CapabilityResult, CapabilityState
from .models.robot_structure import RobotStructure
from .models.rule_models import SEMANTIC_RULE_GROUPS, Rule, RuleSet
from .utils import normalize_text, path_get


@dataclass
class ConditionOutcome:
    """Outcome of a condition evaluation."""

    matched: bool
    evidence: Dict[str, Any] = field(default_factory=dict)
    rejected: List[str] = field(default_factory=list)

    def merge(self, other: "ConditionOutcome") -> None:
        self.matched = self.matched and other.matched
        self.evidence.update(other.evidence)
        self.rejected.extend(other.rejected)


class RuleEvaluationContext:
    """Cached structural and capability indexes used by rule operators."""

    def __init__(
        self,
        robot: RobotStructure,
        rules: RuleSet,
        state: CapabilityState,
    ) -> None:
        self.robot = robot
        self.rules = rules
        self.state = state
        self._domain_items = self._build_domain_items()
        self._keyword_cache: Dict[Tuple[str, str, str], Tuple[int, List[str]]] = {}

    def count_keyword(self, vocabulary: str, category: str, domain: str) -> Tuple[int, List[str]]:
        cache_key = (vocabulary, category, domain)
        if cache_key in self._keyword_cache:
            return self._keyword_cache[cache_key]

        vocab = self.rules.vocabularies.get(vocabulary, {})
        synonyms = vocab.get(category, [category])
        normalized_synonyms = [normalize_text(synonym) for synonym in synonyms]
        matches: List[str] = []
        for item in self._domain_items.get(domain, []):
            normalized_item = normalize_text(item)
            if any(self._matches_text(normalized_item, synonym) for synonym in normalized_synonyms):
                matches.append(item)
        unique = sorted(set(matches))
        self._keyword_cache[cache_key] = (len(unique), unique)
        return len(unique), unique

    def count_category_anywhere(self, category: str) -> Tuple[int, List[str]]:
        matches: List[str] = []
        for vocabulary, domain in (
            ("link_keywords", "link"),
            ("joint_keywords", "joint"),
            ("sensor_keywords", "sensor"),
            ("actuator_keywords", "actuator"),
            ("controller_keywords", "controller"),
            ("transmission_keywords", "transmission"),
            ("end_effector_keywords", "end_effector"),
        ):
            _, found = self.count_keyword(vocabulary, category, domain)
            matches.extend(found)
        unique = sorted(set(matches))
        return len(unique), unique

    def resolve_path(self, path: str) -> Any:
        if path in self.state.data:
            return self.state.data[path]
        if path in self.robot.derived_statistics:
            return self.robot.derived_statistics[path]
        if path == "links":
            return self.robot.links
        if path == "joints":
            return self.robot.joints
        if path == "sensors":
            return self.robot.sensors
        if path == "controllers":
            return self.robot.controllers
        if path == "transmissions":
            return self.robot.transmissions
        if path == "end_effectors":
            return self.robot.end_effectors
        if path == "geometry":
            return self.robot.geometry
        if path == "metadata":
            return self.robot.metadata
        if path.startswith("metadata."):
            return path_get(self.robot.metadata, path[len("metadata.") :])
        if path.startswith("derived_statistics."):
            return path_get(
                self.robot.derived_statistics,
                path[len("derived_statistics.") :],
            )
        return None

    def all_text(self) -> List[str]:
        return self._domain_items["all"]

    def _build_domain_items(self) -> Dict[str, List[str]]:
        link_items = self.robot.link_names
        joint_items = [
            f"{joint.name} {joint.joint_type}"
            for joint in self.robot.joints.values()
        ]
        sensor_items = [
            f"{sensor.name} {sensor.sensor_type} {sensor.source}"
            for sensor in self.robot.sensors
        ]
        sensor_items.extend(self.robot.link_names)
        sensor_items.extend(f"{plugin.name} {plugin.filename or ''}" for plugin in self.robot.plugins)
        actuator_items = [
            f"{actuator.name} {actuator.actuator_type} {actuator.joint or ''}"
            for actuator in self.robot.actuators
        ]
        controller_items = [
            f"{controller.name} {controller.controller_type}"
            for controller in self.robot.controllers
        ]
        transmission_items = [
            f"{transmission.name} {transmission.transmission_type} {' '.join(transmission.joints)} {' '.join(transmission.actuators)}"
            for transmission in self.robot.transmissions
        ]
        end_effector_items = list(self.robot.end_effectors) + self.robot.link_names
        all_items = (
            link_items
            + joint_items
            + sensor_items
            + actuator_items
            + controller_items
            + transmission_items
            + end_effector_items
            + self.robot.all_structural_text()
        )
        return {
            "link": sorted(set(link_items)),
            "joint": sorted(set(joint_items)),
            "sensor": sorted(set(sensor_items)),
            "actuator": sorted(set(actuator_items)),
            "controller": sorted(set(controller_items)),
            "transmission": sorted(set(transmission_items)),
            "end_effector": sorted(set(end_effector_items)),
            "all": sorted(set(all_items)),
        }

    @staticmethod
    def _matches_text(item: str, synonym: str) -> bool:
        if not item or not synonym:
            return False
        return synonym == item or synonym in item or item in synonym


class CapabilityRuleEvaluator:
    """Evaluate one rule against a robot and current capability state."""

    KEYWORD_OPERATORS = {
        "any_link_keyword": ("link_keywords", "link", "any"),
        "all_link_keywords": ("link_keywords", "link", "all"),
        "min_link_keyword_count": ("link_keywords", "link", "minimum"),
        "any_joint_keyword": ("joint_keywords", "joint", "any"),
        "min_joint_keyword_count": ("joint_keywords", "joint", "minimum"),
        "any_sensor_keyword": ("sensor_keywords", "sensor", "any"),
        "min_sensor_keyword_count": ("sensor_keywords", "sensor", "minimum"),
        "any_actuator_keyword": ("actuator_keywords", "actuator", "any"),
        "any_controller_keyword": ("controller_keywords", "controller", "any"),
        "any_transmission_keyword": ("transmission_keywords", "transmission", "any"),
        "any_end_effector_keyword": ("end_effector_keywords", "end_effector", "any"),
    }

    def __init__(self, logger: logging.Logger | None = None, debug_rules: bool = False) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.debug_rules = debug_rules

    def evaluate(
        self,
        rule: Rule,
        robot: RobotStructure,
        rules: RuleSet,
        state: CapabilityState,
    ) -> CapabilityResult:
        context = RuleEvaluationContext(robot, rules, state)
        outcome = self._evaluate_conditions(rule.conditions, context, path=rule.id)
        result = CapabilityResult(
            rule_id=rule.id,
            group=rule.group,
            matched=outcome.matched,
            priority=rule.priority,
            confidence=rule.confidence,
            outputs=rule.outputs if outcome.matched else {},
            evidence=outcome.evidence,
            rejected_conditions=outcome.rejected,
        )
        if self.debug_rules:
            self.logger.debug(
                "Rule %s matched=%s outputs=%s rejected=%s",
                rule.id,
                result.matched,
                result.outputs,
                result.rejected_conditions,
            )
        return result

    def _evaluate_conditions(
        self, conditions: Dict[str, Any], context: RuleEvaluationContext, path: str
    ) -> ConditionOutcome:
        outcome = ConditionOutcome(matched=True)
        for operator, expected in conditions.items():
            current = self._evaluate_operator(operator, expected, context, f"{path}.{operator}")
            outcome.merge(current)
        return outcome

    def _evaluate_operator(
        self,
        operator: str,
        expected: Any,
        context: RuleEvaluationContext,
        path: str,
    ) -> ConditionOutcome:
        if operator == "all":
            return self._all(expected, context, path)
        if operator == "any":
            return self._any(expected, context, path)
        if operator in self.KEYWORD_OPERATORS:
            vocabulary, domain, mode = self.KEYWORD_OPERATORS[operator]
            return self._keyword_condition(vocabulary, domain, mode, expected, context, path)
        if operator in {"min_count", "minimum_count"}:
            return self._count_condition(expected, context, path, minimum=True)
        if operator in {"max_count", "maximum_count"}:
            return self._count_condition(expected, context, path, minimum=False)
        if operator == "capability_true":
            return self._capability_bool(expected, context, path, desired=True)
        if operator == "capability_false":
            return self._capability_bool(expected, context, path, desired=False)
        if operator == "equals":
            return self._comparison(expected, context, path, lambda actual, value: actual == value, "equals")
        if operator in {"greater_than", "numeric_gt"}:
            return self._numeric_comparison(expected, context, path, lambda a, b: a > b, ">")
        if operator in {"less_than", "numeric_lt"}:
            return self._numeric_comparison(expected, context, path, lambda a, b: a < b, "<")
        if operator in {"numeric_gte", "greater_than_or_equal"}:
            return self._numeric_comparison(expected, context, path, lambda a, b: a >= b, ">=")
        if operator in {"numeric_lte", "less_than_or_equal"}:
            return self._numeric_comparison(expected, context, path, lambda a, b: a <= b, "<=")
        if operator == "exists":
            return self._exists(expected, context, path, desired=True)
        if operator == "missing":
            return self._exists(expected, context, path, desired=False)
        if operator == "contains":
            return self._contains(expected, context, path, desired=True)
        if operator == "not_contains":
            return self._contains(expected, context, path, desired=False)
        if operator == "regex":
            return self._regex(expected, context, path)
        if operator == "joint_type":
            return self._type_condition(expected, [joint.joint_type for joint in context.robot.joints.values()], path)
        if operator == "sensor_type":
            return self._type_condition(expected, [sensor.sensor_type for sensor in context.robot.sensors], path)
        if operator == "controller_type":
            return self._type_condition(expected, [controller.controller_type for controller in context.robot.controllers], path)
        if operator == "transmission_type":
            return self._type_condition(expected, [transmission.transmission_type for transmission in context.robot.transmissions], path)
        if operator == "end_effector_type":
            return self._keyword_condition("end_effector_keywords", "end_effector", "any", expected, context, path)
        if operator == "morphology_in":
            values = self._as_list(expected)
            actual = self._state_values(context, ["morphology", "robot_types"])
            return self._membership(values, actual, path)
        if operator == "locomotion_in":
            values = self._as_list(expected)
            actual = self._state_values(context, ["movement_type", "supported_locomotion", "drive_type"])
            return self._membership(values, actual, path)
        return self._direct_field_condition(operator, expected, context, path)

    def _all(self, expected: Any, context: RuleEvaluationContext, path: str) -> ConditionOutcome:
        if not isinstance(expected, list):
            return ConditionOutcome(False, rejected=[f"{path}: expected list"])
        outcome = ConditionOutcome(matched=True)
        for index, condition in enumerate(expected):
            if not isinstance(condition, dict):
                outcome.merge(ConditionOutcome(False, rejected=[f"{path}[{index}]: expected object"]))
                continue
            outcome.merge(self._evaluate_conditions(condition, context, f"{path}[{index}]"))
        return outcome

    def _any(self, expected: Any, context: RuleEvaluationContext, path: str) -> ConditionOutcome:
        if not isinstance(expected, list):
            return ConditionOutcome(False, rejected=[f"{path}: expected list"])
        evidence: Dict[str, Any] = {}
        rejected: List[str] = []
        for index, condition in enumerate(expected):
            if not isinstance(condition, dict):
                rejected.append(f"{path}[{index}]: expected object")
                continue
            result = self._evaluate_conditions(condition, context, f"{path}[{index}]")
            if result.matched:
                evidence.update(result.evidence)
                return ConditionOutcome(True, evidence=evidence)
            rejected.extend(result.rejected)
        return ConditionOutcome(False, evidence=evidence, rejected=rejected)

    def _keyword_condition(
        self,
        vocabulary: str,
        domain: str,
        mode: str,
        expected: Any,
        context: RuleEvaluationContext,
        path: str,
    ) -> ConditionOutcome:
        evidence: Dict[str, Any] = {}
        rejected: List[str] = []

        if mode == "minimum":
            if not isinstance(expected, dict):
                return ConditionOutcome(False, rejected=[f"{path}: expected count object"])
            matched = True
            for category, minimum in expected.items():
                count, matches = context.count_keyword(vocabulary, str(category), domain)
                evidence[f"{vocabulary}.{category}"] = {"count": count, "matches": matches}
                if count < int(minimum):
                    matched = False
                    rejected.append(f"{path}: {category} count {count} < {minimum}")
            return ConditionOutcome(matched, evidence, rejected)

        categories = self._as_list(expected)
        results = []
        for category in categories:
            count, matches = context.count_keyword(vocabulary, str(category), domain)
            results.append(count > 0)
            evidence[f"{vocabulary}.{category}"] = {"count": count, "matches": matches}
            if count == 0:
                rejected.append(f"{path}: no {category} matches in {domain}")
        matched = any(results) if mode == "any" else all(results)
        return ConditionOutcome(matched, evidence, [] if matched else rejected)

    def _count_condition(
        self,
        expected: Any,
        context: RuleEvaluationContext,
        path: str,
        minimum: bool,
    ) -> ConditionOutcome:
        if not isinstance(expected, dict):
            return ConditionOutcome(False, rejected=[f"{path}: expected count object"])
        matched = True
        evidence: Dict[str, Any] = {}
        rejected: List[str] = []
        for field, threshold in expected.items():
            actual = context.resolve_path(str(field))
            if actual is None:
                actual = context.resolve_path(f"{field}_count")
            if actual is None and str(field).endswith("s"):
                actual = context.resolve_path(f"{str(field)[:-1]}_count")
            matches: List[str] = []
            if isinstance(actual, (list, dict, tuple, set)):
                count = len(actual)
            elif isinstance(actual, (int, float)):
                count = int(actual)
            else:
                count, matches = context.count_category_anywhere(str(field))
            evidence[f"count.{field}"] = {"count": count, "matches": matches}
            threshold_int = int(threshold)
            ok = count >= threshold_int if minimum else count <= threshold_int
            if not ok:
                matched = False
                sign = ">=" if minimum else "<="
                rejected.append(f"{path}: {field} count {count} is not {sign} {threshold_int}")
        return ConditionOutcome(matched, evidence, rejected)

    def _capability_bool(
        self, expected: Any, context: RuleEvaluationContext, path: str, desired: bool
    ) -> ConditionOutcome:
        values = self._as_list(expected)
        rejected = []
        evidence: Dict[str, Any] = {}
        for key in values:
            actual = bool(context.state.get(str(key), False))
            evidence[f"capability.{key}"] = actual
            if actual is not desired:
                rejected.append(f"{path}: {key} is {actual}, expected {desired}")
        return ConditionOutcome(not rejected, evidence, rejected)

    def _comparison(
        self,
        expected: Any,
        context: RuleEvaluationContext,
        path: str,
        comparator: Any,
        label: str,
    ) -> ConditionOutcome:
        if not isinstance(expected, dict):
            return ConditionOutcome(False, rejected=[f"{path}: expected object"])
        rejected: List[str] = []
        evidence: Dict[str, Any] = {}
        for key, value in expected.items():
            actual = context.resolve_path(str(key))
            evidence[f"{label}.{key}"] = actual
            if not comparator(actual, value):
                rejected.append(f"{path}: {key}={actual!r} does not {label} {value!r}")
        return ConditionOutcome(not rejected, evidence, rejected)

    def _numeric_comparison(
        self,
        expected: Any,
        context: RuleEvaluationContext,
        path: str,
        comparator: Any,
        label: str,
    ) -> ConditionOutcome:
        if not isinstance(expected, dict):
            return ConditionOutcome(False, rejected=[f"{path}: expected object"])
        rejected: List[str] = []
        evidence: Dict[str, Any] = {}
        for key, value in expected.items():
            actual = context.resolve_path(str(key))
            try:
                actual_number = float(actual)
                expected_number = float(value)
            except (TypeError, ValueError):
                rejected.append(f"{path}: {key}={actual!r} is not numeric")
                continue
            evidence[f"numeric.{key}"] = actual_number
            if not comparator(actual_number, expected_number):
                rejected.append(f"{path}: {actual_number} is not {label} {expected_number}")
        return ConditionOutcome(not rejected, evidence, rejected)

    def _exists(
        self, expected: Any, context: RuleEvaluationContext, path: str, desired: bool
    ) -> ConditionOutcome:
        rejected: List[str] = []
        evidence: Dict[str, Any] = {}
        for key in self._as_list(expected):
            actual = context.resolve_path(str(key))
            exists = actual not in (None, "", [], {}, ())
            evidence[f"exists.{key}"] = exists
            if exists is not desired:
                rejected.append(f"{path}: {key} exists={exists}, expected {desired}")
        return ConditionOutcome(not rejected, evidence, rejected)

    def _contains(
        self, expected: Any, context: RuleEvaluationContext, path: str, desired: bool
    ) -> ConditionOutcome:
        checks: Dict[str, Any]
        if isinstance(expected, dict):
            checks = expected
        else:
            checks = {"all": expected}

        rejected: List[str] = []
        evidence: Dict[str, Any] = {}
        for key, value in checks.items():
            haystack = context.all_text() if key == "all" else context.resolve_path(str(key))
            values = self._as_list(value)
            matched_values = [item for item in values if self._value_contains(haystack, item)]
            contains = bool(matched_values)
            evidence[f"contains.{key}"] = matched_values
            if contains is not desired:
                rejected.append(f"{path}: contains({key}, {values})={contains}, expected {desired}")
        return ConditionOutcome(not rejected, evidence, rejected)

    def _regex(self, expected: Any, context: RuleEvaluationContext, path: str) -> ConditionOutcome:
        checks = expected if isinstance(expected, dict) else {"all": expected}
        rejected: List[str] = []
        evidence: Dict[str, Any] = {}
        for key, pattern in checks.items():
            haystack = context.all_text() if key == "all" else self._as_list(context.resolve_path(str(key)))
            compiled = re.compile(str(pattern), re.IGNORECASE)
            matches = [str(item) for item in self._as_list(haystack) if compiled.search(str(item))]
            evidence[f"regex.{key}"] = matches
            if not matches:
                rejected.append(f"{path}: no regex matches for {pattern!r}")
        return ConditionOutcome(not rejected, evidence, rejected)

    def _type_condition(self, expected: Any, actual_values: Sequence[str], path: str) -> ConditionOutcome:
        expected_values = {normalize_text(value) for value in self._as_list(expected)}
        actual = {normalize_text(value) for value in actual_values}
        matches = sorted(expected_values & actual)
        if matches:
            return ConditionOutcome(True, {path: matches})
        return ConditionOutcome(False, {path: sorted(actual)}, [f"{path}: no type match"])

    def _membership(self, expected: List[Any], actual: List[Any], path: str) -> ConditionOutcome:
        expected_norm = {normalize_text(value) for value in expected}
        actual_norm = {normalize_text(value) for value in actual}
        matches = sorted(expected_norm & actual_norm)
        if matches:
            return ConditionOutcome(True, {path: matches})
        return ConditionOutcome(False, {path: sorted(actual_norm)}, [f"{path}: no membership match"])

    def _direct_field_condition(
        self,
        operator: str,
        expected: Any,
        context: RuleEvaluationContext,
        path: str,
    ) -> ConditionOutcome:
        actual = context.resolve_path(operator)
        if actual is None and operator in context.state.data:
            actual = context.state.data[operator]
        if isinstance(expected, bool):
            matched = bool(actual) is expected
        elif isinstance(actual, list):
            expected_values = self._as_list(expected)
            matched = any(item in actual for item in expected_values)
        else:
            matched = actual == expected
        evidence = {f"direct.{operator}": actual}
        rejected = [] if matched else [f"{path}: {actual!r} != {expected!r}"]
        return ConditionOutcome(matched, evidence, rejected)

    def _state_values(self, context: RuleEvaluationContext, keys: Iterable[str]) -> List[Any]:
        values: List[Any] = []
        for key in keys:
            value = context.state.get(key)
            if isinstance(value, list):
                values.extend(value)
            elif value not in (None, "", "unknown"):
                values.append(value)
        return values

    def _value_contains(self, haystack: Any, needle: Any) -> bool:
        normalized_needle = normalize_text(needle)
        if isinstance(haystack, dict):
            return any(self._value_contains(value, needle) for value in haystack.values())
        if isinstance(haystack, (list, tuple, set)):
            return any(self._value_contains(item, needle) for item in haystack)
        return normalized_needle in normalize_text(haystack)

    def _as_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, set):
            return sorted(value)
        return [value]


class SemanticRuleEngine:
    """Evaluate semantic rules and merge matched outputs."""

    def __init__(
        self,
        evaluator: CapabilityRuleEvaluator,
        max_passes: int = 6,
        logger: logging.Logger | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.max_passes = max_passes
        self.logger = logger or logging.getLogger(__name__)

    def run(self, robot: RobotStructure, rules: RuleSet, state: CapabilityState) -> CapabilityState:
        for pass_index in range(1, self.max_passes + 1):
            changed = False
            for rule in rules.iter_rules(SEMANTIC_RULE_GROUPS):
                result = self.evaluator.evaluate(rule, robot, rules, state)
                state.record_trace(result)
                if result.matched:
                    changed = (
                        state.merge_outputs(
                            result.outputs,
                            rule_id=rule.id,
                            group=rule.group,
                            priority=rule.priority,
                            confidence=rule.confidence,
                        )
                        or changed
                    )
            self.logger.debug("Semantic pass %s changed=%s", pass_index, changed)
            if not changed:
                break
        return state
