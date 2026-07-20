"""Internal data models for the generated robot task plan."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlanAction:
    """A single atomic action step within a checkpoint.

    Attributes:
        step: 1-based step index within the checkpoint.
        action: Action name (e.g. ``navigate_to_room``).
        obj: Target object referenced by the action (may be empty).
        location: Location referenced by the action (may be empty).
        checkpoint_id: Parent checkpoint identifier.
        global_index: Monotonically increasing index across all actions in
            the entire plan (used by sequence / dependency validators).
        raw: Original raw JSON for this action.
    """
    step: int
    action: str
    obj: str
    location: str
    checkpoint_id: int
    global_index: int
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GroundedSkill:
    """Grounding information provided by the LLM for one plan step.

    Attributes:
        step: 1-based step index within the checkpoint.
        abstract_skill: Skill name the LLM claims to use.
        ros2_interface: ROS 2 interface path.
        reason: LLM-provided justification.
    """
    step: int
    abstract_skill: str
    ros2_interface: str
    reason: str


@dataclass
class Checkpoint:
    """A logical phase of the plan grouping related actions.

    Attributes:
        checkpoint_id: Unique numeric identifier.
        checkpoint_goal: Human-readable goal for this phase.
        entry_state: World state description at checkpoint entry.
        exit_state: World state description at checkpoint exit.
        is_replannable: Whether the planner can replan at this checkpoint.
        actions: Ordered list of plan actions.
        grounded_skills: LLM-provided skill groundings aligned by step number.
    """
    checkpoint_id: int
    checkpoint_goal: str
    entry_state: str
    exit_state: str
    is_replannable: bool
    actions: List[PlanAction]
    grounded_skills: List[GroundedSkill]


@dataclass
class PlanMetadata:
    """Header metadata from the generated plan JSON.

    Attributes:
        robot: Robot name used during planning.
        world: World environment name.
        task: Original natural-language task.
        model: Planner model identifier.
    """
    robot: str
    world: str
    task: str
    model: str


@dataclass
class GeneratedPlan:
    """Complete parsed plan ready for evaluation.

    Attributes:
        metadata: Plan header.
        goal: Overall mission goal string.
        checkpoints: Ordered list of plan checkpoints.
        constraints: LLM-stated plan constraints / caveats.
        execution_summary: LLM self-assessment block.
        all_actions: Flattened ordered list of every action across all
            checkpoints, sorted by ``global_index``.
        raw: Original parsed JSON.
    """
    metadata: PlanMetadata
    goal: str
    checkpoints: List[Checkpoint]
    constraints: List[str]
    execution_summary: Dict[str, Any]
    all_actions: List[PlanAction]
    raw: Dict[str, Any] = field(default_factory=dict)
