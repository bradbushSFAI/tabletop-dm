"""The life-state machine of PRD section 11. Pure: a copy goes in, a changed copy comes out.

States: alive, dying, stable, fallen (hero only), dead, departed.
Where the hero becomes fallen (and the Grit save decides), a companion becomes dead.
"""
import copy
from typing import Any, Dict, Optional, Tuple

from .errors import DmError

DEATH_SAVE_DC = 10
FAILURES_TO_DIE = 3
SUCCESSES_TO_STABILIZE = 3
NO_TARGET_STATES = ("fallen", "dead", "departed")

# The Grit save outcome for a failure, by difficulty (PRD section 11).
GRIT_FAILURE_OUTCOME = {"story": "light_cost", "standard": "heavy_cost", "iron": "dead"}


def _end_state(is_hero: bool) -> str:
    return "fallen" if is_hero else "dead"


def _reset_saves(character: Dict[str, Any]) -> None:
    character["death_saves"] = {"successes": 0, "failures": 0}


def _set_unconscious(character: Dict[str, Any], unconscious: bool) -> None:
    conditions = [c for c in character["conditions"] if c != "unconscious"]
    if unconscious:
        conditions.append("unconscious")
    character["conditions"] = conditions


def apply_damage(character: Dict[str, Any], amount: int, is_crit: bool, is_hero: bool) -> Dict[str, Any]:
    c = copy.deepcopy(character)
    state = c["life_state"]
    if state in NO_TARGET_STATES:
        raise DmError("not_eligible_for_damage", "%s is %s. Damage has no effect." % (c["id"], state))
    absorbed = min(c["hp"].get("temp", 0), amount)
    c["hp"]["temp"] = c["hp"].get("temp", 0) - absorbed
    amount -= absorbed
    # SRD instant death: the damage left over after reaching 0 HP equals or passes the HP maximum.
    # For a character already at 0 HP, all of the damage is left over. One formula covers both.
    overkill = amount - c["hp"]["current"]
    if overkill >= c["hp"]["max"]:
        c["hp"]["current"] = 0
        c["life_state"] = _end_state(is_hero)
        c["death_saves"]["failures"] = FAILURES_TO_DIE
        _set_unconscious(c, True)
        c["note"] = "massive damage"
        return c
    if state == "alive":
        c["hp"]["current"] = max(0, c["hp"]["current"] - amount)
        if c["hp"]["current"] == 0:
            c["life_state"] = "dying"
            _reset_saves(c)
            _set_unconscious(c, True)
        return c
    if amount <= 0:
        return c
    # Already at 0 HP. Damage is a death-save failure, two on a critical hit (5e).
    if state == "stable":
        _reset_saves(c)
        c["life_state"] = "dying"
    c["death_saves"]["failures"] = min(FAILURES_TO_DIE, c["death_saves"]["failures"] + (2 if is_crit else 1))
    if c["death_saves"]["failures"] >= FAILURES_TO_DIE:
        c["life_state"] = _end_state(is_hero)
    return c


def _wake(c: Dict[str, Any]) -> None:
    c["life_state"] = "alive"
    _reset_saves(c)
    _set_unconscious(c, False)


def apply_heal(character: Dict[str, Any], amount: int) -> Dict[str, Any]:
    c = copy.deepcopy(character)
    if c["life_state"] in NO_TARGET_STATES:
        raise DmError("not_eligible_for_heal", "%s is %s. Healing cannot help. %s" % (
            c["id"], c["life_state"], "Run grit first." if c["life_state"] == "fallen" else ""))
    c["hp"]["current"] = min(c["hp"]["max"], c["hp"]["current"] + amount)
    if c["hp"]["current"] > 0 and c["life_state"] in ("dying", "stable"):
        _wake(c)
    return c


def apply_death_save(character: Dict[str, Any], d20_roll: int, is_hero: bool) -> Tuple[Dict[str, Any], str]:
    c = copy.deepcopy(character)
    if c["life_state"] != "dying":
        raise DmError("not_dying", "%s is %s, not dying." % (c["id"], c["life_state"]))
    saves = c["death_saves"]
    if d20_roll == 20:
        c["hp"]["current"] = 1
        _wake(c)
        return c, "critical_success"
    if d20_roll >= DEATH_SAVE_DC:
        saves["successes"] += 1
        result = "success"
    else:
        saves["failures"] = min(FAILURES_TO_DIE, saves["failures"] + (2 if d20_roll == 1 else 1))
        result = "critical_failure" if d20_roll == 1 else "failure"
    if saves["failures"] >= FAILURES_TO_DIE:
        c["life_state"] = _end_state(is_hero)
    elif saves["successes"] >= SUCCESSES_TO_STABILIZE:
        c["life_state"] = "stable"
        _reset_saves(c)
    return c, result


def apply_grit(character: Dict[str, Any], save_total: Optional[int], dc: int,
               difficulty: str) -> Tuple[Dict[str, Any], str]:
    """The Grit save. save_total is None only when it was already used (no roll, automatic failure)."""
    c = copy.deepcopy(character)
    if c["life_state"] != "fallen":
        raise DmError("not_fallen", "%s is %s, not fallen." % (c["id"], c["life_state"]))
    if c["grit_used_since_long_rest"]:
        success = False
    else:
        if save_total is None:
            raise ValueError("a Grit roll is required when the save is available")
        success = save_total >= dc
    c["grit_used_since_long_rest"] = True
    outcome = "light_cost" if success else GRIT_FAILURE_OUTCOME[difficulty]
    if outcome == "dead":
        c["life_state"] = "dead"
        return c, outcome
    c["life_state"] = "stable"
    c["hp"]["current"] = 0
    _reset_saves(c)
    _set_unconscious(c, True)
    return c, outcome


def apply_hp_gain_from_rest(character: Dict[str, Any], hp_gained: int) -> Dict[str, Any]:
    """A rest that restores HP wakes a stable character. A rest that restores none does not."""
    c = copy.deepcopy(character)
    c["hp"]["current"] = min(c["hp"]["max"], c["hp"]["current"] + hp_gained)
    if c["hp"]["current"] > 0 and c["life_state"] in ("dying", "stable"):
        _wake(c)
    return c
