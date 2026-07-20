"""Unit tests for individual validators using synthetic minimal fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest
from evaluation.models.plan import GeneratedPlan, Checkpoint, PlanAction, PlanMetadata
from evaluation.models.robot import RobotCapabilities, RobotMetadata, BinaryCapabilities
from evaluation.models.world import WorldState, Room
from evaluation.models.ontology import SkillOntology, Skill, SkillImplementation
from evaluation.validators.schema_validator import validate_schema
from evaluation.validators.action_validator import validate_actions
from evaluation.validators.object_validator import validate_objects
from evaluation.validators.location_validator import validate_locations
from evaluation.validators.capability_validator import validate_capabilities
from evaluation.validators.constraint_validator import validate_constraints
from evaluation.validators.dependency_validator import validate_dependencies
from evaluation.validators.sequence_validator import validate_sequence
from evaluation.validators.goal_validator import validate_goal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_action(action: str, obj: str = "", location: str = "", step: int = 1,
                 cp_id: int = 1, gidx: int = 0) -> PlanAction:
    return PlanAction(
        step=step, action=action, obj=obj, location=location,
        checkpoint_id=cp_id, global_index=gidx, raw={},
    )


def _make_plan(actions: list, task: str = "Bring me water",
               goal: str = "Bring water to user") -> GeneratedPlan:
    cp = Checkpoint(
        checkpoint_id=1,
        checkpoint_goal="Test checkpoint",
        entry_state="Start",
        exit_state="Done, water delivered to user",
        is_replannable=False,
        actions=actions,
        grounded_skills=[],
    )
    return GeneratedPlan(
        metadata=PlanMetadata(robot="test_robot", world="test_world",
                              task=task, model="test_model"),
        goal=goal,
        checkpoints=[cp],
        constraints=[],
        execution_summary={"plan_valid": True},
        all_actions=actions,
        raw={"goal": goal, "checkpoints": []},
    )


def _make_robot(can_pick: bool = True, can_navigate: bool = True,
                can_place: bool = True, can_detect: bool = True) -> RobotCapabilities:
    binary = BinaryCapabilities(
        can_pick=can_pick,
        can_navigate=can_navigate,
        can_place=can_place,
        can_detect_objects=can_detect,
        supports_localization=True,
        supports_obstacle_avoidance=True,
    )
    return RobotCapabilities(
        metadata=RobotMetadata(name="test_robot"),
        binary=binary,
    )


def _make_world(rooms=None, objects=None) -> WorldState:
    rooms = rooms or [Room("kitchen", "Kitchen"), Room("bedroom", "Bedroom")]
    objs = objects or ["bottle", "cup", "water", "book"]
    return WorldState(
        name="Test World",
        env_type="Indoor",
        rooms=rooms,
        objects=objs,
        room_names_lower=WorldState.build_room_names_lower(rooms),
    )


def _make_ontology() -> SkillOntology:
    skills = [
        Skill(
            skill_id="NAV_001", abstract_skill="navigate_to_room",
            category="Navigation",
            aliases=["navigate", "go_to", "move_to"],
            required_capabilities=["can_navigate", "supports_localization"],
        ),
        Skill(
            skill_id="MAN_001", abstract_skill="pick_object",
            category="Manipulation",
            aliases=["pick", "grab", "grasp"],
            required_capabilities=["can_pick"],
        ),
        Skill(
            skill_id="MAN_002", abstract_skill="place_object",
            category="Manipulation",
            aliases=["place", "put", "deliver"],
            required_capabilities=["can_place"],
        ),
        Skill(
            skill_id="PER_001", abstract_skill="detect_object",
            category="Perception",
            aliases=["detect", "find", "locate"],
            required_capabilities=["can_detect_objects"],
        ),
    ]
    return SkillOntology(version="1.0", skills=skills)


# ---------------------------------------------------------------------------
# Schema Validator Tests
# ---------------------------------------------------------------------------

class TestSchemaValidator:
    def test_valid_plan_passes(self):
        actions = [_make_action("navigate_to_room", location="Kitchen")]
        plan = _make_plan(actions)
        # Provide a valid raw dict that the schema validator inspects
        plan.raw = {
            "goal": plan.goal,
            "checkpoints": [
                {
                    "checkpoint_id": 1,
                    "actions": [{"step": 1, "action": "navigate_to_room", "location": "Kitchen"}],
                }
            ],
        }
        result = validate_schema(plan)
        assert result.status == "PASS"

    def test_empty_checkpoints_fails(self):
        actions = []
        plan = _make_plan(actions)
        plan.raw = {"goal": "test", "checkpoints": []}
        plan.checkpoints = []
        plan.all_actions = []
        result = validate_schema(plan)
        assert result.status == "FAIL"

    def test_empty_action_name_flagged(self):
        actions = [_make_action("", location="Kitchen")]
        plan = _make_plan(actions)
        # Supply a raw dict with the empty action so the validator sees it
        plan.raw = {
            "goal": plan.goal,
            "checkpoints": [
                {
                    "checkpoint_id": 1,
                    "actions": [{"step": 1, "action": "", "location": "Kitchen"}],
                }
            ],
        }
        result = validate_schema(plan)
        assert any(i.code == "MALFORMED_ACTION" for i in result.issues)


# ---------------------------------------------------------------------------
# Action Validator Tests
# ---------------------------------------------------------------------------

class TestActionValidator:
    def test_known_action_passes(self):
        actions = [_make_action("navigate_to_room")]
        plan = _make_plan(actions)
        ontology = _make_ontology()
        result = validate_actions(plan, ontology)
        assert result.normalised_score == 1.0

    def test_unknown_action_fails(self):
        actions = [_make_action("teleport")]
        plan = _make_plan(actions)
        ontology = _make_ontology()
        result = validate_actions(plan, ontology)
        assert result.normalised_score < 1.0
        assert any(i.code == "ACTION_NOT_FOUND" for i in result.issues)

    def test_alias_action_resolves(self):
        actions = [_make_action("navigate")]  # alias for navigate_to_room
        plan = _make_plan(actions)
        ontology = _make_ontology()
        result = validate_actions(plan, ontology)
        assert result.normalised_score == 1.0


# ---------------------------------------------------------------------------
# Object Validator Tests
# ---------------------------------------------------------------------------

class TestObjectValidator:
    def test_existing_object_passes(self):
        actions = [_make_action("pick_object", obj="bottle")]
        plan = _make_plan(actions)
        world = _make_world()
        result = validate_objects(plan, world)
        assert result.normalised_score == 1.0

    def test_missing_object_flagged(self):
        actions = [_make_action("pick_object", obj="pizza")]
        plan = _make_plan(actions)
        world = _make_world()
        result = validate_objects(plan, world)
        assert any(i.code == "OBJECT_NOT_FOUND" for i in result.issues)

    def test_empty_object_skipped(self):
        actions = [_make_action("navigate_to_room", obj="", location="Kitchen")]
        plan = _make_plan(actions)
        world = _make_world()
        result = validate_objects(plan, world)
        assert result.normalised_score == 1.0  # no objects to check


# ---------------------------------------------------------------------------
# Location Validator Tests
# ---------------------------------------------------------------------------

class TestLocationValidator:
    def test_existing_location_passes(self):
        actions = [_make_action("navigate_to_room", location="Kitchen")]
        plan = _make_plan(actions)
        world = _make_world()
        result = validate_locations(plan, world)
        assert result.normalised_score == 1.0

    def test_missing_location_flagged(self):
        actions = [_make_action("navigate_to_room", location="Garage")]
        plan = _make_plan(actions)
        world = _make_world()
        result = validate_locations(plan, world)
        assert any(i.code == "INVALID_LOCATION" for i in result.issues)


# ---------------------------------------------------------------------------
# Capability Validator Tests
# ---------------------------------------------------------------------------

class TestCapabilityValidator:
    def test_robot_with_capabilities_passes(self):
        actions = [_make_action("navigate_to_room", location="Kitchen")]
        plan = _make_plan(actions)
        robot = _make_robot(can_navigate=True)
        ontology = _make_ontology()
        result = validate_capabilities(plan, robot, ontology)
        assert result.normalised_score == 1.0

    def test_missing_capability_flagged(self):
        actions = [_make_action("pick_object", obj="bottle")]
        plan = _make_plan(actions)
        robot = _make_robot(can_pick=False)
        ontology = _make_ontology()
        result = validate_capabilities(plan, robot, ontology)
        assert any(i.code == "CAPABILITY_MISSING" for i in result.issues)

    def test_capability_trace_has_entries(self):
        actions = [_make_action("navigate_to_room", location="Kitchen")]
        plan = _make_plan(actions)
        robot = _make_robot()
        ontology = _make_ontology()
        result = validate_capabilities(plan, robot, ontology)
        assert len(result.extra.get("capability_trace", [])) > 0


# ---------------------------------------------------------------------------
# Constraint Validator Tests
# ---------------------------------------------------------------------------

class TestConstraintValidator:
    def test_pick_without_capability_flagged(self):
        actions = [_make_action("pick_object", obj="bottle", location="Kitchen")]
        plan = _make_plan(actions)
        robot = _make_robot(can_pick=False)
        world = _make_world()
        result = validate_constraints(plan, robot, world)
        assert any(i.code == "CONSTRAINT_VIOLATION" for i in result.issues)

    def test_pick_with_capability_passes(self):
        actions = [_make_action("pick_object", obj="bottle", location="Kitchen")]
        plan = _make_plan(actions)
        robot = _make_robot(can_pick=True)
        world = _make_world()
        result = validate_constraints(plan, robot, world)
        errors = [i for i in result.issues if i.severity == "ERROR"]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Dependency Validator Tests
# ---------------------------------------------------------------------------

class TestDependencyValidator:
    def test_correct_order_passes(self):
        actions = [
            _make_action("navigate_to_room", location="kitchen", gidx=0),
            _make_action("detect_object", obj="bottle", location="kitchen", gidx=1),
            _make_action("pick_object", obj="bottle", location="kitchen", gidx=2),
            _make_action("place_object", obj="bottle", location="kitchen", gidx=3),
        ]
        plan = _make_plan(actions)
        result = validate_dependencies(plan)
        errors = [i for i in result.issues if i.severity == "ERROR"]
        assert len(errors) == 0

    def test_place_before_pick_flagged(self):
        actions = [
            _make_action("place_object", obj="bottle", location="kitchen", gidx=0),
            _make_action("pick_object", obj="bottle", location="kitchen", gidx=1),
        ]
        plan = _make_plan(actions)
        result = validate_dependencies(plan)
        errors = [i for i in result.issues if i.severity == "ERROR"]
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Sequence Validator Tests
# ---------------------------------------------------------------------------

class TestSequenceValidator:
    def test_correct_sequence_passes(self):
        actions = [
            _make_action("navigate_to_room", gidx=0),
            _make_action("detect_object", gidx=1),
            _make_action("pick_object", gidx=2),
            _make_action("place_object", gidx=3),
        ]
        plan = _make_plan(actions)
        result = validate_sequence(plan)
        assert result.normalised_score >= 0.8

    def test_single_action_passes(self):
        actions = [_make_action("navigate_to_room", gidx=0)]
        plan = _make_plan(actions)
        result = validate_sequence(plan)
        assert result.status == "PASS"


# ---------------------------------------------------------------------------
# Goal Validator Tests
# ---------------------------------------------------------------------------

class TestGoalValidator:
    def test_matching_goal_passes(self):
        plan = _make_plan(
            actions=[_make_action("navigate_to_room")],
            task="Bring me water from kitchen",
            goal="Navigate to kitchen, pick water, bring water to user",
        )
        plan.checkpoints[0].exit_state = "Robot delivered water to user"
        plan.execution_summary = {"plan_valid": True}
        result = validate_goal(plan)
        assert result.normalised_score == 1.0

    def test_self_reported_invalid_fails(self):
        plan = _make_plan(
            actions=[_make_action("navigate_to_room")],
            task="Bring me water",
            goal="Navigate to kitchen",
        )
        plan.execution_summary = {"plan_valid": False}
        result = validate_goal(plan)
        assert result.normalised_score == 0.0
