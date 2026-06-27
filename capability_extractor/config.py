"""Configuration for the capability extractor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class ExtractorConfig:
    """Runtime configuration."""

    urdf_path: Optional[Path]
    rules_path: Path
    output_path: Path
    ros_package: Optional[str] = None
    package_file: Optional[Path] = None
    ros_package_paths: List[Path] | None = None
    xacro_args: List[str] | None = None
    log_level: str = "INFO"
    debug_rules: bool = False
    max_rule_passes: int = 6
