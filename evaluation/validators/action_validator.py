"""Stage 2 — Action Validator.

Checks that every action name in the plan exists in the skill ontology.
Actions are matched using the ontology's resolution order:
  1. Exact ``abstract_skill`` name match.
  2. Alias match.
  3. Substring / prefix fallback.

Score = valid_actions / total_actions.
"""
from __future__ import annotations

import logging
from typing import List

from evaluation.models.plan import GeneratedPlan
from evaluation.models.ontology import SkillOntology
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


def validate_actions(plan: GeneratedPlan, ontology: SkillOntology) -> ValidationResult:
    """Validate that every plan action resolves to a known skill.

    Args:
        plan: Parsed generated plan.
        ontology: Loaded skill ontology.

    Returns:
        :class:`ValidationResult` with per-action issues and a validity score.
    """
    issues: List[ValidationIssue] = []
    total = len(plan.all_actions)
    valid = 0

    for action in plan.all_actions:
        skill = ontology.find_skill(action.action)
        if skill is not None:
            valid += 1
            logger.debug(
                "Action '%s' (idx=%d) resolved to skill '%s'.",
                action.action, action.global_index, skill.abstract_skill,
            )
        else:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.ACTION_NOT_FOUND,
                    message=(
                        f"Action '{action.action}' (checkpoint {action.checkpoint_id}, "
                        f"step {action.step}) is not in the skill ontology."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion=(
                        f"Check the skill ontology for a valid alternative to "
                        f"'{action.action}' or add a new ontology entry."
                    ),
                )
            )
            logger.warning(
                "Action '%s' not found in ontology (idx=%d).",
                action.action, action.global_index,
            )

    raw_score = valid / total if total > 0 else 1.0
    status = "PASS" if not issues else ("WARNING" if raw_score >= 0.6 else "FAIL")

    return ValidationResult(
        validator_name="ActionValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{valid}/{total} actions are valid. "
            f"Score: {raw_score:.2%}."
        ),
        extra={"valid_actions": valid, "total_actions": total},
    )
