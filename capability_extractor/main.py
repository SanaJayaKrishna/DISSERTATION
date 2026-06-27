"""Command line entry point for the URDF capability extractor."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capability_extractor.config import ExtractorConfig
from capability_extractor.capability_builder import CapabilityBuilder
from capability_extractor.constraint_engine import ConstraintEngine
from capability_extractor.inference_engine import InferenceEngine
from capability_extractor.models.capability_model import CapabilityState
from capability_extractor.parser import StructuralParser
from capability_extractor.quantitative_engine import QuantitativeCapabilityEngine
from capability_extractor.ros2_resolver import ROS2DescriptionResolver
from capability_extractor.rule_loader import RuleLoader
from capability_extractor.semantic_engine import CapabilityRuleEvaluator, SemanticRuleEngine
from capability_extractor.utils import setup_logging, write_json


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_RULES_PATH = PROJECT_DIR / "rules" / "rules.json"
DEFAULT_OUTPUT_PATH = PROJECT_DIR / "outputs" / "capabilities.json"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract robot capabilities from URDF and rules.json")
    parser.add_argument(
        "--urdf",
        "--robot-description",
        dest="urdf",
        type=Path,
        help="Path to a URDF or Xacro robot description file",
    )
    parser.add_argument(
        "--ros-package",
        "--ros2-package",
        dest="ros_package",
        help="ROS 2 package name containing the robot description",
    )
    parser.add_argument(
        "--package-file",
        "--description-file",
        "--package-description",
        dest="package_file",
        type=Path,
        help="Robot description path relative to the ROS 2 package share directory",
    )
    parser.add_argument(
        "--ros-package-path",
        type=Path,
        action="append",
        default=[],
        help="Additional directory to search for ROS 2 packages",
    )
    parser.add_argument(
        "--xacro-arg",
        action="append",
        default=[],
        help="Argument passed to xacro, for example name:=value. Can be repeated.",
    )
    parser.add_argument(
        "--list-package-files",
        action="store_true",
        help="List .urdf and .xacro files in --ros-package and exit",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES_PATH,
        help=f"Path to rules.json. Default: {DEFAULT_RULES_PATH}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to write capabilities.json. Default: {DEFAULT_OUTPUT_PATH}",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--debug-rules", action="store_true", help="Log each rule evaluation")
    return parser


class CapabilityExtractorApplication:
    """Coordinates the complete extraction pipeline."""

    def __init__(self, config: ExtractorConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.rule_loader = RuleLoader(logger)
        self.parser = StructuralParser(logger)
        self.resolver = ROS2DescriptionResolver(config.ros_package_paths)
        self.evaluator = CapabilityRuleEvaluator(logger, debug_rules=config.debug_rules)
        self.quantitative_engine = QuantitativeCapabilityEngine(self.evaluator, logger)
        self.semantic_engine = SemanticRuleEngine(
            self.evaluator,
            max_passes=config.max_rule_passes,
            logger=logger,
        )
        self.inference_engine = InferenceEngine(self.evaluator, logger=logger)
        self.constraint_engine = ConstraintEngine(self.evaluator, logger)
        self.builder = CapabilityBuilder()

    def run(self) -> None:
        rules = self.rule_loader.load(self.config.rules_path)
        robot_description_path = self.resolver.resolve(
            urdf_path=self.config.urdf_path,
            package=self.config.ros_package,
            package_file=self.config.package_file,
            xacro_args=self.config.xacro_args,
        )
        self.logger.info("Using robot description %s", robot_description_path)
        robot = self.parser.parse(robot_description_path)
        self.logger.info(
            "Parsed robot '%s' with %s links and %s joints",
            robot.name,
            len(robot.links),
            len(robot.joints),
        )

        state = CapabilityState.from_defaults(rules.defaults)
        self.quantitative_engine.run(robot, rules, state)
        self.semantic_engine.run(robot, rules, state)
        self.inference_engine.run(robot, rules, state)
        self.constraint_engine.run(robot, rules, state)

        document = self.builder.build(robot, rules, state)
        write_json(self.config.output_path, document)
        self.logger.info("Wrote capabilities JSON to %s", self.config.output_path)


def main() -> int:
    args = build_arg_parser().parse_args()
    logger = setup_logging(args.log_level)
    if args.list_package_files:
        try:
            _list_package_files(args.ros_package, args.ros_package_path)
        except Exception:
            logger.exception("Could not list package robot descriptions")
            return 1
        return 0

    config = ExtractorConfig(
        urdf_path=args.urdf,
        rules_path=args.rules,
        output_path=args.output,
        ros_package=args.ros_package,
        package_file=args.package_file,
        ros_package_paths=args.ros_package_path,
        xacro_args=args.xacro_arg,
        log_level=args.log_level,
        debug_rules=args.debug_rules,
    )
    try:
        CapabilityExtractorApplication(config, logger).run()
    except Exception:
        logger.exception("Capability extraction failed")
        return 1
    return 0


def _list_package_files(package: str | None, search_paths: list[Path]) -> None:
    if not package:
        raise ValueError("--list-package-files requires --ros-package")
    resolver = ROS2DescriptionResolver(search_paths)
    share = resolver.find_package_share(package)
    files = sorted(
        path.relative_to(share)
        for path in share.rglob("*")
        if path.suffix.lower() in {".urdf", ".xacro"}
    )
    for path in files:
        print(path)


if __name__ == "__main__":
    raise SystemExit(main())
