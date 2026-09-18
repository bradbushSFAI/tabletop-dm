"""Small helpers that every command module shares."""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import io_campaign
from .errors import DmError

INACTIVE_STATES = ("dead", "departed")
_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _SLUG.sub("-", text.strip().lower()).strip("-")


def split_list(text: Optional[str]) -> List[str]:
    """'a, b,c' -> ['a', 'b', 'c']."""
    if not text:
        return []
    return [part.strip().lower() for part in text.split(",") if part.strip()]


def require_character(party: Dict[str, Any], who: str) -> Dict[str, Any]:
    key = slugify(who)
    if key not in party["characters"]:
        known = ", ".join(sorted(party["characters"])) or "none yet"
        raise DmError("unknown_id", "no character '%s'. Known: %s." % (who, known))
    return party["characters"][key]


def is_active(character: Dict[str, Any]) -> bool:
    return character["life_state"] not in INACTIVE_STATES


def require_active(character: Dict[str, Any]) -> None:
    if not is_active(character):
        raise DmError("not_active", "%s is %s." % (character["id"], character["life_state"]))


def active_characters(party: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [ch for ch in party["characters"].values() if is_active(ch)]


def commit(campaign_dir: Path, party: Dict[str, Any], entries: List[Dict[str, Any]]) -> None:
    """State first, then the log. Both happen only after every check has passed."""
    io_campaign.save_party(campaign_dir, party)
    io_campaign.append_log(campaign_dir, entries)


def inventory_quantity(character: Dict[str, Any], item: str) -> int:
    for line in character["inventory"]:
        if line["item"] == item:
            return line["quantity"]
    return 0
