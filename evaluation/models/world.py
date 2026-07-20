"""Internal data models for the world / environment."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass
class Room:
    """A navigable location in the world.

    Attributes:
        room_id: Unique snake-case identifier (e.g. ``cafeteria``).
        name: Human-readable display name (e.g. ``Cafeteria``).
    """
    room_id: str
    name: str


@dataclass
class WorldState:
    """Complete world model used by validators.

    Attributes:
        name: World environment name (e.g. ``College Campus``).
        env_type: Category string (e.g. ``Mixed (Indoor + Outdoor)``).
        rooms: All navigable rooms / locations.
        objects: Flat collection of all known object names (normalised to
            lowercase for case-insensitive matching).
        room_names_lower: Pre-computed lowercase set of all room *names* and
            *ids* for O(1) lookup.
        raw: Original parsed JSON for validators needing raw access.
    """
    name: str
    env_type: str
    rooms: List[Room]
    objects: List[str]
    room_names_lower: Set[str]
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build_room_names_lower(cls, rooms: List[Room]) -> Set[str]:
        """Return a lowercase set of all room ids and names.

        Args:
            rooms: Parsed room list.

        Returns:
            Set of lowercase strings for O(1) membership checks.
        """
        result: Set[str] = set()
        for r in rooms:
            result.add(r.room_id.lower())
            result.add(r.name.lower())
        return result

    def location_exists(self, location: str) -> bool:
        """Check whether a location string is valid in this world.

        Args:
            location: Location name or id from the plan (case-insensitive).

        Returns:
            ``True`` if the location is known.
        """
        return location.strip().lower() in self.room_names_lower

    def object_exists(self, obj: str) -> bool:
        """Check whether an object exists in this world (fuzzy/substring).

        Because plan object references are often natural-language phrases
        (e.g. *"best book for learning Reinforcement Learning"*) rather than
        exact keys, we do a case-insensitive substring match against every
        known object token.

        Args:
            obj: Object reference from the plan.

        Returns:
            ``True`` if any known object is a substring of *obj* or vice-versa.
        """
        obj_lower = obj.strip().lower()
        for known in self.objects:
            k = known.lower()
            if k in obj_lower or obj_lower in k:
                return True
        return False
