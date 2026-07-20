"""Stage 9 — Sequence Validator.

Checks the logical ordering of actions within and across checkpoints.

Expected canonical order for a fetch-and-deliver plan:
  navigate → locate/detect → pick → carry → navigate → place

The validator uses a lightweight state machine to score ordering quality.
It detects:
  * Pick before navigate
  * Place before pick
  * Repeated identical consecutive actions (indicative of loops)
  * Actions that violate expected phase ordering

Score = correctly ordered transitions / total action transitions.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from evaluation.models.plan import GeneratedPlan, PlanAction
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)

# Phase ordering constants (lower = earlier)
_PHASE = {
    "navigate":   1,
    "locate":     2,
    "detect":     2,
    "recognize":  2,
    "classify":   2,
    "find":       2,
    "identify":   2,
    "pick":       3,
    "grasp":      3,
    "grab":       3,
    "carry":      4,
    "transport":  4,
    "place":      5,
    "put":        5,
    "deliver":    5,
    "release":    5,
    "inspect":    6,
    "report":     7,
}

_FORBIDDEN_BACK_TRANSITIONS = {
    # place → pick (without navigate in between)
    ("place", "pick"),
    ("put", "pick"),
    ("release", "pick"),
    # carry → navigate is allowed; carry → locate without navigate is odd
}


def _phase(action_name: str) -> int:
    a = action_name.lower()
    for k, v in _PHASE.items():
        if k in a:
            return v
    return 0  # unknown → no ordering constraint


def validate_sequence(plan: GeneratedPlan) -> ValidationResult:
    """Validate the logical ordering of the plan's action sequence.

    Args:
        plan: Parsed generated plan.

    Returns:
        :class:`ValidationResult` with ordering issues and a sequence score.
    """
    issues: List[ValidationIssue] = []
    actions = plan.all_actions
    n = len(actions)
    good_transitions = 0
    total_transitions = max(n - 1, 0)

    for i in range(1, n):
        prev = actions[i - 1]
        curr = actions[i]
        prev_phase = _phase(prev.action)
        curr_phase = _phase(curr.action)

        # Allow equal phase (e.g. multiple detects in a row) and forward
        if curr_phase == 0 or prev_phase == 0:
            good_transitions += 1  # unknown action → no penalty
            continue

        if curr_phase >= prev_phase:
            good_transitions += 1
        else:
            # Backward phase jump — might be valid (e.g. navigate after place)
            # Only flag if it's a known forbidden pattern
            prev_key = prev.action.lower()
            curr_key = curr.action.lower()
            forbidden = any(
                prev_key.startswith(fb[0]) and curr_key.startswith(fb[1])
                for fb in _FORBIDDEN_BACK_TRANSITIONS
            )
            if forbidden:
                issues.append(ValidationIssue(
                    code=ErrorCode.ORDERING_ERROR,
                    message=(
                        f"Illegal backward transition: '{prev.action}' (idx="
                        f"{prev.global_index}) → '{curr.action}' (idx="
                        f"{curr.global_index}). Expected phase "
                        f"{prev_phase} → {curr_phase}."
                    ),
                    action_index=curr.global_index,
                    checkpoint_id=curr.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion=(
                        f"Move '{curr.action}' to before '{prev.action}', or insert "
                        "a navigate step between them."
                    ),
                ))
            else:
                # Soft warning for other backward jumps
                issues.append(ValidationIssue(
                    code=ErrorCode.ORDERING_ERROR,
                    message=(
                        f"Unexpected phase regression: '{prev.action}' → "
                        f"'{curr.action}' (phase {prev_phase} → {curr_phase})."
                    ),
                    action_index=curr.global_index,
                    checkpoint_id=curr.checkpoint_id,
                    severity=Severity.WARNING,
                    suggestion="Review whether this action order is intentional.",
                ))
                good_transitions += 1  # don't penalise unknown regressions fully

    # Repeated consecutive identical actions
    for i in range(1, n):
        if actions[i].action.lower() == actions[i - 1].action.lower():
            issues.append(ValidationIssue(
                code=ErrorCode.REDUNDANT_ACTION,
                message=(
                    f"Consecutive duplicate action '{actions[i].action}' at "
                    f"indices {actions[i-1].global_index} and "
                    f"{actions[i].global_index}."
                ),
                action_index=actions[i].global_index,
                checkpoint_id=actions[i].checkpoint_id,
                severity=Severity.WARNING,
                suggestion="Remove the duplicate action or merge the steps.",
            ))

    raw_score = good_transitions / total_transitions if total_transitions > 0 else 1.0
    error_issues = [i for i in issues if i.severity == Severity.ERROR]
    status = "PASS" if not error_issues else ("WARNING" if raw_score >= 0.6 else "FAIL")

    return ValidationResult(
        validator_name="SequenceValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{good_transitions}/{total_transitions} action transitions are "
            f"logically ordered. Score: {raw_score:.2%}."
        ),
        extra={
            "good_transitions": good_transitions,
            "total_transitions": total_transitions,
        },
    )
