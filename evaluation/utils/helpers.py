"""General-purpose helpers used across the evaluation framework."""
from __future__ import annotations

import re
from typing import Any, Dict, Set


def normalise_name(name: str) -> str:
    """Normalise a name string for comparison.

    Converts to lowercase, strips whitespace, and collapses internal spaces.

    Args:
        name: Input string.

    Returns:
        Normalised lowercase string.
    """
    return re.sub(r"\s+", " ", name.strip().lower())


def keyword_overlap(text_a: str, text_b: str, stop_words: Set[str] | None = None) -> float:
    """Compute Jaccard-like keyword overlap between two texts.

    Args:
        text_a: First text.
        text_b: Second text.
        stop_words: Optional set of words to exclude.

    Returns:
        Overlap ratio in [0, 1].
    """
    stop = stop_words or set()

    def tokens(t: str) -> Set[str]:
        return {
            w.lower()
            for w in re.findall(r"[a-zA-Z]+", t)
            if w.lower() not in stop and len(w) > 2
        }

    a, b = tokens(text_a), tokens(text_b)
    if not a and not b:
        return 1.0
    union = a | b
    intersection = a & b
    return len(intersection) / len(union) if union else 0.0


def clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clip a float to the [lo, hi] range.

    Args:
        value: Input value.
        lo: Lower bound (default 0.0).
        hi: Upper bound (default 1.0).

    Returns:
        Clipped value.
    """
    return max(lo, min(hi, value))


def deep_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safe nested dict accessor.

    Args:
        d: Source dictionary.
        *keys: Chain of keys to traverse.
        default: Value to return if any key is missing.

    Returns:
        Nested value or default.
    """
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur
