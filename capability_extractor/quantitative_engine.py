"""Quantitative capability extraction stage."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Set

from .models.capability_model import CapabilityState
from .models.robot_structure import GeometryInfo, RobotStructure
from .models.rule_models import RuleSet
from .semantic_engine import CapabilityRuleEvaluator, RuleEvaluationContext
from .utils import normalize_text


class QuantitativeCapabilityEngine:
    """Extract numerical capability facts without assigning robot semantics."""

    def __init__(
        self,
        evaluator: CapabilityRuleEvaluator,
        logger: logging.Logger | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.logger = logger or logging.getLogger(__name__)

    def run(self, robot: RobotStructure, rules: RuleSet, state: CapabilityState) -> CapabilityState:
        context = RuleEvaluationContext(robot, rules, state)
        metrics = self._extract_metrics(robot, rules, context)
        for key, value in metrics.items():
            state.set_metric(key, value)

        for rule in rules.iter_rules(["quantitative_rules"]):
            result = self.evaluator.evaluate(rule, robot, rules, state)
            state.record_trace(result)
            if result.matched:
                self._attach_quantitative_rule_evidence(state, rule.id, result.outputs)
        self.logger.info("Extracted %s quantitative capability fields", len(metrics))
        return state

    def _extract_metrics(
        self,
        robot: RobotStructure,
        rules: RuleSet,
        context: RuleEvaluationContext,
    ) -> Dict[str, Any]:
        joint_count = len(robot.joints)
        link_count = len(robot.links)
        degrees_of_freedom = sum(self._joint_dof(joint.joint_type) for joint in robot.joints.values())
        camera_count = self._union_keyword_count(
            context,
            "sensor_keywords",
            "sensor",
            ["rgb_camera", "stereo_camera", "depth_camera", "rgbd_camera", "thermal_camera", "event_camera"],
        )
        lidar_count = self._union_keyword_count(context, "sensor_keywords", "sensor", ["lidar"])
        wheel_matches = self._keyword_matches(context, "link_keywords", "wheel", "link")
        track_matches = self._keyword_matches(context, "link_keywords", "track", "link")
        leg_matches = self._keyword_matches(context, "link_keywords", "leg", "link")
        propeller_matches = self._keyword_matches(context, "link_keywords", "propeller", "link")
        thruster_matches = self._keyword_matches(context, "link_keywords", "thruster", "link")
        sensor_count = max(
            len(robot.sensors),
            self._union_keyword_count(context, "sensor_keywords", "sensor", list(rules.vocabularies.get("sensor_keywords", {}))),
        )

        dimensions = robot.derived_statistics.get("estimated_dimensions", {})
        manipulator_reach = self._estimate_manipulator_reach(robot, rules)
        payload = self._estimate_payload(robot, context)
        wheel_diameter = self._estimate_component_diameter(robot, wheel_matches)
        track_width = self._estimate_track_width(robot, track_matches or wheel_matches)

        velocity_limits = {
            name: joint.limit.get("velocity")
            for name, joint in sorted(robot.joints.items())
            if "velocity" in joint.limit
        }
        effort_limits = {
            name: joint.limit.get("effort")
            for name, joint in sorted(robot.joints.items())
            if "effort" in joint.limit
        }

        return {
            "link_count": link_count,
            "number_of_links": link_count,
            "joint_count": joint_count,
            "number_of_joints": joint_count,
            "degrees_of_freedom": degrees_of_freedom,
            "manipulator_count": self._estimate_manipulator_count(robot, rules),
            "arm_count": self._estimate_manipulator_count(robot, rules),
            "leg_count": len(leg_matches),
            "wheel_count": len(wheel_matches),
            "track_count": len(track_matches),
            "sensor_count": sensor_count,
            "camera_count": camera_count,
            "lidar_count": lidar_count,
            "propeller_count": len(propeller_matches),
            "thruster_count": len(thruster_matches),
            "manipulator_reach": manipulator_reach,
            "arm_length": manipulator_reach,
            "payload": payload,
            "wheel_diameter": wheel_diameter,
            "track_width": track_width,
            "weight": round(float(robot.derived_statistics.get("total_mass", 0.0)), 6),
            "height": float(dimensions.get("height", 0.0)),
            "width": float(dimensions.get("width", 0.0)),
            "length": float(dimensions.get("length", 0.0)),
            "maximum_speed": self._estimate_maximum_speed(robot, wheel_diameter),
            "turning_radius": 0,
            "battery_capacity": 0,
            "joint_limits": robot.joint_limits,
            "velocity_limits": velocity_limits,
            "effort_limits": effort_limits,
        }

    def _attach_quantitative_rule_evidence(
        self, state: CapabilityState, rule_id: str, outputs: Dict[str, Any]
    ) -> None:
        metric = outputs.get("metric")
        metrics = outputs.get("metrics", [])
        for name in ([metric] if metric else []) + list(metrics):
            if name in state.data:
                state.evidence.setdefault(name, []).append(
                    {"rule_id": rule_id, "group": "quantitative_rules", "value": state.data[name]}
                )

    def _joint_dof(self, joint_type: str) -> int:
        return {
            "fixed": 0,
            "revolute": 1,
            "continuous": 1,
            "prismatic": 1,
            "planar": 3,
            "floating": 6,
        }.get(joint_type, 0)

    def _keyword_matches(
        self, context: RuleEvaluationContext, vocabulary: str, category: str, domain: str
    ) -> Set[str]:
        _, matches = context.count_keyword(vocabulary, category, domain)
        return set(matches)

    def _union_keyword_count(
        self,
        context: RuleEvaluationContext,
        vocabulary: str,
        domain: str,
        categories: Iterable[str],
    ) -> int:
        matches: Set[str] = set()
        for category in categories:
            _, found = context.count_keyword(vocabulary, str(category), domain)
            matches.update(found)
        return len(matches)

    def _estimate_manipulator_count(self, robot: RobotStructure, rules: RuleSet) -> int:
        arm_vocab = rules.vocabularies.get("link_keywords", {}).get("arm", ["arm"])
        normalized = [normalize_text(value) for value in arm_vocab]
        roots = set()
        for chain in robot.kinematic_chains:
            chain_text = " ".join(chain.links)
            if any(token in normalize_text(chain_text) for token in normalized):
                roots.add(chain.links[1] if len(chain.links) > 1 else chain.tip)
        if roots:
            return len(roots)
        return 1 if any(token in normalize_text(" ".join(robot.link_names)) for token in normalized) else 0

    def _estimate_manipulator_reach(self, robot: RobotStructure, rules: RuleSet) -> float:
        arm_vocab = rules.vocabularies.get("link_keywords", {}).get("arm", ["arm"])
        ee_vocab = rules.vocabularies.get("link_keywords", {}).get("end_effector", ["end_effector"])
        tokens = [normalize_text(value) for value in arm_vocab + ee_vocab]
        reach = 0.0
        for chain in robot.kinematic_chains:
            text = normalize_text(" ".join(chain.links + chain.joints))
            if any(token in text for token in tokens):
                reach = max(reach, chain.length_estimate)
        return round(reach, 6)

    def _estimate_payload(self, robot: RobotStructure, context: RuleEvaluationContext) -> float:
        _, payload_links = context.count_keyword("link_keywords", "payload", "link")
        payload_names = {normalize_text(name) for name in payload_links}
        payload_mass = 0.0
        for name, inertial in robot.inertials.items():
            if normalize_text(name) in payload_names:
                payload_mass += inertial.mass
        return round(payload_mass, 6)

    def _estimate_component_diameter(
        self, robot: RobotStructure, component_names: Iterable[str]
    ) -> float:
        normalized_components = {normalize_text(name) for name in component_names}
        diameter = 0.0
        for name, link in robot.links.items():
            if normalize_text(name) not in normalized_components:
                continue
            for geometry in link.visuals + link.collisions:
                diameter = max(diameter, self._diameter_from_geometry(geometry))
        return round(diameter, 6)

    def _diameter_from_geometry(self, geometry: GeometryInfo) -> float:
        if geometry.kind in {"cylinder", "sphere"}:
            return 2.0 * float(geometry.data.get("radius", 0.0))
        if geometry.kind == "box":
            size = geometry.data.get("size") or [0.0, 0.0, 0.0]
            return max(float(value) for value in size) if size else 0.0
        return 0.0

    def _estimate_track_width(
        self, robot: RobotStructure, component_names: Iterable[str]
    ) -> float:
        component_text = {normalize_text(name) for name in component_names}
        lateral_offsets: List[float] = []
        for joint in robot.joints.values():
            text = normalize_text(f"{joint.name} {joint.child or ''}")
            if any(name in text or text in name for name in component_text):
                xyz = joint.origin.get("xyz", [0.0, 0.0, 0.0])
                if len(xyz) > 1:
                    lateral_offsets.append(float(xyz[1]))
        if not lateral_offsets:
            return 0.0
        return round(max(lateral_offsets) - min(lateral_offsets), 6)

    def _estimate_maximum_speed(self, robot: RobotStructure, wheel_diameter: float) -> float:
        if wheel_diameter <= 0:
            return 0.0
        max_joint_velocity = 0.0
        for joint in robot.joints.values():
            velocity = joint.limit.get("velocity")
            if isinstance(velocity, (int, float)):
                max_joint_velocity = max(max_joint_velocity, float(velocity))
        return round((wheel_diameter / 2.0) * max_joint_velocity, 6)
