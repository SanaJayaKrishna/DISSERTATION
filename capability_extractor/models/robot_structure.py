"""Structural URDF data models.

These models intentionally avoid semantic robot interpretation. They store the
facts found in the URDF and lightweight derived graph/statistical facts that
are independent of robot category.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


JSONDict = Dict[str, Any]


@dataclass(frozen=True)
class GeometryInfo:
    """Geometry extracted from visual or collision elements."""

    kind: str
    data: JSONDict = field(default_factory=dict)
    origin: JSONDict = field(default_factory=dict)
    material: Optional[str] = None


@dataclass(frozen=True)
class InertialInfo:
    """Mass and inertia for a link."""

    mass: float = 0.0
    inertia: JSONDict = field(default_factory=dict)
    origin: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class LinkInfo:
    """URDF link information."""

    name: str
    visuals: List[GeometryInfo] = field(default_factory=list)
    collisions: List[GeometryInfo] = field(default_factory=list)
    inertial: Optional[InertialInfo] = None
    materials: List[str] = field(default_factory=list)
    raw_attributes: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class JointInfo:
    """URDF joint information."""

    name: str
    joint_type: str
    parent: Optional[str]
    child: Optional[str]
    origin: JSONDict = field(default_factory=dict)
    axis: List[float] = field(default_factory=list)
    limit: JSONDict = field(default_factory=dict)
    dynamics: JSONDict = field(default_factory=dict)
    safety: JSONDict = field(default_factory=dict)
    calibration: JSONDict = field(default_factory=dict)
    mimic: JSONDict = field(default_factory=dict)
    raw_attributes: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class TransmissionInfo:
    """URDF transmission information."""

    name: str
    transmission_type: str
    joints: List[str] = field(default_factory=list)
    actuators: List[str] = field(default_factory=list)
    data: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class SensorInfo:
    """Sensor-like XML elements and plugins."""

    name: str
    sensor_type: str
    parent: Optional[str] = None
    source: str = "urdf"
    data: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class ActuatorInfo:
    """Actuator extracted from transmission or plugin data."""

    name: str
    actuator_type: str = "unknown"
    joint: Optional[str] = None
    data: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class ControllerInfo:
    """Controller or control plugin reference."""

    name: str
    controller_type: str = "unknown"
    source: str = "plugin"
    data: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class PluginInfo:
    """Gazebo or URDF plugin data."""

    name: str
    filename: Optional[str] = None
    parent: Optional[str] = None
    data: JSONDict = field(default_factory=dict)


@dataclass(frozen=True)
class KinematicChain:
    """Root-to-leaf kinematic chain."""

    root: str
    tip: str
    links: List[str]
    joints: List[str]
    length_estimate: float = 0.0


@dataclass
class RobotStructure:
    """Complete structural representation consumed by later stages."""

    metadata: JSONDict
    links: Dict[str, LinkInfo]
    joints: Dict[str, JointInfo]
    joint_limits: Dict[str, JSONDict]
    hierarchy: Dict[str, List[str]]
    child_to_parent: Dict[str, str]
    kinematic_chains: List[KinematicChain]
    sensors: List[SensorInfo]
    actuators: List[ActuatorInfo]
    controllers: List[ControllerInfo]
    transmissions: List[TransmissionInfo]
    end_effectors: List[str]
    plugins: List[PluginInfo]
    geometry: Dict[str, JSONDict]
    inertials: Dict[str, InertialInfo]
    materials: Dict[str, JSONDict]
    derived_statistics: JSONDict
    raw_urdf: str
    source_path: Path
    urdfpy_summary: JSONDict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return str(self.metadata.get("name", "unknown"))

    @property
    def link_names(self) -> List[str]:
        return sorted(self.links)

    @property
    def joint_names(self) -> List[str]:
        return sorted(self.joints)

    @property
    def root_links(self) -> List[str]:
        child_links = {joint.child for joint in self.joints.values() if joint.child}
        roots = sorted(set(self.links) - child_links)
        return roots or self.link_names[:1]

    @property
    def leaf_links(self) -> List[str]:
        parent_links = {joint.parent for joint in self.joints.values() if joint.parent}
        return sorted(set(self.links) - parent_links)

    @property
    def movable_joints(self) -> List[JointInfo]:
        return [
            joint
            for joint in self.joints.values()
            if joint.joint_type not in {"fixed", "unknown"}
        ]

    def all_structural_text(self) -> List[str]:
        """Return stable text tokens useful for generic rule matching."""

        values: List[str] = []
        values.extend(self.link_names)
        values.extend(self.joint_names)
        values.extend(sensor.name for sensor in self.sensors)
        values.extend(sensor.sensor_type for sensor in self.sensors)
        values.extend(actuator.name for actuator in self.actuators)
        values.extend(actuator.actuator_type for actuator in self.actuators)
        values.extend(controller.name for controller in self.controllers)
        values.extend(controller.controller_type for controller in self.controllers)
        values.extend(transmission.name for transmission in self.transmissions)
        values.extend(transmission.transmission_type for transmission in self.transmissions)
        values.extend(plugin.name for plugin in self.plugins)
        values.extend(plugin.filename or "" for plugin in self.plugins)
        values.extend(self.end_effectors)
        return sorted(v for v in values if v)
