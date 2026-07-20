"""
Configuration for the Deterministic Capability-Aware Plan Evaluation Framework.

All tunable parameters live here so that the core pipeline never needs to be
modified when thresholds or weights change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: int = logging.INFO
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


# ---------------------------------------------------------------------------
# Metric weights  (must sum to 1.0)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "task_success":           0.02,  # Least weightage (not the primary focus of verification)
    "capability":             0.25,  # Highest weightage (primary focus of dissertation)
    "constraints":            0.20,  # Physical/operational constraint satisfaction
    "skill_mapping":          0.15,  # Correctness of mapping actions to skill ontology
    "action_validity":        0.10,
    "object_validity":        0.10,
    "location_validity":      0.08,
    "sequence":               0.07,
    "efficiency":             0.03,
}



# ---------------------------------------------------------------------------
# Score thresholds
# ---------------------------------------------------------------------------

@dataclass
class ScoreThresholds:
    """Thresholds that control PASS / WARNING / FAIL bands for each metric."""

    pass_threshold: float = 0.80      # score >= this -> PASS
    warn_threshold: float = 0.60      # score >= this -> WARNING
    # anything below warn_threshold -> FAIL


SCORE_THRESHOLDS: ScoreThresholds = ScoreThresholds()


# ---------------------------------------------------------------------------
# Evaluation modes
# ---------------------------------------------------------------------------

@dataclass
class EvaluationConfig:
    """
    Master configuration object passed to the Evaluator.

    Attributes:
        strict_mode: If True, the pipeline stops at the first FAIL and does
            not continue to subsequent validators.
        warn_as_error: Treat WARNING-level issues as errors (affects
            overall PASS/FAIL decision only; individual scores are unchanged).
        verbosity: 0=quiet, 1=normal, 2=verbose (controls how much detail
            goes into the evaluation report).
        weights: Per-metric weight mapping.  Values must sum to 1.0.
        thresholds: Score band thresholds.
        report_capability_trace: If True, the report includes a per-step
            Capability Trace table (recommended for dissertations).
        ideal_steps_per_action: Used by the efficiency analyser as the
            reference step count.  Override if your domain differs.
    """

    strict_mode: bool = False
    warn_as_error: bool = False
    verbosity: int = 1

    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: ScoreThresholds = field(default_factory=ScoreThresholds)

    report_capability_trace: bool = True

    # Efficiency tuning
    ideal_steps_per_action: int = 1  # 1 ideal step per logical action


# ---------------------------------------------------------------------------
# Error / warning codes used across all validators
# ---------------------------------------------------------------------------

class ErrorCode:
    """Centralised error-code constants (avoids magic strings)."""

    # Schema
    SCHEMA_INVALID          = "SCHEMA_INVALID"
    MISSING_FIELD           = "MISSING_FIELD"
    DUPLICATE_ID            = "DUPLICATE_ID"
    MALFORMED_ACTION        = "MALFORMED_ACTION"

    # Action
    ACTION_NOT_FOUND        = "ACTION_NOT_FOUND"

    # Object
    OBJECT_NOT_FOUND        = "OBJECT_NOT_FOUND"

    # Location
    INVALID_LOCATION        = "INVALID_LOCATION"

    # Skill
    SKILL_NOT_FOUND         = "SKILL_NOT_FOUND"

    # Capability
    CAPABILITY_MISSING      = "CAPABILITY_MISSING"

    # Constraint
    CONSTRAINT_VIOLATION    = "CONSTRAINT_VIOLATION"

    # Dependency
    DEPENDENCY_ERROR        = "DEPENDENCY_ERROR"

    # Sequence
    ORDERING_ERROR          = "ORDERING_ERROR"

    # Goal
    GOAL_NOT_REACHED        = "GOAL_NOT_REACHED"

    # Efficiency
    REDUNDANT_ACTION        = "REDUNDANT_ACTION"
    REDUNDANT_NAVIGATION    = "REDUNDANT_NAVIGATION"


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------

class Severity:
    CRITICAL = "CRITICAL"   # plan cannot execute
    ERROR    = "ERROR"      # step will fail
    WARNING  = "WARNING"    # step may fail or is suboptimal
    INFO     = "INFO"       # informational only
