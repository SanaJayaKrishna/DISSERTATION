"""Stage 4 — Location Validator.

Checks that every location referenced in the plan (action.location field)
exists in the world state.

Score = existing_locations / referenced_locations.
"""
from __future__ import annotations

import logging
from typing import List

from evaluation.models.plan import GeneratedPlan
from evaluation.models.world import WorldState
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


def validate_locations(plan: GeneratedPlan, world: WorldState) -> ValidationResult:
    """Validate that every location in the plan exists in the world.

    Args:
        plan: Parsed generated plan.
        world: Loaded world state.

    Returns:
        :class:`ValidationResult` with per-location issues and validity score.
    """
    issues: List[ValidationIssue] = []

    references = [
        a for a in plan.all_actions if a.location and a.location.strip()
    ]
    total = len(references)
    valid = 0

    for action in references:
        loc = action.location.strip()
        if world.location_exists(loc):
            valid += 1
            logger.debug(
                "Location '%s' (idx=%d) found in world.", loc, action.global_index
            )
        else:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.INVALID_LOCATION,
                    message=(
                        f"Location '{loc}' in action '{action.action}' "
                        f"(checkpoint {action.checkpoint_id}, step {action.step}) "
                        f"does not exist in world '{world.name}'."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion=(
                        f"Verify that '{loc}' is a valid room/location in the world "
                        "JSON. Check for spelling differences (e.g. 'Cafeteria' vs "
                        "'cafeteria')."
                    ),
                    extra={"referenced_location": loc},
                )
            )
            logger.warning(
                "Location '%s' not found in world '%s' (idx=%d).",
                loc, world.name, action.global_index,
            )

    raw_score = valid / total if total > 0 else 1.0
    status = "PASS" if not issues else ("WARNING" if raw_score >= 0.6 else "FAIL")

    return ValidationResult(
        validator_name="LocationValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{valid}/{total} location references are valid. "
            f"Score: {raw_score:.2%}."
        ),
        extra={"valid_locations": valid, "total_location_refs": total},
    )
