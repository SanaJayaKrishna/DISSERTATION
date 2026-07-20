"""Stage 5 — Skill Validator.

Checks that every action in the plan maps to exactly one skill in the
ontology and that the LLM-provided grounded skill (if present) matches the
ontology resolution.

Score = mapped_actions / total_actions.
"""
from __future__ import annotations

import logging
from typing import Dict, List

from evaluation.models.plan import GeneratedPlan, PlanAction
from evaluation.models.ontology import SkillOntology
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


def validate_skills(plan: GeneratedPlan, ontology: SkillOntology) -> ValidationResult:
    """Validate action-to-skill mapping and LLM grounding consistency.

    Args:
        plan: Parsed generated plan.
        ontology: Loaded skill ontology.

    Returns:
        :class:`ValidationResult` with mapping issues and accuracy score.
    """
    issues: List[ValidationIssue] = []
    total = len(plan.all_actions)
    mapped = 0

    # Build grounded_skill lookup: (checkpoint_id, step) -> abstract_skill
    grounded_lookup: Dict[tuple, str] = {}
    for cp in plan.checkpoints:
        for gs in cp.grounded_skills:
            grounded_lookup[(cp.checkpoint_id, gs.step)] = gs.abstract_skill

    for action in plan.all_actions:
        resolved = ontology.find_skill(action.action)

        if resolved is None:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.SKILL_NOT_FOUND,
                    message=(
                        f"No skill mapping found for action '{action.action}' "
                        f"(checkpoint {action.checkpoint_id}, step {action.step})."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion=(
                        "Add an entry to the skill ontology with "
                        f"abstract_skill='{action.action}' or a matching alias."
                    ),
                )
            )
            continue

        mapped += 1

        # Cross-check with LLM-provided grounding if available
        llm_skill = grounded_lookup.get((action.checkpoint_id, action.step))
        if llm_skill:
            llm_resolved = ontology.find_skill(llm_skill)
            if (
                llm_resolved is not None
                and llm_resolved.abstract_skill != resolved.abstract_skill
            ):
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.SKILL_NOT_FOUND,
                        message=(
                            f"Skill mismatch for '{action.action}' at "
                            f"checkpoint {action.checkpoint_id} step {action.step}: "
                            f"ontology resolves to '{resolved.abstract_skill}' but "
                            f"LLM grounded to '{llm_resolved.abstract_skill}'."
                        ),
                        action_index=action.global_index,
                        checkpoint_id=action.checkpoint_id,
                        severity=Severity.WARNING,
                        suggestion=(
                            "Review whether the LLM grounding is semantically correct."
                        ),
                        extra={
                            "ontology_skill": resolved.abstract_skill,
                            "llm_skill": llm_resolved.abstract_skill,
                        },
                    )
                )

    raw_score = mapped / total if total > 0 else 1.0
    status = "PASS" if raw_score == 1.0 else ("WARNING" if raw_score >= 0.6 else "FAIL")

    return ValidationResult(
        validator_name="SkillValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{mapped}/{total} actions map to valid skills. "
            f"Score: {raw_score:.2%}."
        ),
        extra={"mapped_actions": mapped, "total_actions": total},
    )
