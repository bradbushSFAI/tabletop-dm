"""encounter start / add / next / end. encounter.json exists only while a fight is active."""
import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import cmd_character, data, derive, dice, io_campaign, party_ops
from .errors import DmError
from .rules_tables import ABILITIES, xp_for_cr

MAX_MONSTERS_PER_ENTRY = 20
# A dying character keeps its turn, because the death save happens on it (5e).
SKIP_STATES = ("stable", "dead", "departed")


def _require_encounter(campaign_dir: Path) -> Dict[str, Any]:
    encounter = io_campaign.load_encounter(campaign_dir)
    if encounter is None:
        raise DmError("no_active_encounter", "no fight is active. Start one with: encounter start --monster name:count")
    return encounter


def _parse_custom(text: str) -> Dict[str, Any]:
    try:
        spec = json.loads(text)
    except ValueError as exc:
        raise DmError("illegal_custom_monster", "--custom is not valid JSON (%s)." % exc)
    problems = []
    if not isinstance(spec, dict):
        raise DmError("illegal_custom_monster", "--custom must be a JSON object.")
    if not isinstance(spec.get("name"), str) or not party_ops.slugify(spec.get("name", "")):
        problems.append("name (text)")
    for key in ("ac", "hp"):
        if not isinstance(spec.get(key), int) or spec[key] < 1:
            problems.append("%s (whole number, 1 or more)" % key)
    if "challenge_rating" not in spec and not isinstance(spec.get("xp_value"), int):
        problems.append("challenge_rating or xp_value")
    if problems:
        raise DmError("illegal_custom_monster", "--custom is missing or has a bad: %s." % ", ".join(problems))
    abilities = spec.get("abilities") or {}
    spec["abilities"] = {a: int(abilities.get(a, 10)) for a in ABILITIES}
    if not isinstance(spec.get("xp_value"), int):
        spec["xp_value"] = xp_for_cr(spec["challenge_rating"])
    spec["count"] = int(spec.get("count", 1))
    return spec


def _build_groups(args: argparse.Namespace, monsters_data: Dict[str, Any]) -> List[Tuple[Dict[str, Any], int, bool]]:
    """Every (record, count, is_custom) the command names. Validates all before any die is rolled."""
    groups = []  # type: List[Tuple[Dict[str, Any], int, bool]]
    for entry in args.monster or []:
        name, _, count = entry.partition(":")
        if count and not count.isdigit():
            raise DmError("bad_arguments", "--monster takes name:count, for example --monster goblin:3.")
        groups.append((data.get_record(monsters_data, "monster", name), int(count or 1), False))
    for text in args.custom or []:
        spec = _parse_custom(text)
        groups.append((spec, spec["count"], True))
    if not groups:
        raise DmError("bad_arguments", "name at least one monster: --monster name:count, or --custom '<json>'.")
    for _, count, _ in groups:
        if not 1 <= count <= MAX_MONSTERS_PER_ENTRY:
            raise DmError("illegal_value", "a monster count must be 1 to %d." % MAX_MONSTERS_PER_ENTRY)
    return groups


def _add_monsters(encounter: Dict[str, Any], groups: List[Tuple[Dict[str, Any], int, bool]], average_hp: bool,
                  rng: random.Random, command: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """One initiative roll per group (5e group initiative), one hit-point roll per monster."""
    added, entries = [], []  # type: List[str], List[Dict[str, Any]]
    rolled = []
    for record, count, custom in groups:
        dex = derive.ability_modifier(record["abilities"]["dex"])
        natural = dice.roll_d20(rng)["kept"]
        rolled.append(natural + dex)
        entries.append(io_campaign.roll_entry(command, {"who": record["name"], "kind": "initiative",
                                                        "expr": "1d20%+d" % dex, "rolls": [natural], "total": natural + dex}))
    for (record, count, custom), initiative in zip(groups, rolled):
        source = party_ops.slugify(record["name"]) if custom else record["id"]
        dex = derive.ability_modifier(record["abilities"]["dex"])
        for _ in range(count):
            number = 1 + len([m for m in encounter["monsters"].values() if m["source"] == source])
            mid = "%s-%d" % (source, number)
            if custom:
                hp = record["hp"]
            elif average_hp:
                hp = record["hp_average"]
            else:
                roll = dice.roll_expression(record["hp_expr"], rng)
                hp = max(1, roll["total"])
                entries.append(io_campaign.roll_entry(command, {"who": mid, "kind": "monster_hp",
                                                                "expr": record["hp_expr"], "dice": roll["dice"], "total": hp}))
            encounter["monsters"][mid] = {
                "id": mid, "name": record["name"], "source": source, "custom": custom,
                "hp": {"current": hp, "max": hp}, "ac": record["ac"], "xp_value": record["xp_value"],
                "attacks": record.get("attacks", []), "tactic": record.get("tactic", ""),
                "conditions": [], "defeated": False,
            }
            encounter["initiative_order"].append({"id": mid, "kind": "monster", "initiative": initiative, "dex": dex})
            added.append(mid)
    return added, entries


def _sort_order(encounter: Dict[str, Any]) -> None:
    """High initiative first. Ties: higher Dexterity, then the party before monsters."""
    encounter["initiative_order"].sort(key=lambda c: (-c["initiative"], -c["dex"], c["kind"] != "party"))


def _turn(encounter: Dict[str, Any]) -> Dict[str, Any]:
    current = encounter["initiative_order"][encounter["turn_index"]]
    return {"id": current["id"], "kind": current["kind"]}


def start(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    if io_campaign.load_encounter(campaign_dir) is not None:
        raise DmError("encounter_active", "a fight is already active. Run encounter end first.")
    groups = _build_groups(args, data.load_all(skill_root)["monsters"])
    fighters = party_ops.active_characters(party)
    if not fighters:
        raise DmError("no_party", "create a character first.")
    encounter = {"format": io_campaign.ENCOUNTER_FORMAT, "format_version": 1, "round": 1, "turn_index": 0,
                 "initiative_order": [], "monsters": {}}  # type: Dict[str, Any]
    entries = []
    for character in fighters:
        dex = character["ability_modifiers"]["dex"]
        natural = dice.roll_d20(rng)["kept"]
        encounter["initiative_order"].append({"id": character["id"], "kind": "party", "initiative": natural + dex, "dex": dex})
        entries.append(io_campaign.roll_entry("encounter_start", {"who": character["id"], "kind": "initiative",
                                                                  "expr": "1d20%+d" % dex, "rolls": [natural],
                                                                  "total": natural + dex}))
    _, more = _add_monsters(encounter, groups, args.average_hp, rng, "encounter_start")
    entries.extend(more)
    _sort_order(encounter)
    entries.append(io_campaign.change_entry("encounter_start", None, "encounter", None, sorted(encounter["monsters"])))
    io_campaign.save_encounter(campaign_dir, encounter)
    io_campaign.append_log(campaign_dir, entries)
    return {"round": 1, "turn": _turn(encounter), "initiative_order": encounter["initiative_order"],
            "monsters": encounter["monsters"]}


def add(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    io_campaign.load_party(campaign_dir)
    encounter = _require_encounter(campaign_dir)
    groups = _build_groups(args, data.load_all(skill_root)["monsters"])
    current = encounter["initiative_order"][encounter["turn_index"]]["id"]
    added, entries = _add_monsters(encounter, groups, args.average_hp, rng, "encounter_add")
    _sort_order(encounter)
    # Joining above the current turn must not hand the turn to someone else.
    encounter["turn_index"] = [c["id"] for c in encounter["initiative_order"]].index(current)
    entries.append(io_campaign.change_entry("encounter_add", None, "encounter.monsters", None, added))
    io_campaign.save_encounter(campaign_dir, encounter)
    io_campaign.append_log(campaign_dir, entries)
    return {"added": added, "turn": _turn(encounter), "initiative_order": encounter["initiative_order"],
            "monsters": {mid: encounter["monsters"][mid] for mid in added}}


def _can_take_turn(combatant: Dict[str, Any], party: Dict[str, Any], encounter: Dict[str, Any]) -> bool:
    if combatant["kind"] == "monster":
        monster = encounter["monsters"][combatant["id"]]
        return not monster["defeated"] and not monster.get("fled")
    character = party["characters"].get(combatant["id"])
    return character is not None and character["life_state"] not in SKIP_STATES


def next_turn(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    encounter = _require_encounter(campaign_dir)
    order = encounter["initiative_order"]
    before = {"round": encounter["round"], "turn_index": encounter["turn_index"]}
    note = None
    for _ in range(len(order)):
        encounter["turn_index"] += 1
        if encounter["turn_index"] >= len(order):
            encounter["turn_index"] = 0
            encounter["round"] += 1
        if _can_take_turn(order[encounter["turn_index"]], party, encounter):
            break
    else:
        note = "no combatant can act. End the fight with: encounter end"
    turn = _turn(encounter)
    if turn["kind"] == "party":
        state = party["characters"][turn["id"]]["life_state"]
        if state == "dying":
            turn["note"] = "dying: run deathsave"
        elif state == "fallen":
            turn["note"] = "fallen: run grit"
    if note:
        turn["note"] = note
    io_campaign.save_encounter(campaign_dir, encounter)
    io_campaign.append_log(campaign_dir, [io_campaign.change_entry(
        "encounter_next", None, "encounter.turn", before, {"round": encounter["round"], "turn_index": encounter["turn_index"]})])
    return {"round": encounter["round"], "turn": turn, "monsters": _monsters_left(encounter)}


def _monsters_left(encounter: Dict[str, Any]) -> Dict[str, str]:
    """HP of every monster still in the fight, so the DM never holds one in memory."""
    return {mid: "%d/%d" % (m["hp"]["current"], m["hp"]["max"]) for mid, m in encounter["monsters"].items()
            if not m["defeated"] and not m.get("fled")}


def flee(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    """A monster that runs or yields: out of the turn order, and no XP for it."""
    campaign_dir = Path(args.campaign)
    io_campaign.load_party(campaign_dir)
    encounter = _require_encounter(campaign_dir)
    mid = party_ops.slugify(args.who)
    if mid not in encounter["monsters"]:
        raise DmError("unknown_id", "no monster '%s' in this fight. Monsters: %s."
                      % (args.who, ", ".join(sorted(encounter["monsters"]))))
    encounter["monsters"][mid]["fled"] = True
    io_campaign.save_encounter(campaign_dir, encounter)
    io_campaign.append_log(campaign_dir, [io_campaign.change_entry("encounter_flee", mid, "fled", False, True)])
    return {"who": mid, "fled": True, "monsters": _monsters_left(encounter)}


def end(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    encounter = _require_encounter(campaign_dir)
    for character in party["characters"].values():
        if character["life_state"] == "fallen":
            raise DmError("hero_not_resolved", "%s is fallen. Run grit before the fight ends." % character["id"])
    records = data.load_all(skill_root)
    total = 0 if args.no_xp else sum(m["xp_value"] for m in encounter["monsters"].values() if m["defeated"])
    members = party_ops.active_characters(party)
    share = total // len(members) if members and total else 0
    entries, level_ups = [], {}
    if share:
        for character in members:
            summary, more = cmd_character.award_xp(character, share, records, rng, "encounter_end")
            entries.extend(more)
            if summary:
                level_ups[character["id"]] = summary
    entries.append(io_campaign.change_entry("encounter_end", None, "encounter", sorted(encounter["monsters"]), None,
                                            {"xp_awarded": total, "rounds": encounter["round"]}))
    party_ops.commit(campaign_dir, party, entries)
    io_campaign.delete_encounter(campaign_dir)
    return {"xp_awarded": total, "xp_per_member": share, "members": [c["id"] for c in members],
            "level_ups": level_ups, "rounds": encounter["round"]}
