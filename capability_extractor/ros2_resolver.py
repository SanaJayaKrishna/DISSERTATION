"""Resolve ROS 2 robot description inputs into a parseable URDF file."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import math
import xml.etree.ElementTree as ET

from .validators import URDFValidationError

from ament_index_python.packages import get_package_share_directory
import ament_index_python.packages as ament_packages


class ROS2DescriptionResolver:
    """Resolve URDF, Xacro, ROS 2 package paths, and package:// references."""

    def __init__(self, search_paths: Iterable[Path] | None = None) -> None:
        self.search_paths = [path.resolve() for path in search_paths or []]
        
        self.ros_package_paths = search_paths
        self.workspace_root = Path(__file__).resolve().parent.parent
        self._build_package_map()

    def resolve(
        self,
        urdf_path: Optional[Path] = None,
        package: Optional[str] = None,
        package_file: Optional[Path] = None,
        xacro_args: Optional[List[str]] = None,
    ) -> Path:
        """Return a URDF path suitable for the structural parser."""

        source = self._resolve_source_path(urdf_path, package, package_file)
        if source.suffix.lower() == ".xacro":
            raw_urdf = self._expand_xacro(source, xacro_args or [])
            return self._write_resolved_urdf(source, self._resolve_package_uris(raw_urdf))

        raw_urdf = source.read_text(encoding="utf-8")
        resolved = self._resolve_package_uris(raw_urdf)
        if resolved != raw_urdf:
            return self._write_resolved_urdf(source, resolved)
        return source

    def find_package_share(self, package: str) -> Path:
        ament_share = self._find_with_ament_index(package)
        if ament_share is not None:
            return ament_share

        candidates: List[Path] = []
        for base in self._ament_prefix_paths():
            candidates.append(base / "share" / package)
            candidates.append(base / package)
        for base in self._ros_package_paths():
            candidates.append(base / package)
        for base in self.search_paths:
            candidates.extend([base / package, base / "share" / package, base])

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir() and candidate.name == package:
                return candidate.resolve()
        raise URDFValidationError(
            f"Could not locate ROS 2 package '{package}'. Source your workspace or pass --ros-package-path."
        )

    def _resolve_source_path(
        self,
        urdf_path: Optional[Path],
        package: Optional[str],
        package_file: Optional[Path],
    ) -> Path:
        if urdf_path is not None:
            source = urdf_path.expanduser().resolve()
        elif package and package_file:
            source = (self.find_package_share(package) / package_file).resolve()
        else:
            raise URDFValidationError(
                "Provide either --urdf/--robot-description or both --ros-package and --package-file"
            )

        if not source.exists() or not source.is_file():
            raise URDFValidationError(f"Robot description file does not exist: {source}")
        return source

    def _expand_xacro(self, source: Path, xacro_args: List[str]) -> str:
        try:
            import xacro  # type: ignore

            # document = xacro.process_file(str(source), mappings=self._xacro_mappings(xacro_args))
            
            _original = ament_packages.get_package_share_directory

            def _patched(package):
                if package in self.package_map:
                    return self.package_map[package]
                return _original(package)

            ament_packages.get_package_share_directory = _patched

            source = self._preprocess_xacro(source)

            os.chdir(source.parent)

            document = xacro.process_file(str(source), mappings=self._xacro_mappings(xacro_args)            )

            return document.toprettyxml(indent="  ")
        except ImportError:
            return self._expand_xacro_command(source, xacro_args)
        except Exception as exc:
            raise URDFValidationError(f"Failed to expand xacro file {source}: {exc}") from exc

    def _expand_xacro_command(self, source: Path, xacro_args: List[str]) -> str:
        command = ["xacro", str(source), *xacro_args]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise URDFValidationError(
                "Xacro input requires the Python 'xacro' package or the 'xacro' command on PATH"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise URDFValidationError(
                f"xacro command failed for {source}: {exc.stderr.strip() or exc.stdout.strip()}"
            ) from exc
        return completed.stdout

    def _resolve_package_uris(self, raw_urdf: str) -> str:
        resolved = raw_urdf
        for package in sorted(self._package_names_in_text(raw_urdf)):
            try:
                share = self.find_package_share(package)
            except URDFValidationError:
                continue
            resolved = resolved.replace(f"package://{package}", str(share))
            resolved = resolved.replace(f"$(find {package})", str(share))
            resolved = resolved.replace(f"$(find-pkg-share {package})", str(share))
        return resolved

    def _write_resolved_urdf(self, source: Path, raw_urdf: str) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="capability_extractor_"))
        output = temp_dir / f"{source.stem}.resolved.urdf"
        output.write_text(raw_urdf, encoding="utf-8")
        return output

    def _xacro_mappings(self, args: List[str]) -> Dict[str, str]:
        mappings: Dict[str, str] = {}
        for arg in args:
            if ":=" in arg:
                key, value = arg.split(":=", 1)
                mappings[key] = value

        mappings.setdefault("PI", str(math.pi))
        mappings.setdefault("pi", str(math.pi))
        return mappings

    def _package_names_in_text(self, text: str) -> List[str]:
        names = set()
        marker = "package://"
        start = 0
        while True:
            index = text.find(marker, start)
            if index < 0:
                break
            tail = text[index + len(marker) :]
            name = tail.split("/", 1)[0].split('"', 1)[0].split("'", 1)[0]
            if name:
                names.add(name)
            start = index + len(marker)
        names.update(re.findall(r"\$\(find(?:-pkg-share)?\s+([^) \t]+)\)", text))
        return sorted(names)

    def _find_with_ament_index(self, package: str) -> Optional[Path]:
        try:
            from ament_index_python.packages import get_package_share_directory  # type: ignore

            return Path(get_package_share_directory(package)).resolve()
        except Exception:
            return None

    def _ament_prefix_paths(self) -> List[Path]:
        return [
            Path(path)
            for path in os.environ.get("AMENT_PREFIX_PATH", "").split(os.pathsep)
            if path
        ]

    def _ros_package_paths(self) -> List[Path]:
        return [
            Path(path)
            for path in os.environ.get("ROS_PACKAGE_PATH", "").split(os.pathsep)
            if path
        ]

    def _build_package_map(self):
        self.package_map = {}

        # for package_xml in Path(self.workspace_root).rglob("package.xml"):
        for package_xml in self.workspace_root.rglob("package.xml"):
            try:
                root = ET.parse(package_xml).getroot()
                name = root.findtext("name")
                if name:
                    self.package_map[name] = str(package_xml.parent.resolve())
            except Exception:
                pass

    def _preprocess_xacro(self, source: Path) -> Path:
        text = source.read_text()

        tmp_dir = source.parent

        for package, path in self.package_map.items():
            text = text.replace(
                f"$(find {package})",
                path
            )
            text = text.replace(f"package://{package}", path)

        # tmp = tempfile.NamedTemporaryFile(
        #     suffix=".xacro",
        #     delete=False,
        #     mode="w"
        # )
        tmp = tempfile.NamedTemporaryFile(
            suffix=".xacro",
            dir=tmp_dir,
            delete=False,
            mode="w"
        )
        tmp.write(text)
        tmp.close()

        return Path(tmp.name)