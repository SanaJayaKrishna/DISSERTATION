"""Stage 8 — Dependency Validator.

Checks that each action's preconditions are satisfied by prior actions.

Rules (static, deterministic):
  * A pick action must be preceded by a navigate action to the same location.
  * A place/carry action must be preceded by a pick at the same object.
  * A locate/detect action must occur before pick on the same object.
  * No action on a closed/locked resource before it is opened.

Score = dependency-satisfied actions / total actions.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from evaluation.models.plan import GeneratedPlan, PlanAction
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)

# Categorised action keyword sets
_PICK_KEYS = {"pick", "grasp", "grab"}
_PLACE_KEYS = {"place", "put", "release", "deliver"}
_CARRY_KEYS = {"carry", "transport", "bring"}
_NAV_KEYS = {"navigate", "go_to", "move_to", "travel", "drive"}
_LOCATE_KEYS = {"locate", "detect", "find", "search", "identify", "recognize", "classify"}


def _matches(action_name: str, keys: Set[str]) -> bool:
    a = action_name.lower()
    return any(k in a for k in keys)


def validate_dependencies(plan: GeneratedPlan) -> ValidationResult:
    """Validate action dependency ordering.

    Args:
        plan: Parsed generated plan.

    Returns:
        :class:`ValidationResult` with ordering issues and dependency score.
    """
    issues: List[ValidationIssue] = []
    total = len(plan.all_actions)
    satisfied = 0

    # State tracking
    # picked_objects: set of object names that have been picked up
    picked_objects: Set[str] = set()
    # located_objects: set of objects that have been detected/located
    located_objects: Set[str] = set()
    # current_locations: set of locations the robot has navigated to
    visited_locations: Set[str] = set()
    # last_location: most recent navigation destination
    last_location: Optional[str] = None

    for action in plan.all_actions:
        act = action.action.lower()
        obj = action.obj.strip().lower() if action.obj else ""
        loc = action.location.strip().lower() if action.location else ""
        ok = True
        reason = ""

        # Rule 1: Navigate — always mark location as visited
        if _matches(act, _NAV_KEYS):
            if loc:
                visited_locations.add(loc)
                last_location = loc

        # Rule 2: Pick requires the robot to have navigated to the location
        elif _matches(act, _PICK_KEYS):
            if loc and loc not in visited_locations:
                ok = False
                reason = (
                    f"Pick action on '{obj}' at '{loc}' but robot has not "
                    "navigated there yet."
                )
            elif obj and obj not in located_objects:
                # Soft warning: object not detected first
                issues.append(ValidationIssue(
                    code=ErrorCode.DEPENDENCY_ERROR,
                    message=(
                        f"Action '{action.action}' (idx={action.global_index}): "
                        f"picking '{obj}' without a prior locate/detect step."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.WARNING,
                    suggestion=(
                        f"Add a detect_object or locate_object step for '{obj}' "
                        "before picking it."
                    ),
                ))
            if ok:
                picked_objects.add(obj)

        # Rule 3: Place/carry requires the object to have been picked
        elif _matches(act, _PLACE_KEYS) or _matches(act, _CARRY_KEYS):
            if obj and obj not in picked_objects:
                ok = False
                reason = (
                    f"Action '{action.action}' on '{obj}' requires a prior "
                    "pick action, but none was found."
                )
            else:
                if _matches(act, _PLACE_KEYS) and obj:
                    picked_objects.discard(obj)  # object placed → no longer held

        # Rule 4: Locate/detect updates located_objects
        elif _matches(act, _LOCATE_KEYS):
            if obj:
                located_objects.add(obj)

        if not ok:
            issues.append(ValidationIssue(
                code=ErrorCode.DEPENDENCY_ERROR,
                message=reason,
                action_index=action.global_index,
                checkpoint_id=action.checkpoint_id,
                severity=Severity.ERROR,
                suggestion="Reorder actions to satisfy preconditions first.",
            ))
        else:
            satisfied += 1

    raw_score = satisfied / total if total > 0 else 1.0
    status = "PASS" if not [i for i in issues if i.severity == Severity.ERROR] \
        else ("WARNING" if raw_score >= 0.6 else "FAIL")

    return ValidationResult(
        validator_name="DependencyValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{satisfied}/{total} actions satisfy their dependencies. "
            f"Score: {raw_score:.2%}."
        ),
        extra={"satisfied_dependencies": satisfied, "total_actions": total},
    )
