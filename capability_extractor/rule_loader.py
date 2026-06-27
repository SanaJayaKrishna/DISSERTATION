"""Load and validate semantic rules."""

from __future__ import annotations

import logging
from pathlib import Path

from .models.rule_models import RULE_GROUPS, Rule, RuleSet
from .utils import read_json
from .validators import validate_json_path, validate_rules_document


class RuleLoader:
    """Loads rule JSON into strongly typed rule objects."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def load(self, path: Path) -> RuleSet:
        validate_json_path(path)
        document = read_json(path)
        warnings = validate_rules_document(document)
        for warning in warnings:
            self.logger.warning(warning)

        rules_by_group = {
            group: [Rule.from_dict(group, data) for data in document.get(group, [])]
            for group in RULE_GROUPS
        }
        rule_count = sum(len(rules) for rules in rules_by_group.values())
        self.logger.info("Loaded %s rules from %s", rule_count, path)
        return RuleSet(
            version=str(document["version"]),
            metadata=dict(document.get("metadata", {})),
            vocabularies=dict(document.get("vocabularies", {})),
            rules_by_group=rules_by_group,
            conflict_resolution=dict(document.get("conflict_resolution", {})),
            defaults=dict(document.get("defaults", {})),
        )
