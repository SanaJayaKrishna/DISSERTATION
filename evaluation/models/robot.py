"""Internal data models for robot capabilities."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RobotMetadata:
    """Basic identification fields for a robot.

    Attributes:
        name: Canonical robot name (e.g. ``aliengo``).
        robot_type: General classification (e.g. ``quadruped``).
        manufacturer: OEM name.
        description: Free-text human-readable description.
    """
    name: str
    robot_type: str = ""
    manufacturer: str = ""
    description: str = ""


@dataclass
class BinaryCapabilities:
    """Boolean capability flags extracted from ``BinaryCapabilities`` block.

    Each attribute maps 1-to-1 to a key in the robot JSON's
    ``Robot.Capabilities.BinaryCapabilities`` object.  Any key present in
    the JSON that is not listed here is stored in ``extra``.
    """
    can_navigate: bool = False
    can_move: bool = False
    can_walk: bool = False
    can_fly: bool = False
    can_pick: bool = False
    can_place: bool = False
    can_carry: bool = False
    can_grasp: bool = False
    can_hold: bool = False
    can_manipulate: bool = False
    can_dexterous_manipulate: bool = False
    can_collaborative_manipulate: bool = False
    can_climb: bool = False
    can_crawl: bool = False
    can_hover: bool = False
    can_run: bool = False
    can_swim: bool = False
    can_strafe: bool = False
    can_rotate: bool = False
    can_hop: bool = False
    can_inspect: bool = False
    can_detect_objects: bool = False
    can_detect_humans: bool = False
    can_detect_obstacles: bool = False
    can_follow_path: bool = False
    can_follow_waypoints: bool = False
    can_follow_person: bool = False
    can_open_door: bool = False
    can_open_drawer: bool = False
    can_press_button: bool = False
    can_pull: bool = False
    can_push: bool = False
    can_spray: bool = False
    can_screw: bool = False
    can_weld: bool = False
    can_drill: bool = False
    can_cut: bool = False
    can_paint: bool = False
    can_transport: bool = False
    can_assemble: bool = False
    can_disassemble: bool = False
    can_exchange_tools: bool = False
    can_use_two_hands: bool = False
    can_use_elevator: bool = False
    can_handover: bool = False
    can_contact_interact: bool = False
    can_estimate_range: bool = False
    can_thermal_inspect: bool = False
    can_monitor_equipment: bool = False
    can_execute_mission: bool = False
    has_visual_perception: bool = False
    has_depth_perception: bool = False
    has_force_feedback: bool = False
    has_touch_sensing: bool = False
    has_audio_input: bool = False
    environmental_sensing: bool = False
    human_robot_interaction: bool = False
    human_safe_interaction_support: bool = False
    supports_localization: bool = False
    supports_obstacle_avoidance: bool = False
    supports_autonomous_navigation: bool = False
    supports_indoor_navigation: bool = False
    supports_outdoor_navigation: bool = False
    supports_slam: bool = False
    supports_map_building: bool = False
    supports_remote_operation: bool = False
    supports_fleet_communication: bool = False
    supports_human_robot_communication: bool = False
    supports_voice_interaction: bool = False
    supports_speech_output: bool = False
    supports_state_estimation: bool = False
    docking_capable: bool = False
    fleet_capable: bool = False
    battery_powered: bool = False
    rechargeable: bool = False
    limited_payload: bool = False
    no_visual_perception: bool = False
    no_depth_perception: bool = False
    no_audio: bool = False
    tethered_candidate: bool = False

    # Catch-all for non-standard fields in the JSON
    extra: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: bool = False) -> bool:
        """Return capability value by string key, falling back to ``extra``."""
        if hasattr(self, key):
            return bool(getattr(self, key))
        return bool(self.extra.get(key, default))


@dataclass
class RobotCapabilities:
    """Aggregated capabilities for a robot.

    Attributes:
        metadata: Identification block.
        binary: Boolean capability flags.
        derived: Derived capability labels (e.g. ``remote_operation``).
        raw: Original parsed JSON for advanced validators that need deep access.
    """
    metadata: RobotMetadata
    binary: BinaryCapabilities
    derived: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def has_capability(self, key: str) -> bool:
        """Convenience method used by validators.

        Checks ``binary`` attributes first, then ``derived`` list, then
        ``binary.extra`` dict.

        Args:
            key: Capability key (e.g. ``can_navigate``).

        Returns:
            ``True`` if the robot has this capability.
        """
        if hasattr(self.binary, key):
            return bool(getattr(self.binary, key))
        if key in self.derived:
            return True
        return bool(self.binary.extra.get(key, False))
