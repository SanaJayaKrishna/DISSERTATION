"""Stage 6 — Capability Validator (Main Contribution).

For every action the validator:
  1. Resolves the action to a skill in the ontology.
  2. Retrieves the skill's required_capabilities list.
  3. Checks each required capability against the robot's capability model.
  4. Records a detailed per-step Capability Trace.

Score = compatible_actions / total_actions.

The Capability Trace is the dissertation's key novelty: it provides a
transparent, deterministic, step-by-step record of which robot capabilities
were checked at each plan step.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from evaluation.models.plan import GeneratedPlan
from evaluation.models.robot import RobotCapabilities
from evaluation.models.ontology import SkillOntology, Skill
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capability Trace
# ---------------------------------------------------------------------------

@dataclass
class CapabilityTraceEntry:
    """Per-step record of the capability verification process.

    Attributes:
        global_index: Monotonic action index in the plan.
        checkpoint_id: Parent checkpoint.
        step: 1-based step within the checkpoint.
        action_name: Action name from the plan.
        required_skill: Ontology skill name resolved for this action.
        required_capabilities: Capabilities the skill demands.
        robot_capabilities_checked: Actual True/False for each required cap.
        passed: Overall PASS/FAIL for this step.
        failure_reason: Human-readable reason if FAIL; empty string if PASS.
    """
    global_index: int
    checkpoint_id: int
    step: int
    action_name: str
    required_skill: str
    required_capabilities: List[str]
    robot_capabilities_checked: Dict[str, bool]
    passed: bool
    failure_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict for JSON reports."""
        return {
            "global_index": self.global_index,
            "checkpoint_id": self.checkpoint_id,
            "step": self.step,
            "action_name": self.action_name,
            "required_skill": self.required_skill,
            "required_capabilities": self.required_capabilities,
            "robot_capabilities_checked": self.robot_capabilities_checked,
            "result": "PASS" if self.passed else "FAIL",
            "failure_reason": self.failure_reason,
        }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_capabilities(
    plan: GeneratedPlan,
    robot: RobotCapabilities,
    ontology: SkillOntology,
) -> ValidationResult:
    """Validate robot capabilities against every plan action.

    Args:
        plan: Parsed generated plan.
        robot: Loaded robot capabilities.
        ontology: Loaded skill ontology.

    Returns:
        :class:`ValidationResult` with capability issues, capability trace,
        and a compatibility score.
    """
    issues: List[ValidationIssue] = []
    trace: List[CapabilityTraceEntry] = []
    total = len(plan.all_actions)
    compatible = 0

    for action in plan.all_actions:
        skill: Optional[Skill] = ontology.find_skill(action.action)

        if skill is None:
            # Skill not found — skip capability check (SkillValidator catches this)
            trace.append(
                CapabilityTraceEntry(
                    global_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    step=action.step,
                    action_name=action.action,
                    required_skill="UNKNOWN",
                    required_capabilities=[],
                    robot_capabilities_checked={},
                    passed=False,
                    failure_reason=(
                        f"Action '{action.action}' has no matching skill in the "
                        "ontology; capability check skipped."
                    ),
                )
            )
            continue

        required_caps = skill.required_capabilities
        cap_check: Dict[str, bool] = {}
        missing: List[str] = []

        for cap in required_caps:
            has = robot.has_capability(cap)
            cap_check[cap] = has
            if not has:
                missing.append(cap)

        passed = len(missing) == 0
        if passed:
            compatible += 1
            failure_reason = ""
        else:
            failure_reason = (
                f"Robot '{robot.metadata.name}' lacks required capabilities: "
                + ", ".join(missing)
            )
            issues.append(
                ValidationIssue(
                    code=ErrorCode.CAPABILITY_MISSING,
                    message=(
                        f"Action '{action.action}' (checkpoint {action.checkpoint_id}, "
                        f"step {action.step}) requires capabilities "
                        f"[{', '.join(missing)}] that the robot does not have."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion=(
                        f"Use a robot with [{', '.join(missing)}] capabilities, "
                        "or remove this action from the plan."
                    ),
                    extra={
                        "missing_capabilities": missing,
                        "required_skill": skill.abstract_skill,
                    },
                )
            )
            logger.warning(
                "Capability FAIL for '%s' (skill='%s'): missing %s",
                action.action, skill.abstract_skill, missing,
            )

        trace.append(
            CapabilityTraceEntry(
                global_index=action.global_index,
                checkpoint_id=action.checkpoint_id,
                step=action.step,
                action_name=action.action,
                required_skill=skill.abstract_skill,
                required_capabilities=required_caps,
                robot_capabilities_checked=cap_check,
                passed=passed,
                failure_reason=failure_reason,
            )
        )

    raw_score = compatible / total if total > 0 else 1.0
    status = "PASS" if not issues else ("WARNING" if raw_score >= 0.6 else "FAIL")

    logger.info(
        "CapabilityValidator: %d/%d actions compatible. Score=%.2f",
        compatible, total, raw_score,
    )

    return ValidationResult(
        validator_name="CapabilityValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{compatible}/{total} actions are capability-compatible with robot "
            f"'{robot.metadata.name}'. Score: {raw_score:.2%}."
        ),
        extra={
            "compatible_actions": compatible,
            "total_actions": total,
            "capability_trace": [t.to_dict() for t in trace],
        },
    )
