"""Deterministic Capability-Aware Plan Evaluation Framework — Main Entry Point.

The :class:`Evaluator` class orchestrates the full 11-stage validation
pipeline and produces a structured JSON report.

Usage (from any Python context, including Streamlit)::

    from evaluation.evaluator import Evaluator, EvaluationConfig

    config = EvaluationConfig()
    evaluator = Evaluator(config)

    report = evaluator.evaluate(
        robot_path="robots/aliengo.json",
        world_path="worlds/college.json",
        ontology_path="robot_skill_ontology.json",
        plan_path="sample plan.json",
        output_path="outputs/evaluation_report.json",  # optional
    )

    print(report["overall_score"])
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from evaluation.config import EvaluationConfig, LOG_FORMAT, LOG_LEVEL, Severity
from evaluation.loader.json_loader import load_all
from evaluation.metrics.efficiency import compute_efficiency
from evaluation.models.plan import GeneratedPlan
from evaluation.models.robot import RobotCapabilities
from evaluation.models.world import WorldState
from evaluation.models.ontology import SkillOntology
from evaluation.report.report_generator import generate_report
from evaluation.validators.action_validator import validate_actions
from evaluation.validators.capability_validator import validate_capabilities
from evaluation.validators.constraint_validator import validate_constraints
from evaluation.validators.dependency_validator import validate_dependencies
from evaluation.validators.goal_validator import validate_goal
from evaluation.validators.location_validator import validate_locations
from evaluation.validators.object_validator import validate_objects
from evaluation.validators.schema_validator import validate_schema
from evaluation.validators.sequence_validator import validate_sequence
from evaluation.validators.skill_validator import validate_skills
from evaluation.validators.base import ValidationResult

# ---------------------------------------------------------------------------
# Module-level logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class Evaluator:
    """Orchestrates the full deterministic plan evaluation pipeline.

    The evaluator is stateless between ``evaluate()`` calls and can be reused
    across multiple plans.  It is designed to be called from:
      * A Streamlit application.
      * A CLI script.
      * Unit tests.

    Attributes:
        config: Evaluation configuration controlling weights, thresholds,
            and verbosity.
    """

    def __init__(self, config: Optional[EvaluationConfig] = None) -> None:
        """Initialise the evaluator with an optional configuration.

        Args:
            config: Evaluation configuration.  Defaults to
                :class:`EvaluationConfig` with all defaults.
        """
        self.config = config or EvaluationConfig()
        logger.info(
            "Evaluator initialised. strict_mode=%s, weights=%s",
            self.config.strict_mode,
            self.config.weights,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        robot_path: Union[str, Path],
        world_path: Union[str, Path],
        ontology_path: Union[str, Path],
        plan_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Run the complete evaluation pipeline on a generated plan.

        This method:
        1. Loads all JSON inputs into typed internal models (once).
        2. Runs all 11 validation stages in order.
        3. Computes efficiency metrics.
        4. Generates and (optionally) writes the evaluation report.

        Args:
            robot_path: Path to the robot capabilities JSON.
            world_path: Path to the world JSON.
            ontology_path: Path to the skill ontology JSON.
            plan_path: Path to the generated plan JSON.
            output_path: Optional path to write ``evaluation_report.json``.

        Returns:
            Evaluation report as a Python dict (also valid JSON).

        Raises:
            FileNotFoundError: If any input file is missing.
            ValueError: If any input file contains malformed JSON.
        """
        logger.info("=" * 60)
        logger.info("Starting evaluation pipeline")
        logger.info("  Robot:    %s", robot_path)
        logger.info("  World:    %s", world_path)
        logger.info("  Ontology: %s", ontology_path)
        logger.info("  Plan:     %s", plan_path)
        logger.info("=" * 60)

        # ------------------------------------------------------------------
        # Stage 0: Load all inputs
        # ------------------------------------------------------------------
        robot, world, ontology, plan = load_all(
            robot_path=robot_path,
            world_path=world_path,
            ontology_path=ontology_path,
            plan_path=plan_path,
        )

        # ------------------------------------------------------------------
        # Run pipeline
        # ------------------------------------------------------------------
        results: Dict[str, ValidationResult] = {}

        results = self._run_pipeline(robot, world, ontology, plan, results)

        # ------------------------------------------------------------------
        # Stage 11: Efficiency analysis
        # ------------------------------------------------------------------
        logger.info("Stage 11: Efficiency analysis")
        results["EfficiencyAnalyser"] = compute_efficiency(plan, self.config)

        # ------------------------------------------------------------------
        # Stage 12: Generate report
        # ------------------------------------------------------------------
        logger.info("Stage 12: Generating report")
        plan_metadata = {
            "robot": plan.metadata.robot,
            "world": plan.metadata.world,
            "task": plan.metadata.task,
            "model": plan.metadata.model,
            "goal": plan.goal,
            "total_actions": len(plan.all_actions),
            "total_checkpoints": len(plan.checkpoints),
        }

        report = generate_report(
            results=results,
            config=self.config,
            plan_metadata=plan_metadata,
            output_path=output_path,
        )

        logger.info(
            "Evaluation complete. overall_score=%.4f status=%s",
            report["overall_score"],
            report["overall_status"],
        )
        return report

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        robot: RobotCapabilities,
        world: WorldState,
        ontology: SkillOntology,
        plan: GeneratedPlan,
        results: Dict[str, ValidationResult],
    ) -> Dict[str, ValidationResult]:
        """Execute the ordered validation stages.

        The pipeline is Open/Closed: to add a validator, implement a function
        that accepts the required inputs and returns a :class:`ValidationResult`,
        then append it to this method.  No other code needs to change.

        Args:
            robot: Loaded robot capabilities.
            world: Loaded world state.
            ontology: Loaded skill ontology.
            plan: Loaded generated plan.
            results: Result accumulator dict (mutated in-place).

        Returns:
            Updated results dict.
        """
        stages = [
            ("Stage 1:  Schema validation",      self._stage_schema),
            ("Stage 2:  Action validation",      self._stage_action),
            ("Stage 3:  Object validation",      self._stage_object),
            ("Stage 4:  Location validation",    self._stage_location),
            ("Stage 5:  Skill validation",       self._stage_skill),
            ("Stage 6:  Capability validation",  self._stage_capability),
            ("Stage 7:  Constraint validation",  self._stage_constraint),
            ("Stage 8:  Dependency validation",  self._stage_dependency),
            ("Stage 9:  Sequence validation",    self._stage_sequence),
            ("Stage 10: Goal validation",        self._stage_goal),
        ]

        for label, stage_fn in stages:
            logger.info(label)
            result = stage_fn(robot, world, ontology, plan)
            results[result.validator_name] = result

            # Strict mode: stop on FAIL
            if self.config.strict_mode and result.status == "FAIL":
                logger.warning(
                    "strict_mode=True — pipeline halted after %s (FAIL).",
                    result.validator_name,
                )
                break

        return results

    # ------------------------------------------------------------------
    # Stage delegation methods
    # Each wraps a stateless validator function with exception handling.
    # ------------------------------------------------------------------

    def _stage_schema(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_schema(plan)

    def _stage_action(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_actions(plan, ontology)

    def _stage_object(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_objects(plan, world)

    def _stage_location(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_locations(plan, world)

    def _stage_skill(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_skills(plan, ontology)

    def _stage_capability(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_capabilities(plan, robot, ontology)

    def _stage_constraint(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_constraints(plan, robot, world)

    def _stage_dependency(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_dependencies(plan)

    def _stage_sequence(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_sequence(plan)

    def _stage_goal(self, robot, world, ontology, plan) -> ValidationResult:
        return validate_goal(plan)


# ---------------------------------------------------------------------------
# Convenience function for Streamlit (avoids creating Evaluator object)
# ---------------------------------------------------------------------------

def run_evaluation(
    robot_path: Union[str, Path],
    world_path: Union[str, Path],
    ontology_path: Union[str, Path],
    plan_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    config: Optional[EvaluationConfig] = None,
) -> Dict[str, Any]:
    """One-shot evaluation convenience function.

    Args:
        robot_path: Path to the robot capabilities JSON.
        world_path: Path to the world JSON.
        ontology_path: Path to the skill ontology JSON.
        plan_path: Path to the generated plan JSON (or a dict if already parsed).
        output_path: Optional path to write the evaluation report.
        config: Optional evaluation configuration.

    Returns:
        Evaluation report dict.
    """
    return Evaluator(config).evaluate(
        robot_path=robot_path,
        world_path=world_path,
        ontology_path=ontology_path,
        plan_path=plan_path,
        output_path=output_path,
    )
