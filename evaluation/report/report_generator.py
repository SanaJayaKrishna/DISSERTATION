"""Report Generator — Stage 12.

Aggregates all ValidationResult objects into a structured evaluation report
and serialises it to JSON.

The report includes:
  * Overall plan score (weighted average).
  * Per-metric scores and statuses.
  * All errors and warnings.
  * Capability trace (when enabled).
  * Plan metadata.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from evaluation.config import EvaluationConfig, Severity
from evaluation.validators.base import ValidationResult

logger = logging.getLogger(__name__)


def generate_report(
    results: Dict[str, ValidationResult],
    config: EvaluationConfig,
    plan_metadata: Dict[str, Any],
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Aggregate validation results into a structured evaluation report.

    Args:
        results: Mapping of metric-name → :class:`ValidationResult`.
        config: Evaluation configuration (weights, thresholds).
        plan_metadata: Plan metadata dict to embed in the report header.
        output_path: Optional file path to write the JSON report to.

    Returns:
        Complete report as a Python dict (also serialisable to JSON).
    """
    weights = config.weights

    # ------------------------------------------------------------------
    # Per-metric score extraction
    # ------------------------------------------------------------------
    metric_scores: Dict[str, float] = {}
    metric_statuses: Dict[str, str] = {}

    metric_key_map = {
        "task_success":      "GoalValidator",
        "capability":        "CapabilityValidator",
        "constraints":       "ConstraintValidator",
        "action_validity":   "ActionValidator",
        "object_validity":   "ObjectValidator",
        "location_validity": "LocationValidator",
        "skill_mapping":     "SkillValidator",
        "sequence":          "SequenceValidator",
        "efficiency":        "EfficiencyAnalyser",
    }

    for metric_key, validator_name in metric_key_map.items():
        result = results.get(validator_name)
        if result:
            metric_scores[metric_key] = result.normalised_score
            metric_statuses[metric_key] = result.status
        else:
            metric_scores[metric_key] = 0.0
            metric_statuses[metric_key] = "MISSING"

    # ------------------------------------------------------------------
    # Overall weighted score
    # ------------------------------------------------------------------
    overall_score = sum(
        weights.get(k, 0.0) * metric_scores.get(k, 0.0)
        for k in weights
    )

    # ------------------------------------------------------------------
    # Task success (binary from GoalValidator)
    # ------------------------------------------------------------------
    task_success = metric_scores.get("task_success", 0.0) >= 0.5

    # ------------------------------------------------------------------
    # Aggregate errors and warnings
    # ------------------------------------------------------------------
    all_errors: List[Dict[str, Any]] = []
    all_warnings: List[Dict[str, Any]] = []

    for result in results.values():
        for issue in result.issues:
            if issue.severity in (Severity.CRITICAL, Severity.ERROR):
                all_errors.append(issue.to_dict())
            else:
                all_warnings.append(issue.to_dict())

    # ------------------------------------------------------------------
    # Capability trace (from CapabilityValidator)
    # ------------------------------------------------------------------
    capability_trace: List[Dict[str, Any]] = []
    if config.report_capability_trace:
        cap_result = results.get("CapabilityValidator")
        if cap_result:
            capability_trace = cap_result.extra.get("capability_trace", [])

    # ------------------------------------------------------------------
    # Per-validator detail block
    # ------------------------------------------------------------------
    validator_details: Dict[str, Any] = {
        name: result.to_dict() for name, result in results.items()
    }

    # ------------------------------------------------------------------
    # Determine overall status
    # ------------------------------------------------------------------
    if all_errors:
        overall_status = "FAIL" if overall_score < config.thresholds.warn_threshold else "WARNING"
    else:
        overall_status = "PASS" if overall_score >= config.thresholds.pass_threshold else "WARNING"

    # ------------------------------------------------------------------
    # Compose report
    # ------------------------------------------------------------------
    report: Dict[str, Any] = {
        "report_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_metadata": plan_metadata,
        "task_success": task_success,
        "overall_score": round(overall_score, 4),
        "overall_status": overall_status,
        "metrics": {
            k: {
                "score": round(v, 4),
                "status": metric_statuses.get(k, "UNKNOWN"),
                "weight": weights.get(k, 0.0),
            }
            for k, v in metric_scores.items()
        },
        "errors": all_errors,
        "warnings": all_warnings,
        "capability_trace": capability_trace,
        "validator_details": validator_details,
        "config": {
            "strict_mode": config.strict_mode,
            "weights": config.weights,
            "thresholds": {
                "pass": config.thresholds.pass_threshold,
                "warn": config.thresholds.warn_threshold,
            },
        },
    }

    # ------------------------------------------------------------------
    # Write to file if requested
    # ------------------------------------------------------------------
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        logger.info("Evaluation report written to %s", out.resolve())

    return report
