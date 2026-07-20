"""Stage 10 — Goal Validator.

Compares the original task, the plan goal, and the predicted final world
state (inferred from the plan's last checkpoint exit_state) to determine
whether the plan achieves the requested goal.

Goal validation is deterministic: it uses keyword overlap between:
  * The user's original task (plan.metadata.task)
  * The plan's declared goal (plan.goal)
  * The final checkpoint exit_state

Score: 1.0 if goal appears satisfied, 0.0 otherwise.
"""
from __future__ import annotations

import logging
import re
from typing import List, Set

from evaluation.models.plan import GeneratedPlan
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)

_STOP_WORDS: Set[str] = {
    "a", "an", "the", "to", "for", "of", "in", "at", "is", "are",
    "and", "or", "with", "be", "will", "has", "have", "me", "my",
    "i", "you", "robot", "please", "bring", "give", "take",
}


def _keywords(text: str) -> Set[str]:
    """Extract non-stop-word tokens from a text string."""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 2}


def validate_goal(plan: GeneratedPlan) -> ValidationResult:
    """Validate whether the plan achieves the user's stated goal.

    Args:
        plan: Parsed generated plan.

    Returns:
        :class:`ValidationResult` with a binary goal satisfaction score.
    """
    issues: List[ValidationIssue] = []

    task_text = plan.metadata.task
    plan_goal = plan.goal

    # Get predicted final world state from last checkpoint exit_state
    final_exit_state = ""
    if plan.checkpoints:
        final_exit_state = plan.checkpoints[-1].exit_state

    task_kw = _keywords(task_text)
    goal_kw = _keywords(plan_goal)
    exit_kw = _keywords(final_exit_state)

    # Overlap: how many task keywords appear in the plan goal?
    goal_overlap = task_kw & goal_kw
    goal_coverage = len(goal_overlap) / len(task_kw) if task_kw else 1.0

    # Overlap: how many task keywords appear in the final world state?
    exit_overlap = task_kw & exit_kw
    exit_coverage = len(exit_overlap) / len(task_kw) if task_kw else 1.0

    # Check LLM's self-reported plan_valid flag
    llm_valid = plan.execution_summary.get("plan_valid", None)

    # Heuristic goal satisfaction score
    goal_satisfied = goal_coverage >= 0.4 and exit_coverage >= 0.3

    if not goal_satisfied:
        issues.append(ValidationIssue(
            code=ErrorCode.GOAL_NOT_REACHED,
            message=(
                f"Goal may not be fully satisfied. "
                f"Task-to-goal keyword coverage: {goal_coverage:.0%}, "
                f"task-to-exit-state coverage: {exit_coverage:.0%}."
            ),
            severity=Severity.WARNING,
            suggestion=(
                "Review the plan goal and final checkpoint exit_state to ensure "
                "they reflect the user's task requirements."
            ),
            extra={
                "task_keywords": sorted(task_kw),
                "goal_keywords": sorted(goal_kw),
                "matched_goal_keywords": sorted(goal_overlap),
                "matched_exit_keywords": sorted(exit_overlap),
            },
        ))

    if llm_valid is False:
        issues.append(ValidationIssue(
            code=ErrorCode.GOAL_NOT_REACHED,
            message=(
                "The LLM's own execution_summary.plan_valid is False, "
                "indicating self-reported plan failure."
            ),
            severity=Severity.ERROR,
            suggestion="Re-plan with corrected capabilities or a different robot.",
        ))
        goal_satisfied = False

    score = 1.0 if goal_satisfied else 0.0
    status = "PASS" if score == 1.0 else ("WARNING" if goal_coverage >= 0.3 else "FAIL")

    logger.info(
        "GoalValidator: satisfied=%s goal_coverage=%.2f exit_coverage=%.2f",
        goal_satisfied, goal_coverage, exit_coverage,
    )

    return ValidationResult(
        validator_name="GoalValidator",
        raw_score=score,
        normalised_score=score,
        status=status,
        issues=issues,
        comments=(
            f"Goal {'satisfied' if goal_satisfied else 'NOT satisfied'}. "
            f"Task-to-goal keyword match: {goal_coverage:.0%}. "
            f"Task-to-final-state match: {exit_coverage:.0%}."
        ),
        extra={
            "goal_satisfied": goal_satisfied,
            "goal_coverage": round(goal_coverage, 4),
            "exit_coverage": round(exit_coverage, 4),
            "llm_self_reported_valid": llm_valid,
        },
    )
