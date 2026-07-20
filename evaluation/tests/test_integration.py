"""
Integration test: Run the full evaluation pipeline on the sample plan.

Run with:
    cd /home/sjk/DISSERTATION
    python -m pytest evaluation/tests/test_integration.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the package importable when run from the project root
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest
from evaluation.evaluator import Evaluator, run_evaluation
from evaluation.config import EvaluationConfig

ROBOT_PATH    = ROOT / "robots" / "aliengo.json"
WORLD_PATH    = ROOT / "worlds" / "college.json"
ONTOLOGY_PATH = ROOT / "robot_skill_ontology.json"
PLAN_PATH     = ROOT / "sample plan.json"


@pytest.mark.skipif(
    not all(p.exists() for p in [ROBOT_PATH, WORLD_PATH, ONTOLOGY_PATH, PLAN_PATH]),
    reason="One or more input files are missing."
)
class TestIntegration:
    """End-to-end integration tests using the real sample plan."""

    def test_run_evaluation_returns_dict(self):
        report = run_evaluation(
            robot_path=ROBOT_PATH,
            world_path=WORLD_PATH,
            ontology_path=ONTOLOGY_PATH,
            plan_path=PLAN_PATH,
        )
        assert isinstance(report, dict)

    def test_report_has_required_keys(self):
        report = run_evaluation(
            robot_path=ROBOT_PATH,
            world_path=WORLD_PATH,
            ontology_path=ONTOLOGY_PATH,
            plan_path=PLAN_PATH,
        )
        required = {
            "overall_score", "overall_status", "task_success",
            "metrics", "errors", "warnings", "capability_trace",
            "plan_metadata", "validator_details",
        }
        assert required.issubset(set(report.keys()))

    def test_overall_score_in_range(self):
        report = run_evaluation(
            robot_path=ROBOT_PATH,
            world_path=WORLD_PATH,
            ontology_path=ONTOLOGY_PATH,
            plan_path=PLAN_PATH,
        )
        score = report["overall_score"]
        assert 0.0 <= score <= 1.0

    def test_capability_trace_populated(self):
        config = EvaluationConfig(report_capability_trace=True)
        report = Evaluator(config).evaluate(
            robot_path=ROBOT_PATH,
            world_path=WORLD_PATH,
            ontology_path=ONTOLOGY_PATH,
            plan_path=PLAN_PATH,
        )
        # Aliengo has limited caps — trace should have entries
        assert len(report["capability_trace"]) > 0

    def test_all_metrics_present(self):
        report = run_evaluation(
            robot_path=ROBOT_PATH,
            world_path=WORLD_PATH,
            ontology_path=ONTOLOGY_PATH,
            plan_path=PLAN_PATH,
        )
        expected_metrics = {
            "task_success", "capability", "constraints",
            "action_validity", "object_validity", "location_validity",
            "skill_mapping", "sequence", "efficiency",
        }
        assert expected_metrics.issubset(set(report["metrics"].keys()))

    def test_report_is_json_serialisable(self):
        report = run_evaluation(
            robot_path=ROBOT_PATH,
            world_path=WORLD_PATH,
            ontology_path=ONTOLOGY_PATH,
            plan_path=PLAN_PATH,
        )
        try:
            json.dumps(report)
        except (TypeError, ValueError) as e:
            pytest.fail(f"Report is not JSON-serialisable: {e}")

    def test_strict_mode_stops_on_fail(self):
        """Strict mode should not crash — it should just stop early."""
        config = EvaluationConfig(strict_mode=True)
        report = Evaluator(config).evaluate(
            robot_path=ROBOT_PATH,
            world_path=WORLD_PATH,
            ontology_path=ONTOLOGY_PATH,
            plan_path=PLAN_PATH,
        )
        assert isinstance(report, dict)
