# evaluation/__init__.py
"""
Deterministic Capability-Aware Plan Evaluation Framework.

Primary entry points:
  * evaluation.evaluator.Evaluator          — full pipeline class
  * evaluation.evaluator.run_evaluation     — convenience one-shot function
  * evaluation.config.EvaluationConfig      — configuration dataclass
"""
from .evaluator import Evaluator, run_evaluation
from .config import EvaluationConfig

__all__ = ["Evaluator", "run_evaluation", "EvaluationConfig"]
