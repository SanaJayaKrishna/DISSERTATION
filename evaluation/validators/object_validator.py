"""Stage 3 — Object Validator.

Checks that every object referenced by a plan action exists in the world state.
Matching uses the WorldState.object_exists() fuzzy matcher which handles
natural-language plan references such as
  "best book for learning Reinforcement Learning" → "book".

Score = existing_objects / referenced_objects.
"""
from __future__ import annotations

import logging
from typing import List

from evaluation.models.plan import GeneratedPlan
from evaluation.models.world import WorldState
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


def validate_objects(plan: GeneratedPlan, world: WorldState) -> ValidationResult:
    """Validate that every object in the plan exists in the world.

    Args:
        plan: Parsed generated plan.
        world: Loaded world state.

    Returns:
        :class:`ValidationResult` with per-object issues and validity score.
    """
    issues: List[ValidationIssue] = []

    # Collect unique non-empty object references
    references = [
        a for a in plan.all_actions if a.obj and a.obj.strip()
    ]
    total = len(references)
    valid = 0

    for action in references:
        obj = action.obj.strip()
        if world.object_exists(obj):
            valid += 1
            logger.debug(
                "Object '%s' (idx=%d) found in world.", obj, action.global_index
            )
        else:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.OBJECT_NOT_FOUND,
                    message=(
                        f"Object '{obj}' referenced in action '{action.action}' "
                        f"(checkpoint {action.checkpoint_id}, step {action.step}) "
                        f"does not exist in the world '{world.name}'."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.WARNING,
                    suggestion=(
                        f"Verify that '{obj}' exists in the world JSON or rephrase "
                        "the object reference to match a known world object."
                    ),
                    extra={"referenced_object": obj},
                )
            )
            logger.warning(
                "Object '%s' not found in world '%s' (idx=%d).",
                obj, world.name, action.global_index,
            )

    raw_score = valid / total if total > 0 else 1.0
    status = "PASS" if not issues else ("WARNING" if raw_score >= 0.6 else "FAIL")

    return ValidationResult(
        validator_name="ObjectValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{valid}/{total} object references are valid. "
            f"Score: {raw_score:.2%}."
        ),
        extra={"valid_objects": valid, "total_object_refs": total},
    )
