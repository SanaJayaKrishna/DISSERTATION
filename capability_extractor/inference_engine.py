"""Composite capability inference stage."""

from __future__ import annotations

import logging

from .models.capability_model import CapabilityState
from .models.robot_structure import RobotStructure
from .models.rule_models import RuleSet
from .semantic_engine import CapabilityRuleEvaluator


class InferenceEngine:
    """Evaluate higher-level inference rules from rules.json."""

    def __init__(
        self,
        evaluator: CapabilityRuleEvaluator,
        max_passes: int = 4,
        logger: logging.Logger | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.max_passes = max_passes
        self.logger = logger or logging.getLogger(__name__)

    def run(self, robot: RobotStructure, rules: RuleSet, state: CapabilityState) -> CapabilityState:
        for pass_index in range(1, self.max_passes + 1):
            changed = False
            for rule in rules.iter_rules(["inference_rules"]):
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
            self.logger.debug("Inference pass %s changed=%s", pass_index, changed)
            if not changed:
                break
        return state
