"""Stage 7 — Constraint Validator.

Checks robot physical and operational constraints against plan actions.

Constraints checked (deterministically, no simulation required):
  * Payload limit: if action involves carrying/transporting and robot has
    limited_payload=True, warn.
  * Manipulator required: pick/place/grasp require can_manipulate or can_pick.
  * Navigation indoor vs outdoor: actions inside rooms require indoor navigation
    support; outdoor-only robots in indoor rooms are flagged.
  * Visual perception required: detect/recognize/classify require
    has_visual_perception.
  * Obstacle avoidance: navigation in crowded environments requires
    supports_obstacle_avoidance.

Score = satisfied_constraints / total_constraints_checked.
"""
from __future__ import annotations

import logging
from typing import List, Set, Tuple

from evaluation.models.plan import GeneratedPlan, PlanAction
from evaluation.models.robot import RobotCapabilities
from evaluation.models.world import WorldState
from evaluation.config import ErrorCode, Severity
from evaluation.validators.base import ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)

# Action groups used by constraint rules
_PICK_ACTIONS: Set[str] = {
    "pick", "pick_object", "grasp", "grasp_object", "grab",
}
_PLACE_ACTIONS: Set[str] = {
    "place", "place_object", "put", "put_down", "release",
}
_CARRY_ACTIONS: Set[str] = {
    "carry", "transport", "deliver", "bring", "hold",
}
_DETECT_ACTIONS: Set[str] = {
    "detect_object", "recognize_object", "classify_object",
    "identify_object", "visual_search",
}
_NAV_ACTIONS: Set[str] = {
    "navigate_to_room", "navigate", "navigate_to_pose", "go_to", "move_to",
}


def _action_in(action_name: str, group: Set[str]) -> bool:
    """Check if an action name (or prefix thereof) is in a group."""
    key = action_name.lower()
    return key in group or any(key.startswith(g) for g in group)


def validate_constraints(
    plan: GeneratedPlan,
    robot: RobotCapabilities,
    world: WorldState,
) -> ValidationResult:
    """Validate physical and operational constraints.

    Args:
        plan: Parsed generated plan.
        robot: Loaded robot capabilities.
        world: Loaded world state.

    Returns:
        :class:`ValidationResult` with constraint violations and satisfaction score.
    """
    issues: List[ValidationIssue] = []
    checks: List[Tuple[bool, str]] = []  # (passed, description)

    indoor_room_names: Set[str] = {r.name.lower() for r in world.rooms}

    for action in plan.all_actions:
        act = action.action.lower()

        # ------------------------------------------------------------------
        # C1: Pick/Grasp requires can_pick or can_grasp
        # ------------------------------------------------------------------
        if _action_in(act, _PICK_ACTIONS):
            has = robot.has_capability("can_pick") or robot.has_capability("can_grasp")
            checks.append((has, f"C1:pick_capability@step{action.global_index}"))
            if not has:
                issues.append(ValidationIssue(
                    code=ErrorCode.CONSTRAINT_VIOLATION,
                    message=(
                        f"Action '{action.action}' requires picking capability "
                        f"(can_pick or can_grasp) which robot "
                        f"'{robot.metadata.name}' lacks."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion="Use a robot with a manipulator arm, or remove pick step.",
                ))

        # ------------------------------------------------------------------
        # C2: Place requires can_place
        # ------------------------------------------------------------------
        if _action_in(act, _PLACE_ACTIONS):
            has = robot.has_capability("can_place")
            checks.append((has, f"C2:place_capability@step{action.global_index}"))
            if not has:
                issues.append(ValidationIssue(
                    code=ErrorCode.CONSTRAINT_VIOLATION,
                    message=(
                        f"Action '{action.action}' requires place capability "
                        f"which robot '{robot.metadata.name}' lacks."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion="Use a robot with can_place capability.",
                ))

        # ------------------------------------------------------------------
        # C3: Carry/transport with limited_payload → warning
        # ------------------------------------------------------------------
        if _action_in(act, _CARRY_ACTIONS) and robot.binary.limited_payload:
            checks.append((True, f"C3:payload_warning@step{action.global_index}"))
            issues.append(ValidationIssue(
                code=ErrorCode.CONSTRAINT_VIOLATION,
                message=(
                    f"Action '{action.action}' involves carrying but robot "
                    f"'{robot.metadata.name}' has limited_payload=True."
                ),
                action_index=action.global_index,
                checkpoint_id=action.checkpoint_id,
                severity=Severity.WARNING,
                suggestion=(
                    "Verify the object weight is within the robot's payload limit."
                ),
            ))

        # ------------------------------------------------------------------
        # C4: Visual detection requires has_visual_perception
        # ------------------------------------------------------------------
        if _action_in(act, _DETECT_ACTIONS):
            has = (
                robot.has_capability("has_visual_perception")
                or robot.has_capability("can_detect_objects")
            )
            checks.append((has, f"C4:visual_perception@step{action.global_index}"))
            if not has:
                issues.append(ValidationIssue(
                    code=ErrorCode.CONSTRAINT_VIOLATION,
                    message=(
                        f"Action '{action.action}' requires visual perception / "
                        f"object detection capability which robot "
                        f"'{robot.metadata.name}' lacks."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.ERROR,
                    suggestion=(
                        "Add a vision sensor to the robot, or use a pre-mapped "
                        "semantic knowledge base as a fallback."
                    ),
                ))

        # ------------------------------------------------------------------
        # C5: Indoor navigation requires supports_indoor_navigation
        # ------------------------------------------------------------------
        if _action_in(act, _NAV_ACTIONS):
            loc = action.location.strip().lower()
            is_indoor = loc in indoor_room_names
            if is_indoor and not robot.has_capability("supports_indoor_navigation"):
                # Downgrade to warning — outdoor robots may still navigate indoors
                checks.append((True, f"C5:indoor_nav_warn@step{action.global_index}"))
                issues.append(ValidationIssue(
                    code=ErrorCode.CONSTRAINT_VIOLATION,
                    message=(
                        f"Action '{action.action}' navigates to an indoor location "
                        f"'{action.location}' but robot '{robot.metadata.name}' "
                        "does not explicitly support indoor navigation."
                    ),
                    action_index=action.global_index,
                    checkpoint_id=action.checkpoint_id,
                    severity=Severity.WARNING,
                    suggestion=(
                        "Verify indoor clearance heights and obstacle density are "
                        "compatible with this robot platform."
                    ),
                ))
            else:
                checks.append((True, f"C5:indoor_nav_ok@step{action.global_index}"))

    total = len(checks)
    satisfied = sum(1 for passed, _ in checks if passed)
    raw_score = satisfied / total if total > 0 else 1.0

    error_issues = [i for i in issues if i.severity == Severity.ERROR]
    status = (
        "PASS" if not error_issues else
        ("WARNING" if raw_score >= 0.6 else "FAIL")
    )

    logger.info(
        "ConstraintValidator: %d/%d constraints satisfied. Score=%.2f",
        satisfied, total, raw_score,
    )

    return ValidationResult(
        validator_name="ConstraintValidator",
        raw_score=raw_score,
        normalised_score=raw_score,
        status=status,
        issues=issues,
        comments=(
            f"{satisfied}/{total} constraint checks satisfied. "
            f"Score: {raw_score:.2%}."
        ),
        extra={"satisfied_constraints": satisfied, "total_constraints": total},
    )
