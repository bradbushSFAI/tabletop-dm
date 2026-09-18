"""damage, heal, stabilize, cast, rest, item, gold, condition, deathsave, grit."""
import argparse
import copy
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import data, derive, dice, io_campaign, life_states, party_ops
from .cmd_setup import gp
from .errors import DmError
from .rules_tables import LEGAL_CONDITIONS

MAX_GRIT_DC = 30
_GP = re.compile(r"^\d+(\.\d{1,2})?$")


def _hp_text(hp: Dict[str, int]) -> str:
    return "%d/%d" % (hp["current"], hp["max"])


def _positive(amount: int, what: str) -> None:
    if amount < 1:
        raise DmError("illegal_value", "%s must be 1 or more." % what)


def _find_target(party: Dict[str, Any], encounter: Optional[Dict[str, Any]], who: str) -> Tuple[str, Dict[str, Any]]:
    """A party member first, then a monster in the active fight."""
    key = party_ops.slugify(who)
    if key in party["characters"]:
        return "character", party["characters"][key]
    if encounter and key in encounter["monsters"]:
        return "monster", encounter["monsters"][key]
    known = sorted(party["characters"]) + sorted((encounter or {}).get("monsters", {}))
    raise DmError("unknown_id", "no character or monster '%s'. Known: %s." % (who, ", ".join(known) or "none"))


def _state_report(character: Dict[str, Any]) -> Dict[str, Any]:
    out = {"who": character["id"], "hp": _hp_text(character["hp"]), "life_state": character["life_state"]}  # type: Dict[str, Any]
    if character["hp"].get("temp"):
        out["temp_hp"] = character["hp"]["temp"]
    if character["life_state"] == "dying":
        out["death_saves"] = character["death_saves"]
        out["next"] = "on this character's turn run: deathsave --who %s" % character["id"]
    if character["life_state"] == "fallen":
        out["next"] = "by the 5e rules the hero is dead. Set a DC and run: grit --dc N"
    if character.get("note"):
        out["note"] = character.pop("note")
    return out


def _hp_entries(command: str, before: Dict[str, Any], after: Dict[str, Any], details: Dict[str, Any]) -> List[Dict[str, Any]]:
    info = dict(details)
    info["life_state_before"] = before["life_state"]
    info["life_state_after"] = after["life_state"]
    entries = [io_campaign.change_entry(command, after["id"], "hp.current", before["hp"]["current"],
                                        after["hp"]["current"], info)]
    if before["death_saves"] != after["death_saves"]:
        entries.append(io_campaign.change_entry(command, after["id"], "death_saves", before["death_saves"],
                                                after["death_saves"]))
    return entries


# ---------- damage / heal / stabilize ----------

def _change_hp(args: argparse.Namespace, command: str) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    encounter = io_campaign.load_encounter(campaign_dir)
    _positive(args.amount, "--amount")
    kind, target = _find_target(party, encounter, args.who)
    if kind == "monster":
        before = target["hp"]["current"]
        if command == "damage":
            target["hp"]["current"] = max(0, before - args.amount)
        else:
            target["hp"]["current"] = min(target["hp"]["max"], before + args.amount)
        target["defeated"] = target["hp"]["current"] == 0
        io_campaign.save_encounter(campaign_dir, encounter)  # type: ignore[arg-type]
        io_campaign.append_log(campaign_dir, [io_campaign.change_entry(
            command, target["id"], "hp.current", before, target["hp"]["current"], {"amount": args.amount})])
        return {"who": target["id"], "hp": _hp_text(target["hp"]), "defeated": target["defeated"]}
    before_sheet = copy.deepcopy(target)
    is_hero = party["hero_id"] == target["id"]
    if command == "damage":
        after = life_states.apply_damage(target, args.amount, args.crit, is_hero)
        details = {"amount": args.amount, "crit": args.crit}
    elif args.temp:
        # 5e: temporary hit points do not stack. Keep the higher value.
        party_ops.require_active(target)
        after = copy.deepcopy(target)
        after["hp"]["temp"] = max(after["hp"].get("temp", 0), args.amount)
        details = {"amount": args.amount, "temp": True}
    else:
        after = life_states.apply_heal(target, args.amount)
        details = {"amount": args.amount}
    report = _state_report(after)
    party["characters"][after["id"]] = after
    party_ops.commit(campaign_dir, party, _hp_entries(command, before_sheet, after, details))
    return report


def damage(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    return _change_hp(args, "damage")


def heal(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    return _change_hp(args, "heal")


def stabilize(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    """After a DC 10 Medicine check, a healer's kit, or a stabilizing spell (5e)."""
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    character = party_ops.require_character(party, args.who)
    if character["life_state"] != "dying":
        raise DmError("not_dying", "%s is %s, not dying." % (character["id"], character["life_state"]))
    character["life_state"] = "stable"
    character["death_saves"] = {"successes": 0, "failures": 0}
    party_ops.commit(campaign_dir, party, [io_campaign.change_entry(
        "stabilize", character["id"], "life_state", "dying", "stable")])
    return _state_report(character)


# ---------- cast ----------

def cast(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    spells = data.load_all(skill_root)["spells"]
    character = party_ops.require_character(party, args.who)
    casting = character.get("spellcasting")
    if not casting:
        raise DmError("not_a_caster", "%s is a %s and casts no spells." % (character["id"], character["class"]))
    if character["life_state"] != "alive":
        raise DmError("cannot_act", "%s is %s and cannot cast." % (character["id"], character["life_state"]))
    spell = data.get_record(spells, "spell", args.spell)
    sid = spell["id"]
    if spell["level"] == 0:
        if sid not in casting["cantrips"]:
            raise DmError("spell_not_prepared", "%s does not know the cantrip %s. Known: %s."
                          % (character["id"], sid, ", ".join(casting["cantrips"])))
        slot = 0
    else:
        if sid not in casting["prepared"]:
            raise DmError("spell_not_prepared", "%s has not prepared %s. Prepared: %s."
                          % (character["id"], sid, ", ".join(casting["prepared"]) or "nothing"))
        slot = args.slot if args.slot is not None else spell["level"]
        if slot < spell["level"]:
            raise DmError("slot_too_low", "%s is a level %d spell. It cannot be cast with a level %d slot."
                          % (sid, spell["level"], slot))
        pool = casting["slots"].get(str(slot))
        if not pool or pool["used"] >= pool["max"]:
            left = {k: v["max"] - v["used"] for k, v in sorted(casting["slots"].items())}
            raise DmError("no_slot_available", "%s has no level %d slot left. Slots left: %s."
                          % (character["id"], slot, left))
    before = copy.deepcopy(casting["slots"])
    if slot:
        casting["slots"][str(slot)]["used"] += 1
    party_ops.commit(campaign_dir, party, [io_campaign.change_entry(
        "cast", character["id"], "spellcasting.slots", before, casting["slots"], {"spell": sid, "slot": slot})])
    return {"who": character["id"], "spell": spell, "slot_used": slot, "save_dc": casting["save_dc"],
            "spell_attack_bonus": casting["attack_bonus"],
            "slots_left": {k: v["max"] - v["used"] for k, v in sorted(casting["slots"].items())}}


# ---------- rest ----------

def _require_restable(party: Dict[str, Any], campaign_dir: Path) -> None:
    if io_campaign.load_encounter(campaign_dir) is not None:
        raise DmError("encounter_active", "end the fight before resting: encounter end.")
    for character in party["characters"].values():
        if character["life_state"] == "fallen":
            raise DmError("hero_not_resolved", "%s is fallen. Run grit first." % character["id"])
        if character["life_state"] == "dying":
            raise DmError("character_dying", "%s is dying. Roll death saves, heal, or stabilize first." % character["id"])


def rest_short(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    _require_restable(party, campaign_dir)
    plan = []  # type: List[Tuple[Dict[str, Any], int]]
    for part in party_ops.split_list(args.dice):
        who, sep, count = part.partition(":")
        if not sep or not count.isdigit():
            raise DmError("bad_arguments", "--dice takes id:count pairs, for example --dice kira:1,thorn:2.")
        character = party_ops.require_character(party, who)
        party_ops.require_active(character)
        if int(count) > character["hit_dice"]["remaining"]:
            raise DmError("insufficient_hit_dice", "%s has %d hit dice remaining, tried to spend %d."
                          % (character["id"], character["hit_dice"]["remaining"], int(count)))
        plan.append((character, int(count)))
    entries, results = [], {}
    for character, count in plan:
        con = character["ability_modifiers"]["con"]
        rolls = [dice.roll_hit_die(character["hit_dice"]["die"], rng) for _ in range(count)]
        for value in rolls:
            entries.append(io_campaign.roll_entry("rest_short", {
                "who": character["id"], "kind": "hit_die", "expr": "1" + character["hit_dice"]["die"],
                "rolls": [value], "modifier": con, "total": max(0, value + con)}))
        wanted = sum(max(0, value + con) for value in rolls)
        before = copy.deepcopy(character)
        after = life_states.apply_hp_gain_from_rest(character, wanted)
        after["hit_dice"]["remaining"] -= count
        party["characters"][after["id"]] = after
        gained = after["hp"]["current"] - before["hp"]["current"]
        entries.extend(_hp_entries("rest_short", before, after, {"dice_spent": count}))
        results[after["id"]] = {"dice_spent": count, "rolls": rolls, "hp_gained": gained,
                                "hp": _hp_text(after["hp"]), "life_state": after["life_state"]}
    party_ops.commit(campaign_dir, party, entries)
    return {"results": results}


def rest_long(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    _require_restable(party, campaign_dir)
    entries, results = [], {}
    for cid, character in list(party["characters"].items()):
        if not party_ops.is_active(character):
            continue
        before = copy.deepcopy(character)
        after = life_states.apply_hp_gain_from_rest(character, character["hp"]["max"])
        after["hp"]["temp"] = 0
        # 5e: a long rest restores half of the total hit dice, minimum one.
        restored = min(max(1, after["hit_dice"]["max"] // 2), after["hit_dice"]["max"] - after["hit_dice"]["remaining"])
        after["hit_dice"]["remaining"] += restored
        if after.get("spellcasting"):
            for slot in after["spellcasting"]["slots"].values():
                slot["used"] = 0
        after["grit_used_since_long_rest"] = False
        party["characters"][cid] = after
        entries.extend(_hp_entries("rest_long", before, after, {"hit_dice_restored": restored}))
        results[cid] = {"hp": _hp_text(after["hp"]), "hit_dice_restored": restored,
                        "slots_reset": bool(after.get("spellcasting")), "life_state": after["life_state"]}
    party_ops.commit(campaign_dir, party, entries)
    return {"results": results}


# ---------- item ----------

def _add_line(character: Dict[str, Any], line: Dict[str, Any]) -> None:
    for existing in character["inventory"]:
        if existing["item"] == line["item"]:
            existing["quantity"] += line["quantity"]
            return
    character["inventory"].append(line)


def item_add(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    equipment = data.load_all(skill_root)["equipment"]
    character = party_ops.require_character(party, args.who)
    party_ops.require_active(character)
    _positive(args.qty, "--qty")
    if bool(args.item) == bool(args.name):
        raise DmError("bad_arguments", "give --item <equipment id>, or --name \"free text\" for loot the DM invented.")
    if args.item:
        try:
            record = data.get_record(equipment, "equipment", args.item)
        except DmError as err:
            raise DmError("unknown_name", err.message + " For an item that is not in the data, use --name \"...\".")
        line = {"item": record["id"], "quantity": args.qty}
    else:
        line = {"item": party_ops.slugify(args.name), "quantity": args.qty, "custom": True, "name": args.name,
                "note": args.note or ""}
        if not line["item"]:
            raise DmError("illegal_value", "--name must contain a letter or a number.")
    _add_line(character, line)
    party_ops.commit(campaign_dir, party, [io_campaign.change_entry(
        "item_add", character["id"], "inventory." + line["item"], None, args.qty)])
    return {"who": character["id"], "inventory": character["inventory"]}


def item_remove(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    character = party_ops.require_character(party, args.who)
    _positive(args.qty, "--qty")
    item_id = party_ops.slugify(args.item)
    have = party_ops.inventory_quantity(character, item_id)
    if have < args.qty:
        raise DmError("item_not_in_inventory", "%s has %d of %s, tried to remove %d."
                      % (character["id"], have, item_id, args.qty))
    receiver = None
    if args.give_to:
        receiver = party_ops.require_character(party, args.give_to)
        party_ops.require_active(receiver)
    line = [l for l in character["inventory"] if l["item"] == item_id][0]
    moved = dict(line, quantity=args.qty)
    line["quantity"] -= args.qty
    character["inventory"] = [l for l in character["inventory"] if l["quantity"] > 0]
    # An item that left the pack cannot stay in hand or on the body.
    equipped = character["equipped"]
    left = party_ops.inventory_quantity(character, item_id)
    while equipped["weapons"].count(item_id) > left:
        equipped["weapons"].remove(item_id)
    for slot in ("armor", "shield"):
        if equipped[slot] == item_id and left == 0:
            equipped[slot] = None
    derive.recompute_all(character, records["classes"], records["equipment"])
    entries = [io_campaign.change_entry("item_remove", character["id"], "inventory." + item_id, have, left)]
    if receiver is not None:
        _add_line(receiver, moved)
        entries.append(io_campaign.change_entry("item_remove", receiver["id"], "inventory." + item_id, None, args.qty,
                                                {"from": character["id"]}))
    party_ops.commit(campaign_dir, party, entries)
    return {"who": character["id"], "inventory": character["inventory"], "ac": character["ac"],
            "equipped": character["equipped"]}


# ---------- gold ----------

def _to_cp(text: str) -> int:
    if not _GP.match(text):
        raise DmError("illegal_value", "a gold amount is a positive number of gp with at most 2 decimals, for example 12.5.")
    whole, _, frac = text.partition(".")
    cp = int(whole) * 100 + int((frac + "00")[:2])
    if cp < 1:
        raise DmError("illegal_value", "the amount must be more than 0.")
    return cp


def gold(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    character = party_ops.require_character(party, args.who)
    if bool(args.add) == bool(args.spend):
        raise DmError("bad_arguments", "give exactly one of --add <gp> or --spend <gp>.")
    if args.give_to and not args.spend:
        raise DmError("bad_arguments", "--give-to goes with --spend.")
    before = character["gold_cp"]
    entries = []
    if args.add:
        character["gold_cp"] += _to_cp(args.add)
    else:
        cost = _to_cp(args.spend)
        if cost > before:
            raise DmError("insufficient_gold", "%s has %s gp, tried to spend %s." % (character["id"], gp(before), gp(cost)))
        character["gold_cp"] -= cost
        if args.give_to:
            receiver = party_ops.require_character(party, args.give_to)
            party_ops.require_active(receiver)
            entries.append(io_campaign.change_entry("gold", receiver["id"], "gold_cp", receiver["gold_cp"],
                                                    receiver["gold_cp"] + cost, {"from": character["id"]}))
            receiver["gold_cp"] += cost
    entries.insert(0, io_campaign.change_entry("gold", character["id"], "gold_cp", before, character["gold_cp"]))
    party_ops.commit(campaign_dir, party, entries)
    return {"who": character["id"], "gold_gp": gp(character["gold_cp"])}


# ---------- condition ----------

def _condition(args: argparse.Namespace, add: bool) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    encounter = io_campaign.load_encounter(campaign_dir)
    kind, target = _find_target(party, encounter, args.who)
    name = party_ops.slugify(args.condition)
    if name not in LEGAL_CONDITIONS:
        raise DmError("unknown_condition", "'%s' is not a 5e condition. Legal: %s." % (args.condition, ", ".join(LEGAL_CONDITIONS)))
    before = list(target.setdefault("conditions", []))
    if add:
        if name not in target["conditions"]:
            target["conditions"].append(name)
    else:
        if name not in target["conditions"]:
            raise DmError("condition_not_present", "%s is not %s." % (target["id"], name))
        target["conditions"].remove(name)
    command = "condition_add" if add else "condition_remove"
    entry = io_campaign.change_entry(command, target["id"], "conditions", before, target["conditions"])
    if kind == "monster":
        io_campaign.save_encounter(campaign_dir, encounter)  # type: ignore[arg-type]
        io_campaign.append_log(campaign_dir, [entry])
    else:
        party_ops.commit(campaign_dir, party, [entry])
    return {"who": target["id"], "conditions": target["conditions"]}


def condition_add(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    return _condition(args, True)


def condition_remove(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    return _condition(args, False)


# ---------- deathsave / grit ----------

def deathsave(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    character = party_ops.require_character(party, args.who)
    if character["life_state"] != "dying":
        raise DmError("not_dying", "%s is %s, not dying." % (character["id"], character["life_state"]))
    before = copy.deepcopy(character)
    value = dice.roll_d20(rng)["kept"]
    after, result = life_states.apply_death_save(character, value, party["hero_id"] == character["id"])
    party["characters"][after["id"]] = after
    entries = [io_campaign.roll_entry("deathsave", {"who": after["id"], "kind": "death_save", "expr": "1d20",
                                                    "rolls": [value], "total": value, "result": result})]
    entries.append(io_campaign.change_entry(
        "deathsave", after["id"], "death_saves", before["death_saves"], after["death_saves"],
        {"result": result, "life_state_before": "dying", "life_state_after": after["life_state"],
         "hp_after": after["hp"]["current"]}))
    party_ops.commit(campaign_dir, party, entries)
    out = _state_report(after)
    out.update({"roll": value, "result": result, "successes": after["death_saves"]["successes"],
                "failures": after["death_saves"]["failures"]})
    return out


def grit(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    if not party["hero_id"]:
        raise DmError("not_hero", "there is no hero yet.")
    hero = party["characters"][party["hero_id"]]
    if hero["life_state"] != "fallen":
        raise DmError("not_fallen", "%s is %s, not fallen. The Grit save is only for a hero the 5e rules call dead."
                      % (hero["id"], hero["life_state"]))
    if not 1 <= args.dc <= MAX_GRIT_DC:
        raise DmError("illegal_value", "--dc must be 1 to %d. The base is 10." % MAX_GRIT_DC)
    difficulty = party["settings"]["difficulty"]
    entries = []
    natural = None  # type: Optional[int]
    total = None  # type: Optional[int]
    note = None
    if hero["grit_used_since_long_rest"]:
        note = "the Grit save was already used since the last long rest: no roll, automatic failure"
    else:
        bonus = hero["saves"]["con"]["bonus"]
        natural = dice.roll_d20(rng)["kept"]
        total = natural + bonus
        entries.append(io_campaign.roll_entry("grit", {"who": hero["id"], "kind": "grit_save", "expr": "1d20%+d" % bonus,
                                                       "rolls": [natural], "modifier": bonus, "total": total,
                                                       "target": {"dc": args.dc}}))
    after, outcome = life_states.apply_grit(hero, total, args.dc, difficulty)
    party["characters"][after["id"]] = after
    entries.append(io_campaign.change_entry("grit", after["id"], "life_state", "fallen", after["life_state"],
                                            {"outcome": outcome, "difficulty": difficulty, "dc": args.dc}))
    party_ops.commit(campaign_dir, party, entries)
    out = {"who": after["id"], "roll": natural, "total": total, "dc": args.dc, "difficulty": difficulty,
           "outcome": outcome, "life_state": after["life_state"], "hp": _hp_text(after["hp"])}  # type: Dict[str, Any]
    if note:
        out["note"] = note
    return out
