"""JSON input loader — parses raw JSON files into typed internal models.

The evaluator never reads JSON directly; instead it calls :func:`load_all`
once and works entirely with Python objects thereafter.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from evaluation.models.robot import BinaryCapabilities, RobotCapabilities, RobotMetadata
from evaluation.models.world import Room, WorldState
from evaluation.models.ontology import Skill, SkillImplementation, SkillOntology
from evaluation.models.plan import (
    Checkpoint,
    GeneratedPlan,
    GroundedSkill,
    PlanAction,
    PlanMetadata,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _load_json(path: Union[str, Path]) -> Dict[str, Any]:
    """Load and parse a JSON file, raising a clear error on failure.

    Args:
        path: Filesystem path to the JSON file.

    Returns:
        Parsed JSON as a Python dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be parsed as JSON.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSON file not found: {p.resolve()}")
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {p}: {exc}") from exc


# ---------------------------------------------------------------------------
# Robot capabilities loader
# ---------------------------------------------------------------------------

def load_robot(path: Union[str, Path]) -> RobotCapabilities:
    """Parse a robot capabilities JSON file into :class:`RobotCapabilities`.

    Args:
        path: Path to ``<robot>.json``.

    Returns:
        Fully populated :class:`RobotCapabilities` instance.

    Raises:
        FileNotFoundError: File not found.
        ValueError: Malformed JSON or missing required top-level keys.
    """
    raw = _load_json(path)
    robot_block = raw.get("Robot", raw)  # handle both top-level and nested

    capabilities_block = robot_block.get("Capabilities", {})
    binary_block = capabilities_block.get("BinaryCapabilities", {})
    derived_block = capabilities_block.get("DerivedCapabilities", [])

    # Build BinaryCapabilities — map every JSON key onto a field if it exists
    bin_fields = {f for f in BinaryCapabilities.__dataclass_fields__}
    known_kwargs: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    for k, v in binary_block.items():
        if k in bin_fields:
            known_kwargs[k] = bool(v)
        else:
            extra[k] = v
    known_kwargs["extra"] = extra
    binary = BinaryCapabilities(**known_kwargs)

    # Derive robot name from filename stem if not embedded in the JSON
    stem = Path(path).stem
    metadata = RobotMetadata(
        name=robot_block.get("name", stem),
        robot_type=robot_block.get("type", robot_block.get("robot_type", "")),
        manufacturer=robot_block.get("manufacturer", ""),
        description=robot_block.get("description", ""),
    )

    return RobotCapabilities(
        metadata=metadata,
        binary=binary,
        derived=list(derived_block) if isinstance(derived_block, list) else [],
        raw=raw,
    )


# ---------------------------------------------------------------------------
# World loader
# ---------------------------------------------------------------------------

def _collect_world_objects(raw: Dict[str, Any]) -> List[str]:
    """Extract a flat list of all object names from the world JSON.

    The world JSON contains objects scattered across multiple nested sections
    (``cafeteria.equipment``, ``hostel.rooms``, ``academic_facilities.library``,
    ``sports_facilities.equipment``, ``static_structures``, etc.).  This
    function does a best-effort recursive extraction of every string leaf.

    Args:
        raw: Parsed world JSON dict.

    Returns:
        Flat list of unique object name strings.
    """
    objects: List[str] = []

    def _recurse(node: Any) -> None:
        if isinstance(node, str):
            objects.append(node)
        elif isinstance(node, list):
            for item in node:
                _recurse(item)
        elif isinstance(node, dict):
            for v in node.values():
                _recurse(v)

    # Exclude top-level structural keys that are not object collections
    skip_keys = {"environment", "zones", "rooms", "semantic_relations",
                 "interaction_rules", "default_robot_spawn_locations"}
    for k, v in raw.items():
        if k not in skip_keys:
            _recurse(v)

    return list(dict.fromkeys(objects))  # preserve order, deduplicate


def load_world(path: Union[str, Path]) -> WorldState:
    """Parse a world JSON file into :class:`WorldState`.

    Args:
        path: Path to ``<world>.json``.

    Returns:
        Fully populated :class:`WorldState` instance.

    Raises:
        FileNotFoundError: File not found.
        ValueError: Malformed JSON.
    """
    raw = _load_json(path)
    env = raw.get("environment", {})

    rooms: List[Room] = []
    for r in raw.get("rooms", []):
        room_id = r.get("id", r.get("name", ""))
        name = r.get("name", room_id)
        rooms.append(Room(room_id=room_id, name=name))

    objects = _collect_world_objects(raw)
    room_names_lower = WorldState.build_room_names_lower(rooms)

    return WorldState(
        name=env.get("name", Path(path).stem),
        env_type=env.get("type", ""),
        rooms=rooms,
        objects=objects,
        room_names_lower=room_names_lower,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Skill ontology loader
# ---------------------------------------------------------------------------

def load_ontology(path: Union[str, Path]) -> SkillOntology:
    """Parse the robot skill ontology JSON into :class:`SkillOntology`.

    Args:
        path: Path to ``robot_skill_ontology.json``.

    Returns:
        Fully indexed :class:`SkillOntology`.

    Raises:
        FileNotFoundError: File not found.
        ValueError: Malformed JSON.
    """
    raw = _load_json(path)
    skills: List[Skill] = []

    for entry in raw.get("skills", []):
        impls = [
            SkillImplementation(
                framework=i.get("framework", ""),
                ros2_interface_type=i.get("ros2_interface_type", ""),
                interface_name=i.get("interface_name", ""),
                message_type=i.get("message_type", ""),
            )
            for i in entry.get("implementations", [])
        ]
        skills.append(
            Skill(
                skill_id=entry.get("skill_id", ""),
                abstract_skill=entry.get("abstract_skill", ""),
                category=entry.get("category", ""),
                description=entry.get("description", ""),
                goal=entry.get("goal", ""),
                aliases=entry.get("aliases", []),
                required_capabilities=entry.get("required_capabilities", []),
                required_components=entry.get("required_components", []),
                preconditions=entry.get("preconditions", []),
                postconditions=entry.get("postconditions", []),
                failure_conditions=entry.get("failure_conditions", []),
                implementations=impls,
            )
        )

    logger.info("Loaded ontology: %d skills from %s", len(skills), path)
    return SkillOntology(version=raw.get("version", "1.0"), skills=skills)


# ---------------------------------------------------------------------------
# Generated plan loader
# ---------------------------------------------------------------------------

def load_plan(path: Union[str, Path]) -> GeneratedPlan:
    """Parse a generated plan JSON into :class:`GeneratedPlan`.

    The loader is tolerant of missing optional fields and assigns sensible
    defaults so that downstream validators can still run partial plans.

    Args:
        path: Path to ``generated_plan.json``.

    Returns:
        Fully populated :class:`GeneratedPlan`.

    Raises:
        FileNotFoundError: File not found.
        ValueError: Malformed JSON.
    """
    raw = _load_json(path)

    meta_block = raw.get("metadata", {})
    metadata = PlanMetadata(
        robot=meta_block.get("robot", ""),
        world=meta_block.get("world", ""),
        task=meta_block.get("task", ""),
        model=meta_block.get("model", ""),
    )

    global_index = 0
    checkpoints: List[Checkpoint] = []

    for cp_raw in raw.get("checkpoints", []):
        actions: List[PlanAction] = []
        for a_raw in cp_raw.get("actions", []):
            actions.append(
                PlanAction(
                    step=int(a_raw.get("step", 0)),
                    action=str(a_raw.get("action", "")),
                    obj=str(a_raw.get("object", a_raw.get("obj", ""))),
                    location=str(a_raw.get("location", "")),
                    checkpoint_id=int(cp_raw.get("checkpoint_id", 0)),
                    global_index=global_index,
                    raw=a_raw,
                )
            )
            global_index += 1

        grounded: List[GroundedSkill] = []
        for g_raw in cp_raw.get("grounded_skills", []):
            grounded.append(
                GroundedSkill(
                    step=int(g_raw.get("step", 0)),
                    abstract_skill=str(g_raw.get("abstract_skill", "")),
                    ros2_interface=str(g_raw.get("ros2_interface", "")),
                    reason=str(g_raw.get("reason", "")),
                )
            )

        checkpoints.append(
            Checkpoint(
                checkpoint_id=int(cp_raw.get("checkpoint_id", 0)),
                checkpoint_goal=str(cp_raw.get("checkpoint_goal", "")),
                entry_state=str(cp_raw.get("entry_state", "")),
                exit_state=str(cp_raw.get("exit_state", "")),
                is_replannable=bool(cp_raw.get("is_replannable", False)),
                actions=actions,
                grounded_skills=grounded,
            )
        )

    all_actions: List[PlanAction] = [
        a for cp in checkpoints for a in cp.actions
    ]

    logger.info(
        "Loaded plan: %d checkpoints, %d total actions from %s",
        len(checkpoints), len(all_actions), path,
    )

    return GeneratedPlan(
        metadata=metadata,
        goal=str(raw.get("goal", "")),
        checkpoints=checkpoints,
        constraints=list(raw.get("constraints", [])),
        execution_summary=dict(raw.get("execution_summary", {})),
        all_actions=all_actions,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Convenience: load everything in one call
# ---------------------------------------------------------------------------

def load_all(
    robot_path: Union[str, Path],
    world_path: Union[str, Path],
    ontology_path: Union[str, Path],
    plan_path: Union[str, Path],
) -> tuple[RobotCapabilities, WorldState, SkillOntology, GeneratedPlan]:
    """Load all four inputs and return typed objects.

    Args:
        robot_path: Path to robot capabilities JSON.
        world_path: Path to world JSON.
        ontology_path: Path to skill ontology JSON.
        plan_path: Path to generated plan JSON.

    Returns:
        Tuple of ``(robot, world, ontology, plan)``.
    """
    robot = load_robot(robot_path)
    world = load_world(world_path)
    ontology = load_ontology(ontology_path)
    plan = load_plan(plan_path)
    return robot, world, ontology, plan
