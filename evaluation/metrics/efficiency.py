"""Efficiency metrics — Stage 11.

Computes the plan efficiency score without simulation by comparing the
number of generated steps to an idealised minimum.

Metrics produced:
  * total_actions: raw count.
  * repeated_actions: count of repeated action names.
  * redundant_navigations: count of back-and-forth navigation sequences.
  * efficiency_score: ideal_steps / actual_steps (clipped 0-1).
  * redundancy_score: 1 - (redundant / total).
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import List, Tuple

from evaluation.models.plan import GeneratedPlan
from evaluation.config import EvaluationConfig, ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


def _detect_redundant_navigation(actions: list) -> List[Tuple[int, int, str]]:
    """Detect back-and-forth navigation patterns.

    Returns a list of (index_a, index_b, location) tuples where the robot
    navigates to the same location more than once non-consecutively.

    Args:
        actions: Flat ordered list of PlanAction objects.

    Returns:
        List of (first_idx, second_idx, location) tuples.
    """
    nav_keywords = {"navigate", "go_to", "move_to", "travel"}

    def is_nav(act: str) -> bool:
        a = act.lower()
        return any(k in a for k in nav_keywords)

    # Track navigation visits
    nav_visits: dict = {}  # location -> list of global_index
    for action in actions:
        if is_nav(action.action) and action.location:
            loc = action.location.strip().lower()
            nav_visits.setdefault(loc, []).append(action.global_index)

    redundant = []
    for loc, indices in nav_visits.items():
        if len(indices) > 1:
            for i in range(1, len(indices)):
                redundant.append((indices[i - 1], indices[i], loc))
    return redundant


def compute_efficiency(
    plan: GeneratedPlan,
    config: EvaluationConfig,
) -> ValidationResult:
    """Compute plan efficiency and redundancy metrics.

    Args:
        plan: Parsed generated plan.
        config: Evaluation configuration (provides ideal_steps_per_action).

    Returns:
        :class:`ValidationResult` with efficiency scores and redundancy counts.
    """
    issues: List[ValidationIssue] = []
    actions = plan.all_actions
    total = len(actions)

    if total == 0:
        return ValidationResult(
            validator_name="EfficiencyAnalyser",
            raw_score=1.0,
            normalised_score=1.0,
            status="PASS",
            comments="No actions to evaluate efficiency.",
        )

    # --- Repeated action names ---
    action_counts = Counter(a.action.lower() for a in actions)
    repeated = sum(c - 1 for c in action_counts.values() if c > 1)

    # --- Redundant navigation ---
    redundant_navs = _detect_redundant_navigation(actions)
    for idx_a, idx_b, loc in redundant_navs:
        issues.append(ValidationIssue(
            code=ErrorCode.REDUNDANT_NAVIGATION,
            message=(
                f"Redundant navigation to '{loc}': visited at action index "
                f"{idx_a} and again at {idx_b}."
            ),
            action_index=idx_b,
            severity=Severity.WARNING,
            suggestion=(
                f"Consolidate the two visits to '{loc}' into a single trip, "
                "or reorder actions to avoid backtracking."
            ),
        ))

    # --- Efficiency score ---
    # Ideal: one step per unique action type per unique location
    unique_combos = len({
        (a.action.lower(), a.location.strip().lower()) for a in actions
    })
    ideal_steps = max(unique_combos * config.ideal_steps_per_action, 1)
    efficiency_score = min(ideal_steps / total, 1.0)

    # --- Redundancy score ---
    redundant_total = repeated + len(redundant_navs)
    redundancy_score = 1.0 - min(redundant_total / total, 1.0)

    logger.info(
        "EfficiencyAnalyser: total=%d ideal=%d eff=%.2f redundancy=%.2f",
        total, ideal_steps, efficiency_score, redundancy_score,
    )

    status = "PASS" if efficiency_score >= 0.7 else ("WARNING" if efficiency_score >= 0.5 else "FAIL")

    return ValidationResult(
        validator_name="EfficiencyAnalyser",
        raw_score=efficiency_score,
        normalised_score=efficiency_score,
        status=status,
        issues=issues,
        comments=(
            f"Efficiency: {efficiency_score:.2%} "
            f"(ideal={ideal_steps}, actual={total}). "
            f"Redundant navigations: {len(redundant_navs)}. "
            f"Repeated actions: {repeated}."
        ),
        extra={
            "total_actions": total,
            "ideal_steps": ideal_steps,
            "efficiency_score": round(efficiency_score, 4),
            "redundancy_score": round(redundancy_score, 4),
            "repeated_actions": repeated,
            "redundant_navigations": len(redundant_navs),
        },
    )
