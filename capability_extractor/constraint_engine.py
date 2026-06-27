"""Stage 3 constraint generator."""

from __future__ import annotations

import logging

from .models.capability_model import CapabilityState
from .models.robot_structure import RobotStructure
from .models.rule_models import RuleSet
from .semantic_engine import CapabilityRuleEvaluator


class ConstraintEngine:
    """Evaluate constraints after semantic and inference stages."""

    def __init__(
        self,
        evaluator: CapabilityRuleEvaluator,
        logger: logging.Logger | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.logger = logger or logging.getLogger(__name__)

    def run(self, robot: RobotStructure, rules: RuleSet, state: CapabilityState) -> CapabilityState:
        matched_count = 0
        for rule in rules.iter_rules(["constraint_rules"]):
            result = self.evaluator.evaluate(rule, robot, rules, state)
            state.record_trace(result)
            if not result.matched:
                continue
            matched_count += 1
            state.merge_outputs(
                result.outputs,
                rule_id=rule.id,
                group=rule.group,
                priority=rule.priority,
                confidence=rule.confidence,
                constraint=True,
            )
            state.add_constraint(
                {
                    "id": rule.id,
                    "description": rule.description,
                    "severity": rule.severity,
                    "priority": rule.priority,
                    "confidence": rule.confidence,
                    "outputs": result.outputs,
                    "evidence": result.evidence,
                }
            )
        self.logger.info("Applied %s constraint rules", matched_count)
        return state
