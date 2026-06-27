"""Shared utility functions."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


LOGGER_NAME = "capability_extractor"


def setup_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger(LOGGER_NAME)


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def split_floats(value: str | None) -> List[float]:
    if not value:
        return []
    return [float(part) for part in value.split()]


def unique_sorted(values: Iterable[str]) -> List[str]:
    return sorted({str(value) for value in values if str(value)})


def stable_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value[key] for key in sorted(value)}


# def local_name(tag: str) -> str:
    # return tag.rsplit("}", 1)[-1] if "}" in tag else tag

def local_name(tag):
    if not isinstance(tag, str):
        return ""

    return tag.rsplit("}", 1)[-1]


def path_get(data: Dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current
