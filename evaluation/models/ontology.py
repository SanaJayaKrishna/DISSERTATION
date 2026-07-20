"""Internal data models for the robot skill ontology."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillImplementation:
    """One concrete ROS 2 / library grounding for an abstract skill.

    Attributes:
        framework: Framework name (e.g. ``Nav2``).
        ros2_interface_type: ``Action`` | ``Service`` | ``Topic``.
        interface_name: ROS 2 interface path (e.g. ``/navigate_to_pose``).
        message_type: Full message type string.
    """
    framework: str
    ros2_interface_type: str
    interface_name: str
    message_type: str


@dataclass
class Skill:
    """One entry from the robot skill ontology.

    Attributes:
        skill_id: Unique identifier such as ``NAV_001``.
        abstract_skill: Canonical skill name (e.g. ``navigate_to_pose``).
        category: High-level family (e.g. ``Navigation``).
        description: Human-readable purpose.
        goal: Planner-level intent.
        aliases: Natural-language phrases that should resolve to this skill.
        required_capabilities: Capability keys that a robot must possess.
        required_components: Physical / software components required.
        preconditions: Conditions that must hold before execution.
        postconditions: Expected world state after success.
        failure_conditions: Common failure causes.
        implementations: Known ROS 2 groundings.
    """
    skill_id: str
    abstract_skill: str
    category: str
    description: str = ""
    goal: str = ""
    aliases: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    required_components: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    failure_conditions: List[str] = field(default_factory=list)
    implementations: List[SkillImplementation] = field(default_factory=list)


@dataclass
class SkillOntology:
    """Complete skill ontology with fast lookup helpers.

    Attributes:
        version: Ontology version string.
        skills: Ordered list of all skills.
        _by_name: Internal index keyed by ``abstract_skill`` (lowercase).
        _by_alias: Internal index from any alias (lowercase) to a skill.
    """
    version: str
    skills: List[Skill]
    _by_name: Dict[str, Skill] = field(default_factory=dict, init=False, repr=False)
    _by_alias: Dict[str, Skill] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Build internal indices after construction."""
        for skill in self.skills:
            self._by_name[skill.abstract_skill.lower()] = skill
            for alias in skill.aliases:
                self._by_alias[alias.strip().lower()] = skill

    def find_skill(self, action_name: str) -> Optional[Skill]:
        """Resolve an action name to exactly one skill.

        Resolution order:
        1. Exact match on ``abstract_skill`` (case-insensitive).
        2. Match on any ``alias`` (case-insensitive).
        3. Prefix / substring match on ``abstract_skill``.

        Args:
            action_name: Action name from the generated plan.

        Returns:
            Matching :class:`Skill` or ``None`` if not found.
        """
        key = action_name.strip().lower()

        # 1. Exact abstract_skill name
        if key in self._by_name:
            return self._by_name[key]

        # 2. Alias lookup
        if key in self._by_alias:
            return self._by_alias[key]

        # 3. Substring / prefix fallback
        for name, skill in self._by_name.items():
            if key in name or name in key:
                return skill

        return None

    def has_skill(self, action_name: str) -> bool:
        """Return ``True`` if the action can be resolved to a skill.

        Args:
            action_name: Action name from the generated plan.

        Returns:
            Boolean membership result.
        """
        return self.find_skill(action_name) is not None
