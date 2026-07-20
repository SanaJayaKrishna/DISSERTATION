"""Stage 1 — Schema Validator.

Checks structural integrity of the generated plan before any semantic
validation is attempted.  If this validator returns FAIL the pipeline
stops immediately (strict schema enforcement).

Checks performed:
* Required top-level fields present (``goal``, ``checkpoints``).
* Every checkpoint has required fields and a non-empty ``actions`` list.
* Every action has required fields (``step``, ``action``).
* No duplicate ``checkpoint_id`` values.
* No duplicate ``step`` values within a checkpoint.
* Action names are non-empty strings.
"""
from __future__ import annotations

import logging
from typing import List

from evaluation.models.plan import GeneratedPlan
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)

# Required keys at each level
_PLAN_REQUIRED = {"goal", "checkpoints"}
_CP_REQUIRED = {"checkpoint_id", "actions"}
_ACTION_REQUIRED = {"action"}


def validate_schema(plan: GeneratedPlan) -> ValidationResult:
    """Validate the structural schema of a generated plan.

    Args:
        plan: Parsed :class:`GeneratedPlan` to validate.

    Returns:
        :class:`ValidationResult` with status PASS / FAIL and any issues found.
    """
    issues: List[ValidationIssue] = []
    raw = plan.raw

    # --- Top-level required fields -----------------------------------------
    for key in _PLAN_REQUIRED:
        if key not in raw:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.MISSING_FIELD,
                    message=f"Top-level field '{key}' is missing from the plan.",
                    severity=Severity.CRITICAL,
                    suggestion=f"Ensure the plan JSON contains a '{key}' field.",
                )
            )

    if not raw.get("checkpoints"):
        issues.append(
            ValidationIssue(
                code=ErrorCode.SCHEMA_INVALID,
                message="Plan contains no checkpoints.",
                severity=Severity.CRITICAL,
                suggestion="The plan must contain at least one checkpoint.",
            )
        )
        # No point continuing if there are no checkpoints
        return _make_result(issues)

    # --- Checkpoint-level checks --------------------------------------------
    seen_cp_ids: set = set()
    for cp in plan.checkpoints:
        cp_id = cp.checkpoint_id

        # Duplicate checkpoint IDs
        if cp_id in seen_cp_ids:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.DUPLICATE_ID,
                    message=f"Duplicate checkpoint_id: {cp_id}.",
                    checkpoint_id=cp_id,
                    severity=Severity.ERROR,
                    suggestion="Each checkpoint must have a unique checkpoint_id.",
                )
            )
        seen_cp_ids.add(cp_id)

        if not cp.actions:
            issues.append(
                ValidationIssue(
                    code=ErrorCode.SCHEMA_INVALID,
                    message=f"Checkpoint {cp_id} has no actions.",
                    checkpoint_id=cp_id,
                    severity=Severity.ERROR,
                    suggestion="Each checkpoint must contain at least one action.",
                )
            )
            continue

        # --- Action-level checks -------------------------------------------
        seen_steps: set = set()
        for action in cp.actions:
            if not action.action or not action.action.strip():
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.MALFORMED_ACTION,
                        message=(
                            f"Checkpoint {cp_id}, step {action.step}: "
                            "'action' field is empty or missing."
                        ),
                        checkpoint_id=cp_id,
                        action_index=action.global_index,
                        severity=Severity.ERROR,
                        suggestion="Every action must have a non-empty 'action' name.",
                    )
                )
            if action.step in seen_steps:
                issues.append(
                    ValidationIssue(
                        code=ErrorCode.DUPLICATE_ID,
                        message=(
                            f"Checkpoint {cp_id}: duplicate step index {action.step}."
                        ),
                        checkpoint_id=cp_id,
                        action_index=action.global_index,
                        severity=Severity.WARNING,
                        suggestion="Step indices within a checkpoint must be unique.",
                    )
                )
            seen_steps.add(action.step)

    return _make_result(issues)


def _make_result(issues: List[ValidationIssue]) -> ValidationResult:
    """Build the final ValidationResult from the collected issues.

    Args:
        issues: All issues found during validation.

    Returns:
        :class:`ValidationResult` with score and status.
    """
    critical_or_error = [
        i for i in issues if i.severity in (Severity.CRITICAL, Severity.ERROR)
    ]
    score = 1.0 if not critical_or_error else 0.0
    status = "PASS" if score == 1.0 else ("WARNING" if not critical_or_error else "FAIL")

    logger.debug(
        "SchemaValidator: %d issues found, status=%s", len(issues), status
    )

    return ValidationResult(
        validator_name="SchemaValidator",
        raw_score=score,
        normalised_score=score,
        status=status,
        issues=issues,
        comments=(
            "Schema is valid — all required fields are present."
            if not issues
            else f"{len(critical_or_error)} structural error(s) found."
        ),
    )
