"""Build the final locked capability JSON document."""

from __future__ import annotations

from typing import Any, Dict, List

from . import __version__
from .models.capability_model import CapabilityState, RuleTrace
from .models.robot_structure import RobotStructure
from .models.rule_models import RuleSet
from .utils import stable_dict
from .validators import validate_capability_document


class CapabilityBuilder:
    """Create the final dissertation capability representation."""

    LOCOMOTION_KEYS = [
        "can_move",
        "can_rotate",
        "can_strafe",
        "can_navigate",
        "can_fly",
        "can_hover",
        "can_walk",
        "can_run",
        "can_climb",
        "can_swim",
        "can_crawl",
        "can_hop",
    ]
    MANIPULATION_KEYS = [
        "can_manipulate",
        "can_grasp",
        "can_pick",
        "can_place",
        "can_push",
        "can_pull",
        "can_hold",
        "can_carry",
        "can_transport",
        "can_assemble",
        "can_disassemble",
        "can_screw",
        "can_drill",
        "can_weld",
        "can_cut",
        "can_paint",
        "can_spray",
        "can_use_two_hands",
        "can_collaborative_manipulate",
        "can_dexterous_manipulate",
        "can_exchange_tools",
    ]
    PERCEPTION_KEYS = [
        "has_visual_perception",
        "has_depth_perception",
        "has_audio_input",
        "has_force_feedback",
        "has_touch_sensing",
        "environmental_sensing",
        "can_detect_objects",
        "can_detect_humans",
        "can_detect_obstacles",
        "can_estimate_range",
        "supports_slam",
        "supports_localization",
        "supports_state_estimation",
        "supports_map_building",
        "supports_obstacle_avoidance",
    ]
    QUANTITATIVE_KEYS = [
        "link_count",
        "number_of_links",
        "joint_count",
        "number_of_joints",
        "degrees_of_freedom",
        "manipulator_count",
        "arm_count",
        "leg_count",
        "wheel_count",
        "track_count",
        "sensor_count",
        "camera_count",
        "lidar_count",
        "propeller_count",
        "thruster_count",
        "manipulator_reach",
        "arm_length",
        "payload",
        "maximum_speed",
        "turning_radius",
        "battery_capacity",
        "wheel_diameter",
        "track_width",
        "weight",
        "height",
        "width",
        "length",
        "joint_limits",
        "velocity_limits",
        "effort_limits",
    ]

    def build(self, robot: RobotStructure, rules: RuleSet, state: CapabilityState) -> Dict[str, Any]:
        data = state.data
        document = {
            "Robot": {
                "Metadata": self._metadata(robot, rules),
                "Morphology": self._morphology(robot, data),
                "Locomotion": self._locomotion(data),
                "Manipulation": self._manipulation(data),
                "Perception": self._perception(data),
                "Capabilities": self._capabilities(data, state),
                "Constraints": self._constraints(data, state),
            }
        }
        validate_capability_document(document)
        return document

    def _metadata(self, robot: RobotStructure, rules: RuleSet) -> Dict[str, Any]:
        return {
            "robot_name": robot.name,
            "source_urdf": str(robot.source_path),
            "extractor_version": __version__,
            "rules_version": rules.version,
            "deterministic": True,
            "parser": robot.metadata.get("parser", "unknown"),
            "urdfpy": robot.urdfpy_summary,
            "structural_counts": {
                "links": len(robot.links),
                "joints": len(robot.joints),
                "sensors": len(robot.sensors),
                "actuators": len(robot.actuators),
                "controllers": len(robot.controllers),
                "transmissions": len(robot.transmissions),
                "plugins": len(robot.plugins),
            },
        }

    def _morphology(self, robot: RobotStructure, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "robot_types": data.get("robot_types", ["unknown"]),
            "primary_morphology": data.get("morphology", "unknown"),
            "supported_environments": data.get("supported_environments", []),
            "candidate_environments": data.get("supported_environments_candidate", []),
            "kinematic_chains": [
                {
                    "root": chain.root,
                    "tip": chain.tip,
                    "links": chain.links,
                    "joints": chain.joints,
                    "length_estimate": chain.length_estimate,
                }
                for chain in robot.kinematic_chains
            ],
            "end_effectors": robot.end_effectors,
            "structure": {
                "root_links": robot.root_links,
                "leaf_links": robot.leaf_links,
                "materials": sorted(robot.materials),
            },
        }

    def _locomotion(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {key: data.get(key, False) for key in self.LOCOMOTION_KEYS}
        payload.update(
            {
                "drive_type": data.get("drive_type", "unknown"),
                "movement_type": data.get("movement_type", []),
                "supported_locomotion": data.get("supported_locomotion", []),
                "navigation": {
                    "supports_autonomous_navigation": data.get("supports_autonomous_navigation", False),
                    "supports_indoor_navigation": data.get("supports_indoor_navigation", False),
                    "supports_outdoor_navigation": data.get("supports_outdoor_navigation", False),
                    "can_follow_waypoints": data.get("can_follow_waypoints", False),
                    "can_follow_path": data.get("can_follow_path", False),
                },
            }
        )
        return payload

    def _manipulation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {key: data.get(key, False) for key in self.MANIPULATION_KEYS}
        payload.update(
            {
                "end_effector_types": data.get("end_effector_types", []),
                "industrial_processes": data.get("industrial_processes", []),
                "object_material_constraints": data.get("object_material_constraints", []),
                "manipulator_count": data.get("manipulator_count", 0),
                "manipulator_count_min": data.get("manipulator_count_min", 0),
                "manipulator_reach": data.get("manipulator_reach", 0),
            }
        )
        return payload

    def _perception(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {key: data.get(key, False) for key in self.PERCEPTION_KEYS}
        payload.update(
            {
                "perception_modalities": data.get("perception_modalities", []),
                "inspection_types": data.get("inspection_types", []),
                "communication_modes": data.get("communication_modes", []),
                "supports_voice_interaction": data.get("supports_voice_interaction", False),
                "supports_speech_output": data.get("supports_speech_output", False),
                "supports_remote_operation": data.get("supports_remote_operation", False),
                "supports_human_robot_communication": data.get("supports_human_robot_communication", False),
            }
        )
        return payload

    def _capabilities(self, data: Dict[str, Any], state: CapabilityState) -> Dict[str, Any]:
        binary = {
            key: value
            for key, value in sorted(data.items())
            if isinstance(value, bool) and not key.startswith("cannot_")
        }
        quantitative = {
            key: data[key]
            for key in self.QUANTITATIVE_KEYS
            if key in data
        }
        qualitative = {
            key: value
            for key, value in sorted(data.items())
            if not isinstance(value, bool)
            and key not in quantitative
            and not key.startswith("cannot_")
        }
        return {
            "BinaryCapabilities": binary,
            "QuantitativeCapabilities": quantitative,
            "QualitativeCapabilities": qualitative,
            "DerivedCapabilities": data.get("high_level_capabilities", []),
            "Autonomy": {
                "autonomy_modes": data.get("autonomy_modes", []),
                "fleet_capable": data.get("fleet_capable", False),
                "can_execute_mission": data.get("can_execute_mission", False),
            },
            "Power": {
                "power_source": data.get("power_source", "unknown"),
                "power_source_candidate": data.get("power_source_candidate", "unknown"),
                "battery_powered": data.get("battery_powered", False),
                "rechargeable": data.get("rechargeable", False),
                "docking_capable": data.get("docking_capable", False),
                "tethered_candidate": data.get("tethered_candidate", False),
            },
            "Evidence": stable_dict(state.evidence),
            "RuleTrace": [self._trace_to_dict(trace) for trace in state.traces],
        }

    def _constraints(self, data: Dict[str, Any], state: CapabilityState) -> Dict[str, Any]:
        flags = {
            key: value
            for key, value in sorted(data.items())
            if isinstance(value, bool) and (key.startswith("cannot_") or key.startswith("no_") or key.startswith("limited_") or key in {"fixed_base", "single_arm_only"})
        }
        return {
            "ActiveConstraints": state.constraints,
            "ConstraintFlags": flags,
        }

    def _trace_to_dict(self, trace: RuleTrace) -> Dict[str, Any]:
        return {
            "rule_id": trace.rule_id,
            "group": trace.group,
            "matched": trace.matched,
            "priority": trace.priority,
            "confidence": trace.confidence,
            "evidence": trace.evidence,
            "rejected_conditions": trace.rejected_conditions,
            "outputs": trace.outputs,
        }
