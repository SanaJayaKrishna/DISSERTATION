"""Stage 1 structural URDF parser."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from lxml import etree as LET
except Exception:  # pragma: no cover - fallback for minimal environments
    LET = None

from xml.etree import ElementTree as ET

from .models.robot_structure import (
    ActuatorInfo,
    ControllerInfo,
    GeometryInfo,
    InertialInfo,
    JointInfo,
    KinematicChain,
    LinkInfo,
    PluginInfo,
    RobotStructure,
    SensorInfo,
    TransmissionInfo,
)
from .utils import local_name, normalize_text, split_floats
from .validators import URDFValidationError, validate_urdf_path


class StructuralParser:
    """Parse URDF into a RobotStructure without applying semantic rules."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def parse(self, path: Path) -> RobotStructure:
        validate_urdf_path(path)
        raw = path.read_text(encoding="utf-8")
        root = self._parse_xml(raw, path)
        if local_name(root.tag) != "robot":
            raise URDFValidationError(f"URDF root element must be <robot>: {path}")

        urdfpy_summary = self._try_urdfpy(path)
        materials = self._parse_materials(root)
        links = self._parse_links(root)
        joints = self._parse_joints(root)
        transmissions, actuators = self._parse_transmissions(root)
        plugins = self._parse_plugins(root)
        sensors = self._parse_sensors(root, plugins)
        controllers = self._parse_controllers(root, plugins)
        hierarchy, child_to_parent = self._build_hierarchy(joints.values())
        chains = self._build_kinematic_chains(links, joints, hierarchy)
        leaf_links = self._leaf_links(links, joints)
        geometry = {
            name: {
                "visuals": [self._geometry_to_dict(geom) for geom in link.visuals],
                "collisions": [self._geometry_to_dict(geom) for geom in link.collisions],
            }
            for name, link in links.items()
        }
        inertials = {
            name: link.inertial
            for name, link in links.items()
            if link.inertial is not None
        }
        derived_statistics = self._derive_statistics(
            links=links,
            joints=joints,
            chains=chains,
            geometry=geometry,
            inertials=inertials,
            sensors=sensors,
            transmissions=transmissions,
        )

        return RobotStructure(
            metadata={
                "name": root.get("name", "unknown"),
                "source_path": str(path),
                "parser": "urdfpy_optional_lxml_xml",
            },
            links=links,
            joints=joints,
            joint_limits={name: joint.limit for name, joint in joints.items() if joint.limit},
            hierarchy=hierarchy,
            child_to_parent=child_to_parent,
            kinematic_chains=chains,
            sensors=sensors,
            actuators=actuators,
            controllers=controllers,
            transmissions=transmissions,
            end_effectors=leaf_links,
            plugins=plugins,
            geometry=geometry,
            inertials=inertials,
            materials=materials,
            derived_statistics=derived_statistics,
            raw_urdf=raw,
            source_path=path,
            urdfpy_summary=urdfpy_summary,
        )

    def _parse_xml(self, raw: str, path: Path) -> Any:
        try:
            if LET is not None:
                parser = LET.XMLParser(remove_blank_text=False, recover=False)
                return LET.fromstring(raw.encode("utf-8"), parser=parser)
            return ET.fromstring(raw)
        except Exception as exc:
            raise URDFValidationError(f"Invalid URDF XML in {path}: {exc}") from exc

    def _try_urdfpy(self, path: Path) -> Dict[str, Any]:
        try:
            from urdfpy import URDF  # type: ignore

            robot = URDF.load(str(path))
            return {
                "loaded": True,
                "link_count": len(robot.links),
                "joint_count": len(robot.joints),
                "actuated_joint_count": len(getattr(robot, "actuated_joints", [])),
            }
        except Exception as exc:
            self.logger.debug("urdfpy load skipped for %s: %s", path, exc)
            return {"loaded": False, "reason": str(exc)}

    def _parse_materials(self, root: Any) -> Dict[str, Dict[str, Any]]:
        materials: Dict[str, Dict[str, Any]] = {}
        for element in self._children(root, "material"):
            name = element.get("name")
            if not name:
                continue
            data: Dict[str, Any] = {"name": name}
            color = self._first_child(element, "color")
            texture = self._first_child(element, "texture")
            if color is not None:
                data["color"] = color.get("rgba", "")
            if texture is not None:
                data["texture"] = texture.get("filename", "")
            materials[name] = data
        return materials

    def _parse_links(self, root: Any) -> Dict[str, LinkInfo]:
        links: Dict[str, LinkInfo] = {}
        for element in self._children(root, "link"):
            name = element.get("name", "")
            visuals = [self._parse_geometry_container(child) for child in self._children(element, "visual")]
            collisions = [
                self._parse_geometry_container(child)
                for child in self._children(element, "collision")
            ]
            inertial = self._parse_inertial(self._first_child(element, "inertial"))
            materials = [
                material
                for material in (
                    self._material_name(child)
                    for child in self._children(element, "visual")
                )
                if material
            ]
            links[name] = LinkInfo(
                name=name,
                visuals=[geom for geom in visuals if geom is not None],
                collisions=[geom for geom in collisions if geom is not None],
                inertial=inertial,
                materials=materials,
                raw_attributes=dict(element.attrib),
            )
        return links

    def _parse_joints(self, root: Any) -> Dict[str, JointInfo]:
        joints: Dict[str, JointInfo] = {}
        for element in self._children(root, "joint"):
            name = element.get("name", "")
            parent = self._link_ref(element, "parent")
            child = self._link_ref(element, "child")
            limit = self._attributes_as_numbers(self._first_child(element, "limit"))
            dynamics = self._attributes_as_numbers(self._first_child(element, "dynamics"))
            safety = self._attributes_as_numbers(self._first_child(element, "safety_controller"))
            calibration = self._attributes_as_numbers(self._first_child(element, "calibration"))
            mimic = self._attributes_as_numbers(self._first_child(element, "mimic"))
            joints[name] = JointInfo(
                name=name,
                joint_type=element.get("type", "unknown"),
                parent=parent,
                child=child,
                origin=self._parse_origin(self._first_child(element, "origin")),
                axis=split_floats(self._first_child(element, "axis").get("xyz"))
                if self._first_child(element, "axis") is not None
                else [],
                limit=limit,
                dynamics=dynamics,
                safety=safety,
                calibration=calibration,
                mimic=mimic,
                raw_attributes=dict(element.attrib),
            )
        return joints

    def _parse_transmissions(
        self, root: Any
    ) -> Tuple[List[TransmissionInfo], List[ActuatorInfo]]:
        transmissions: List[TransmissionInfo] = []
        actuators: List[ActuatorInfo] = []
        for element in self._iter_named(root, "transmission"):
            name = element.get("name", "unnamed_transmission")
            type_element = self._first_child(element, "type")
            joint_names = [
                child.get("name", "")
                for child in self._children(element, "joint")
                if child.get("name")
            ]
            actuator_names = [
                child.get("name", "")
                for child in self._children(element, "actuator")
                if child.get("name")
            ]
            data = self._element_data(element)
            transmissions.append(
                TransmissionInfo(
                    name=name,
                    transmission_type=(type_element.text or "").strip()
                    if type_element is not None and type_element.text
                    else "unknown",
                    joints=joint_names,
                    actuators=actuator_names,
                    data=data,
                )
            )
            for actuator_name in actuator_names:
                actuators.append(
                    ActuatorInfo(
                        name=actuator_name,
                        actuator_type="transmission_actuator",
                        joint=joint_names[0] if joint_names else None,
                        data=data,
                    )
                )
        return transmissions, actuators

    def _parse_plugins(self, root: Any) -> List[PluginInfo]:
        plugins: List[PluginInfo] = []
        for element in self._iter_named(root, "plugin"):
            plugins.append(
                PluginInfo(
                    name=element.get("name", "unnamed_plugin"),
                    filename=element.get("filename"),
                    parent=self._parent_name(element),
                    data=self._element_data(element),
                )
            )
        return plugins

    def _parse_sensors(self, root: Any, plugins: List[PluginInfo]) -> List[SensorInfo]:
        sensors: List[SensorInfo] = []
        for element in self._iter_named(root, "sensor"):
            sensors.append(
                SensorInfo(
                    name=element.get("name", element.get("type", "unnamed_sensor")),
                    sensor_type=element.get("type", "unknown"),
                    parent=self._parent_name(element),
                    source="sensor_element",
                    data=self._element_data(element),
                )
            )
        for plugin in plugins:
            text = normalize_text(f"{plugin.name} {plugin.filename or ''}")
            if any(token in text for token in ("sensor", "camera", "laser", "lidar", "imu", "gps")):
                sensors.append(
                    SensorInfo(
                        name=plugin.name,
                        sensor_type="plugin_sensor",
                        parent=plugin.parent,
                        source="plugin",
                        data=plugin.data,
                    )
                )
        return sensors

    def _parse_controllers(self, root: Any, plugins: List[PluginInfo]) -> List[ControllerInfo]:
        controllers: List[ControllerInfo] = []
        for element in self._iter_named(root, "controller"):
            controllers.append(
                ControllerInfo(
                    name=element.get("name", "unnamed_controller"),
                    controller_type=element.get("type", "unknown"),
                    source="controller_element",
                    data=self._element_data(element),
                )
            )
        for plugin in plugins:
            text = normalize_text(f"{plugin.name} {plugin.filename or ''}")
            if any(token in text for token in ("controller", "control", "drive", "steer")):
                controllers.append(
                    ControllerInfo(
                        name=plugin.name,
                        controller_type=plugin.filename or "plugin_controller",
                        source="plugin",
                        data=plugin.data,
                    )
                )
        return controllers

    def _build_hierarchy(
        self, joints: Iterable[JointInfo]
    ) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
        hierarchy: Dict[str, List[str]] = {}
        child_to_parent: Dict[str, str] = {}
        for joint in joints:
            if not joint.parent or not joint.child:
                continue
            hierarchy.setdefault(joint.parent, []).append(joint.child)
            child_to_parent[joint.child] = joint.parent
        return {key: sorted(value) for key, value in hierarchy.items()}, child_to_parent

    def _build_kinematic_chains(
        self,
        links: Dict[str, LinkInfo],
        joints: Dict[str, JointInfo],
        hierarchy: Dict[str, List[str]],
    ) -> List[KinematicChain]:
        joint_by_edge = {
            (joint.parent, joint.child): joint for joint in joints.values() if joint.parent and joint.child
        }
        roots = sorted(set(links) - {joint.child for joint in joints.values() if joint.child})
        leaves = set(self._leaf_links(links, joints))
        chains: List[KinematicChain] = []

        def walk(link: str, link_path: List[str], joint_path: List[str], length: float) -> None:
            children = hierarchy.get(link, [])
            if not children or link in leaves:
                chains.append(
                    KinematicChain(
                        root=link_path[0],
                        tip=link_path[-1],
                        links=list(link_path),
                        joints=list(joint_path),
                        length_estimate=round(length, 6),
                    )
                )
            for child in children:
                joint = joint_by_edge.get((link, child))
                joint_length = self._origin_length(joint.origin) if joint else 0.0
                walk(
                    child,
                    link_path + [child],
                    joint_path + ([joint.name] if joint else []),
                    length + joint_length,
                )

        for root in roots or sorted(links)[:1]:
            walk(root, [root], [], 0.0)
        return chains

    def _derive_statistics(
        self,
        links: Dict[str, LinkInfo],
        joints: Dict[str, JointInfo],
        chains: List[KinematicChain],
        geometry: Dict[str, Dict[str, Any]],
        inertials: Dict[str, InertialInfo],
        sensors: List[SensorInfo],
        transmissions: List[TransmissionInfo],
    ) -> Dict[str, Any]:
        movable = [joint for joint in joints.values() if joint.joint_type != "fixed"]
        dimensions = self._estimate_dimensions(geometry)
        return {
            "link_count": len(links),
            "joint_count": len(joints),
            "movable_joint_count": len(movable),
            "fixed_joint_count": len(joints) - len(movable),
            "sensor_element_count": len(sensors),
            "transmission_count": len(transmissions),
            "kinematic_chain_count": len(chains),
            "max_chain_depth": max((len(chain.links) for chain in chains), default=0),
            "max_chain_length_estimate": max(
                (chain.length_estimate for chain in chains), default=0.0
            ),
            "total_mass": round(sum(inertial.mass for inertial in inertials.values()), 6),
            "estimated_dimensions": dimensions,
        }

    def _parse_geometry_container(self, element: Any) -> Optional[GeometryInfo]:
        geometry = self._first_child(element, "geometry")
        if geometry is None:
            return None
        shape = next(iter(list(geometry)), None)
        if shape is None:
            return None
        kind = local_name(shape.tag)
        data = self._attributes_as_numbers(shape)
        if kind == "box":
            data["size"] = split_floats(shape.get("size"))
        elif kind == "mesh":
            data["filename"] = shape.get("filename", "")
            data["scale"] = split_floats(shape.get("scale"))
        origin = self._parse_origin(self._first_child(element, "origin"))
        return GeometryInfo(
            kind=kind,
            data=data,
            origin=origin,
            material=self._material_name(element),
        )

    def _parse_inertial(self, element: Any) -> Optional[InertialInfo]:
        if element is None:
            return None
        mass_element = self._first_child(element, "mass")
        inertia_element = self._first_child(element, "inertia")
        mass = self._float_attr(mass_element, "value", 0.0) if mass_element is not None else 0.0
        return InertialInfo(
            mass=mass,
            inertia=self._attributes_as_numbers(inertia_element),
            origin=self._parse_origin(self._first_child(element, "origin")),
        )

    def _parse_origin(self, element: Any) -> Dict[str, List[float]]:
        if element is None:
            return {"xyz": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]}
        return {
            "xyz": split_floats(element.get("xyz")) or [0.0, 0.0, 0.0],
            "rpy": split_floats(element.get("rpy")) or [0.0, 0.0, 0.0],
        }

    def _link_ref(self, element: Any, child_name: str) -> Optional[str]:
        child = self._first_child(element, child_name)
        return child.get("link") if child is not None else None

    def _material_name(self, element: Any) -> Optional[str]:
        material = self._first_child(element, "material")
        return material.get("name") if material is not None else None

    def _attributes_as_numbers(self, element: Any) -> Dict[str, Any]:
        if element is None:
            return {}
        data: Dict[str, Any] = {}
        for key, value in dict(element.attrib).items():
            try:
                data[key] = float(value)
            except (TypeError, ValueError):
                data[key] = value
        return data

    def _element_data(self, element: Any) -> Dict[str, Any]:
        data: Dict[str, Any] = {"attributes": dict(element.attrib)}
        text = (element.text or "").strip()
        if text:
            data["text"] = text
        children: Dict[str, List[Dict[str, Any]]] = {}
        for child in list(element):
            child_name = local_name(child.tag)
            child_data = {"attributes": dict(child.attrib)}
            child_text = (child.text or "").strip()
            if child_text:
                child_data["text"] = child_text
            children.setdefault(child_name, []).append(child_data)
        if children:
            data["children"] = children
        return data

    def _geometry_to_dict(self, geometry: GeometryInfo) -> Dict[str, Any]:
        return {
            "kind": geometry.kind,
            "data": geometry.data,
            "origin": geometry.origin,
            "material": geometry.material,
        }

    def _estimate_dimensions(self, geometry: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        max_x = max_y = max_z = 0.0
        for link_geometry in geometry.values():
            for geom in link_geometry.get("visuals", []) + link_geometry.get("collisions", []):
                x, y, z = self._geometry_size(geom)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                max_z = max(max_z, z)
        return {
            "length": round(max_x, 6),
            "width": round(max_y, 6),
            "height": round(max_z, 6),
        }

    def _geometry_size(self, geometry: Dict[str, Any]) -> Tuple[float, float, float]:
        kind = geometry.get("kind")
        data = geometry.get("data", {})
        if kind == "box":
            size = data.get("size") or []
            padded = list(size) + [0.0, 0.0, 0.0]
            return float(padded[0]), float(padded[1]), float(padded[2])
        if kind == "cylinder":
            radius = float(data.get("radius", 0.0))
            length = float(data.get("length", 0.0))
            return 2 * radius, 2 * radius, length
        if kind == "sphere":
            radius = float(data.get("radius", 0.0))
            return 2 * radius, 2 * radius, 2 * radius
        if kind == "mesh":
            scale = data.get("scale") or [0.0, 0.0, 0.0]
            padded = list(scale) + [0.0, 0.0, 0.0]
            return float(padded[0]), float(padded[1]), float(padded[2])
        return 0.0, 0.0, 0.0

    def _leaf_links(self, links: Dict[str, LinkInfo], joints: Dict[str, JointInfo]) -> List[str]:
        parents = {joint.parent for joint in joints.values() if joint.parent}
        return sorted(set(links) - parents)

    def _origin_length(self, origin: Dict[str, List[float]]) -> float:
        xyz = origin.get("xyz", [0.0, 0.0, 0.0])
        return math.sqrt(sum(float(value) ** 2 for value in xyz))

    def _float_attr(self, element: Any, key: str, default: float) -> float:
        try:
            return float(element.get(key, default))
        except (TypeError, ValueError):
            return default

    # def _children(self, element: Any, tag: str) -> List[Any]:
    #     return [child for child in list(element) if local_name(child.tag) == tag]

    def _children(self, element: Any, tag: str) -> List[Any]:
        return [
            child
            for child in element
            if isinstance(child.tag, str)
            and local_name(child.tag) == tag
        ]

    def _first_child(self, element: Any, tag: str) -> Any:
        children = self._children(element, tag) if element is not None else []
        return children[0] if children else None

    def _iter_named(self, root: Any, tag: str) -> Iterable[Any]:
        for element in root.iter():
            if local_name(element.tag) == tag:
                yield element

    def _parent_name(self, element: Any) -> Optional[str]:
        getparent = getattr(element, "getparent", None)
        if getparent is None:
            return None
        parent = getparent()
        if parent is None:
            return None
        return parent.get("name") or local_name(parent.tag)
