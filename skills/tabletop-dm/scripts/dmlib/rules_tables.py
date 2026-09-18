"""Small constant tables from SRD 5.1, in one place so no command holds a magic number."""
from typing import Dict, Tuple

from .errors import DmError

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")  # type: Tuple[str, ...]

SKILLS = {
    "acrobatics": "dex", "animal-handling": "wis", "arcana": "int", "athletics": "str",
    "deception": "cha", "history": "int", "insight": "wis", "intimidation": "cha",
    "investigation": "int", "medicine": "wis", "nature": "int", "perception": "wis",
    "performance": "cha", "persuasion": "cha", "religion": "int", "sleight-of-hand": "dex",
    "stealth": "dex", "survival": "wis",
}  # type: Dict[str, str]

STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)

# Cumulative XP needed to BE each level. This build stops at level 5 (PRD non-goal).
XP_THRESHOLDS = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500}  # type: Dict[int, int]
MAX_LEVEL = 5

CR_TO_XP = {0: 10, 0.125: 25, 0.25: 50, 0.5: 100, 1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
            6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900}  # type: Dict[float, int]

LEGAL_CONDITIONS = (
    "blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled", "incapacitated",
    "invisible", "paralyzed", "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious",
)

# hero + 2 companions (PRD section 12).
MAX_ACTIVE_PARTY = 3

ABILITY_SCORE_CAP = 20


def xp_for_cr(challenge_rating: float) -> int:
    if challenge_rating not in CR_TO_XP:
        raise DmError("illegal_value", "no XP value for challenge rating %s. Give --custom an xp_value." % challenge_rating)
    return CR_TO_XP[challenge_rating]


def level_for_xp(xp: int) -> int:
    level = 1
    for lvl, need in sorted(XP_THRESHOLDS.items()):
        if xp >= need:
            level = lvl
    return level
