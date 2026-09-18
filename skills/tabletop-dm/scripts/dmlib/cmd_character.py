"""character create / asi / retire / promote, equip, unequip, spells prepare / learn, xp."""
import argparse
import copy
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import data, derive, dice, io_campaign, party_ops
from .errors import DmError
from .rules_tables import (ABILITIES, ABILITY_SCORE_CAP, MAX_ACTIVE_PARTY, MAX_LEVEL, SKILLS,
                           STANDARD_ARRAY, XP_THRESHOLDS)

ASI_FEATURE = "ability-score-improvement"
ASI_POINTS = 2
BACKGROUND_SKILL_COUNT = 2
MIN_START_SCORE = 3
MAX_START_SCORE = 18
MAX_HANDS = 2


# ---------- shared pieces ----------

def _hit_die_sides(class_data: Dict[str, Any]) -> int:
    return int(class_data["hit_die"].lstrip("d"))


def _average_hp_gain(class_data: Dict[str, Any]) -> int:
    """The 5e fixed value: half the hit die, plus one."""
    return _hit_die_sides(class_data) // 2 + 1


def _max_spell_level(class_data: Dict[str, Any], level: int) -> int:
    slots = class_data["levels"][str(level)].get("slots") or {}
    return max([int(k) for k in slots] or [0])


def _spell_ok(spell: Dict[str, Any], class_id: str, max_level: int, cantrip: bool) -> bool:
    if class_id not in spell["classes"]:
        return False
    return spell["level"] == 0 if cantrip else 1 <= spell["level"] <= max_level


def _fill(chosen: List[str], defaults: List[str], spells: Dict[str, Any], class_id: str,
          max_level: int, cantrip: bool, count: int) -> List[str]:
    """Top a pick list up to count: class defaults first, then lowest level, then name."""
    out = list(chosen)
    pool = [sid for sid in defaults if sid in spells and _spell_ok(spells[sid], class_id, max_level, cantrip)]
    rest = sorted((s["level"], sid) for sid, s in spells.items() if _spell_ok(s, class_id, max_level, cantrip))
    for sid in pool + [sid for _, sid in rest]:
        if len(out) >= count:
            break
        if sid not in out:
            out.append(sid)
    return out[:count]


def _check_spell_picks(picks: List[str], spells: Dict[str, Any], class_id: str, max_level: int,
                       cantrip: bool, limit: int, code: str) -> None:
    word = "cantrip" if cantrip else "spell"
    if len(set(picks)) != len(picks):
        raise DmError(code, "a %s was named twice." % word)
    if len(picks) > limit:
        raise DmError(code, "at most %d %ss allowed here, got %d." % (limit, word, len(picks)))
    for sid in picks:
        if sid not in spells:
            raise DmError(code, "no spell '%s' in the data. Use lookup spell --list." % sid)
        if not _spell_ok(spells[sid], class_id, max_level, cantrip):
            raise DmError(code, "%s is not a legal %s pick for a %s who casts up to level %d."
                          % (sid, word, class_id, max_level))


# ---------- character create ----------

def _parse_scores(args: argparse.Namespace, class_data: Dict[str, Any]) -> Dict[str, int]:
    if args.scores is None:
        if args.quick:
            return dict(class_data["quick_scores"])
        raise DmError("illegal_ability_scores",
                      "give --scores as six numbers in str,dex,con,int,wis,cha order, or use --quick.")
    parts = [p.strip() for p in args.scores.split(",")]
    if len(parts) != len(ABILITIES) or not all(p.isdigit() for p in parts):
        raise DmError("illegal_ability_scores", "6 whole numbers required, in str,dex,con,int,wis,cha order.")
    values = [int(p) for p in parts]
    if not all(MIN_START_SCORE <= v <= MAX_START_SCORE for v in values):
        raise DmError("illegal_ability_scores", "each starting score must be %d to %d." % (MIN_START_SCORE, MAX_START_SCORE))
    if args.standard_array and sorted(values) != sorted(STANDARD_ARRAY):
        raise DmError("illegal_ability_scores", "the standard array is %s, in any order."
                      % ",".join(str(v) for v in STANDARD_ARRAY))
    return dict(zip(ABILITIES, values))


def _pick_skills(args: argparse.Namespace, class_data: Dict[str, Any]) -> List[str]:
    need_class = class_data["skill_choices"]["count"]
    if not args.skills:
        return list(class_data["default_skills"]) + list(class_data["default_background_skills"])
    picks = party_ops.split_list(args.skills)
    total = need_class + BACKGROUND_SKILL_COUNT
    unknown = [s for s in picks if s not in SKILLS]
    if unknown:
        raise DmError("illegal_skill_pick", "unknown skill: %s. Legal: %s." % (", ".join(unknown), ", ".join(sorted(SKILLS))))
    if len(set(picks)) != len(picks) or len(picks) != total:
        raise DmError("illegal_skill_pick", "pick exactly %d different skills (%d class + %d background)."
                      % (total, need_class, BACKGROUND_SKILL_COUNT))
    from_class = [s for s in picks if s in class_data["skill_choices"]["options"]]
    if len(from_class) < need_class:
        raise DmError("illegal_skill_pick", "at least %d picks must come from the class list: %s."
                      % (need_class, ", ".join(class_data["skill_choices"]["options"])))
    return picks


def _pick_expertise(args: argparse.Namespace, class_data: Dict[str, Any], level: int, skills: List[str]) -> List[str]:
    rule = class_data.get("expertise")
    if not rule or level < rule["level"]:
        return []
    if not args.expertise:
        picks = [s for s in rule["default"] if s in skills]
        return (picks + [s for s in skills if s not in picks])[:rule["count"]]
    picks = party_ops.split_list(args.expertise)
    if len(set(picks)) != rule["count"] or not all(s in skills for s in picks):
        raise DmError("illegal_skill_pick", "expertise needs exactly %d of the character's own skills." % rule["count"])
    return picks


def create(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    class_id = (args.char_class or "").lower()
    if class_id not in records["classes"]:
        raise DmError("unknown_class", "no class '%s'. Legal: %s." % (args.char_class, ", ".join(sorted(records["classes"]))))
    class_data = records["classes"][class_id]
    cid = party_ops.slugify(args.id or args.name)
    if not cid:
        raise DmError("illegal_value", "the name must contain a letter or a number.")
    if cid in party["characters"]:
        raise DmError("id_taken", "there is already a character '%s'. Pick another --id." % cid)
    if len(party_ops.active_characters(party)) >= MAX_ACTIVE_PARTY:
        raise DmError("party_full", "the party is a hero plus at most %d companions." % (MAX_ACTIVE_PARTY - 1))
    level = args.level
    if not 1 <= level <= MAX_LEVEL:
        raise DmError("illegal_value", "level must be 1 to %d." % MAX_LEVEL)
    abilities = _parse_scores(args, class_data)
    skills = _pick_skills(args, class_data)
    expertise = _pick_expertise(args, class_data, level, skills)
    style = None
    if class_data.get("fighting_styles"):
        style = (args.fighting_style or class_data["default_fighting_style"]).lower()
        if style not in class_data["fighting_styles"]:
            raise DmError("illegal_value", "fighting style must be one of %s." % ", ".join(class_data["fighting_styles"]))

    features = []  # type: List[str]
    pending_asi = 0
    for lvl in range(1, level + 1):
        for feature in class_data["levels"][str(lvl)]["features"]:
            if feature["id"] == ASI_FEATURE:
                pending_asi += 1
            elif feature["id"] not in features:
                features.append(feature["id"])

    con_mod = derive.ability_modifier(abilities["con"])
    hp_max = _hit_die_sides(class_data) + con_mod
    # Levels granted at creation use the fixed average: deterministic, no dice for paperwork.
    hp_max += sum(max(1, _average_hp_gain(class_data) + con_mod) for _ in range(level - 1))
    hp_max = max(1, hp_max)

    casting = None  # type: Optional[Dict[str, Any]]
    rules = class_data.get("spellcasting")
    if rules:
        casting = _starting_spells(args, rules, class_data, class_id, level, abilities, records["spells"])

    character = {
        "id": cid, "name": args.name, "class": class_id, "level": level, "xp": XP_THRESHOLDS[level],
        "background": args.background or "", "bond": args.bond or "", "flaw": args.flaw or "",
        "abilities": abilities, "skill_proficiencies": skills, "expertise": expertise,
        "fighting_style": style, "features": features,
        "pending_asi": pending_asi, "pending_spell_picks": 0, "pending_cantrip_picks": 0,
        "hp": {"current": hp_max, "max": hp_max, "temp": 0},
        "hit_dice": {"die": class_data["hit_die"], "max": level, "remaining": level},
        "life_state": "alive", "death_saves": {"successes": 0, "failures": 0},
        "grit_used_since_long_rest": False, "conditions": [],
        "spellcasting": casting,
        "equipped": copy.deepcopy(class_data["starting_equipped"]),
        "inventory": copy.deepcopy(class_data["starting_equipment"]),
        "gold_cp": class_data["starting_gold_cp"],
    }
    derive.recompute_all(character, records["classes"], records["equipment"])
    party["characters"][cid] = character
    became_hero = party["hero_id"] is None
    if became_hero:
        party["hero_id"] = cid
    entries = [io_campaign.change_entry("character_create", cid, "characters." + cid, None,
                                        {"class": class_id, "level": level, "hero": became_hero})]
    party_ops.commit(campaign_dir, party, entries)
    return {"character": character, "is_hero": became_hero}


def _starting_spells(args: argparse.Namespace, rules: Dict[str, Any], class_data: Dict[str, Any], class_id: str,
                     level: int, abilities: Dict[str, int], spells: Dict[str, Any]) -> Dict[str, Any]:
    max_level = _max_spell_level(class_data, level)
    cantrip_count = class_data["levels"][str(level)].get("cantrips_known", 0)
    cantrips = party_ops.split_list(args.cantrips)
    _check_spell_picks(cantrips, spells, class_id, max_level, True, cantrip_count, "illegal_spell_pick")
    cantrips = _fill(cantrips, rules.get("default_cantrips", []), spells, class_id, max_level, True, cantrip_count)
    limit = max(1, derive.ability_modifier(abilities[rules["ability"]]) + level)
    picks = party_ops.split_list(args.spells)
    if rules.get("spellbook"):
        book_size = rules["spellbook_start"] + rules["spellbook_per_level"] * (level - 1)
        _check_spell_picks(picks, spells, class_id, max_level, False, book_size, "illegal_spell_pick")
        known = _fill(picks, rules.get("default_spells", []), spells, class_id, max_level, False, book_size)
        return {"cantrips": cantrips, "known": known, "prepared": known[:limit], "slots": {}}
    _check_spell_picks(picks, spells, class_id, max_level, False, limit, "illegal_spell_pick")
    prepared = picks or _fill([], rules.get("default_spells", []), spells, class_id, max_level, False, limit)
    return {"cantrips": cantrips, "known": None, "prepared": prepared[:limit], "slots": {}}


# ---------- character asi ----------

def asi(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    character = party_ops.require_character(party, args.who)
    party_ops.require_active(character)
    if character.get("pending_asi", 0) < 1:
        raise DmError("no_pending_asi", "%s has no ability score improvement waiting." % character["id"])
    increases = {}  # type: Dict[str, int]
    for part in party_ops.split_list(args.increase):
        ability, sep, amount = part.partition(":")
        if ability not in ABILITIES or not sep or not amount.isdigit() or int(amount) < 1 or ability in increases:
            raise DmError("illegal_value", "--increase takes ability:points, for example str:2 or str:1,dex:1.")
        increases[ability] = int(amount)
    if sum(increases.values()) != ASI_POINTS:
        raise DmError("illegal_value", "an improvement is exactly %d points: one ability +2, or two abilities +1." % ASI_POINTS)
    for ability, amount in increases.items():
        if character["abilities"][ability] + amount > ABILITY_SCORE_CAP:
            raise DmError("illegal_value", "%s would pass %d." % (ability, ABILITY_SCORE_CAP))
    before = dict(character["abilities"])
    old_con = derive.ability_modifier(character["abilities"]["con"])
    for ability, amount in increases.items():
        character["abilities"][ability] += amount
    # A higher Constitution modifier raises hit points for every level already gained (5e).
    delta = (derive.ability_modifier(character["abilities"]["con"]) - old_con) * character["level"]
    character["hp"]["max"] += delta
    character["hp"]["current"] += delta
    character["pending_asi"] -= 1
    derive.recompute_all(character, records["classes"], records["equipment"])
    entries = [io_campaign.change_entry("character_asi", character["id"], "abilities", before, dict(character["abilities"]))]
    party_ops.commit(campaign_dir, party, entries)
    return {"who": character["id"], "abilities": character["abilities"], "hp": character["hp"],
            "pending_asi": character["pending_asi"]}


# ---------- equip / unequip ----------

def _slot_of(item: Dict[str, Any]) -> Optional[str]:
    if item["category"] == "weapon":
        return "weapon"
    if item["category"] == "armor":
        return "shield" if item.get("armor_type") == "shield" else "armor"
    return None


def _hands_used(equipped: Dict[str, Any], equipment: Dict[str, Any]) -> int:
    hands = 1 if equipped["shield"] else 0
    for weapon_id in equipped["weapons"]:
        hands += 2 if "two-handed" in equipment[weapon_id].get("properties", []) else 1
    return hands


def _equip_result(character: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
    out = {"who": character["id"], "equipped": character["equipped"], "ac": character["ac"],
           "attacks": character["attacks"]}  # type: Dict[str, Any]
    if warnings:
        out["warnings"] = warnings
    return out


def equip(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    character = party_ops.require_character(party, args.who)
    party_ops.require_active(character)
    item_id = party_ops.slugify(args.item)
    equipped = character["equipped"]
    item = records["equipment"].get(item_id)
    if item is not None and _slot_of(item) != args.slot:
        raise DmError("wrong_slot", "%s cannot go in the %s slot." % (item_id, args.slot))
    wielded = equipped["weapons"].count(item_id)
    if party_ops.inventory_quantity(character, item_id) <= wielded:
        raise DmError("item_not_in_inventory", "%s is not in %s's inventory (or every one is already in hand)."
                      % (item_id, character["id"]))
    if item is None:
        raise DmError("wrong_slot", "%s is not in the equipment data, so it has no numbers to equip." % item_id)
    before = copy.deepcopy(equipped)
    trial = copy.deepcopy(equipped)
    if args.slot == "weapon":
        trial["weapons"].append(item_id)
    else:
        trial[args.slot] = item_id
    if _hands_used(trial, records["equipment"]) > MAX_HANDS:
        raise DmError("hands_full", "%s has only two hands. Unequip a weapon or the shield first." % character["id"])
    class_data = records["classes"][character["class"]]
    warnings = []
    if args.slot == "weapon" and not derive.is_weapon_proficient(item, class_data):
        warnings.append("%s is not proficient with %s" % (character["id"], item_id))
    if args.slot != "weapon" and item["armor_type"] not in class_data["armor_proficiencies"]:
        warnings.append("%s is not proficient with %s" % (character["id"], item_id))
    character["equipped"] = trial
    derive.recompute_all(character, records["classes"], records["equipment"])
    entries = [io_campaign.change_entry("equip", character["id"], "equipped", before, trial, {"ac": character["ac"]})]
    party_ops.commit(campaign_dir, party, entries)
    return _equip_result(character, warnings)


def unequip(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    character = party_ops.require_character(party, args.who)
    equipped = character["equipped"]
    before = copy.deepcopy(equipped)
    if args.slot == "weapon":
        weapons = equipped["weapons"]
        item_id = party_ops.slugify(args.item) if args.item else (weapons[0] if len(weapons) == 1 else None)
        if item_id is None and weapons:
            raise DmError("bad_arguments", "name the weapon with --item. In hand: %s." % ", ".join(weapons))
        if item_id not in weapons:
            raise DmError("nothing_equipped", "%s is not wielding %s." % (character["id"], item_id or "a weapon"))
        weapons.remove(item_id)
    else:
        if not equipped[args.slot]:
            raise DmError("nothing_equipped", "%s has nothing in the %s slot." % (character["id"], args.slot))
        equipped[args.slot] = None
    derive.recompute_all(character, records["classes"], records["equipment"])
    entries = [io_campaign.change_entry("unequip", character["id"], "equipped", before, equipped, {"ac": character["ac"]})]
    party_ops.commit(campaign_dir, party, entries)
    return _equip_result(character, [])


# ---------- spells ----------

def _require_caster(character: Dict[str, Any]) -> Dict[str, Any]:
    if not character.get("spellcasting"):
        raise DmError("not_a_caster", "%s is a %s and casts no spells." % (character["id"], character["class"]))
    return character["spellcasting"]


def spells_prepare(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    character = party_ops.require_character(party, args.who)
    party_ops.require_active(character)
    casting = _require_caster(character)
    picks = party_ops.split_list(args.spells)
    if len(picks) > casting["prepare_limit"]:
        raise DmError("too_many_spells_prepared", "level %d %s can prepare %d, tried %d."
                      % (character["level"], character["class"], casting["prepare_limit"], len(picks)))
    if len(set(picks)) != len(picks):
        raise DmError("spell_not_available", "a spell was named twice.")
    for sid in picks:
        spell = records["spells"].get(sid)
        legal = spell is not None and _spell_ok(spell, character["class"], casting["max_spell_level"], False)
        if legal and casting["known"] is not None:
            legal = sid in casting["known"]
        if not legal:
            where = "in the spellbook" if casting["known"] is not None else "on the class list at a castable level"
            raise DmError("spell_not_available", "%s is not %s for %s." % (sid, where, character["id"]))
    before = list(casting["prepared"])
    casting["prepared"] = picks
    entries = [io_campaign.change_entry("spells_prepare", character["id"], "spellcasting.prepared", before, picks)]
    party_ops.commit(campaign_dir, party, entries)
    return {"who": character["id"], "prepared": picks, "prepare_limit": casting["prepare_limit"]}


def spells_learn(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    """Spend the picks a level-up granted: new cantrips, and new spellbook spells."""
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    character = party_ops.require_character(party, args.who)
    party_ops.require_active(character)
    casting = _require_caster(character)
    picks = party_ops.split_list(args.spells)
    if not picks or len(set(picks)) != len(picks):
        raise DmError("spell_not_available", "name one or more different spells with --spells.")
    new_cantrips, new_spells = [], []
    for sid in picks:
        spell = records["spells"].get(sid)
        if spell is None:
            raise DmError("spell_not_available", "no spell '%s' in the data." % sid)
        cantrip = spell["level"] == 0
        if not _spell_ok(spell, character["class"], casting["max_spell_level"], cantrip):
            raise DmError("spell_not_available", "%s is not a %s spell of a level %s can cast."
                          % (sid, character["class"], character["id"]))
        (new_cantrips if cantrip else new_spells).append(sid)
    if len(new_cantrips) > character.get("pending_cantrip_picks", 0) or len(new_spells) > character.get("pending_spell_picks", 0):
        raise DmError("no_pending_picks", "%s has %d cantrip picks and %d spell picks waiting."
                      % (character["id"], character.get("pending_cantrip_picks", 0), character.get("pending_spell_picks", 0)))
    for sid in picks:
        if sid in casting["cantrips"] or sid in (casting["known"] or []):
            raise DmError("spell_not_available", "%s already knows %s." % (character["id"], sid))
    casting["cantrips"].extend(new_cantrips)
    if new_spells:
        casting["known"].extend(new_spells)
    character["pending_cantrip_picks"] -= len(new_cantrips)
    character["pending_spell_picks"] -= len(new_spells)
    entries = [io_campaign.change_entry("spells_learn", character["id"], "spellcasting", None,
                                        {"cantrips": new_cantrips, "spells": new_spells})]
    party_ops.commit(campaign_dir, party, entries)
    return {"who": character["id"], "cantrips": casting["cantrips"], "known": casting["known"],
            "pending_cantrip_picks": character["pending_cantrip_picks"],
            "pending_spell_picks": character["pending_spell_picks"]}


# ---------- xp ----------

def award_xp(character: Dict[str, Any], amount: int, records: Dict[str, Any], rng: random.Random,
             command: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Add XP and apply every level-up it earns. Returns (level_up summary or None, log entries)."""
    class_data = records["classes"][character["class"]]
    entries = []  # type: List[Dict[str, Any]]
    xp_before, level_before = character["xp"], character["level"]
    character["xp"] += amount
    gained_features = []  # type: List[str]
    hp_before = character["hp"]["max"]
    while character["level"] < MAX_LEVEL and character["xp"] >= XP_THRESHOLDS[character["level"] + 1]:
        old_row = class_data["levels"][str(character["level"])]
        character["level"] += 1
        row = class_data["levels"][str(character["level"])]
        rolled = dice.roll_hit_die(class_data["hit_die"], rng)
        gain = max(1, rolled + derive.ability_modifier(character["abilities"]["con"]))
        entries.append(io_campaign.roll_entry(command, {"who": character["id"], "kind": "level_up_hit_die",
                                                        "expr": "1" + class_data["hit_die"], "rolls": [rolled],
                                                        "total": gain, "level": character["level"]}))
        character["hp"]["max"] += gain
        character["hp"]["current"] += gain
        character["hit_dice"]["remaining"] += 1
        for feature in row["features"]:
            if feature["id"] == ASI_FEATURE:
                character["pending_asi"] = character.get("pending_asi", 0) + 1
                gained_features.append(ASI_FEATURE)
            elif feature["id"] not in character["features"]:
                character["features"].append(feature["id"])
                gained_features.append(feature["id"])
        rules = class_data.get("spellcasting")
        if rules:
            more_cantrips = row.get("cantrips_known", 0) - old_row.get("cantrips_known", 0)
            character["pending_cantrip_picks"] = character.get("pending_cantrip_picks", 0) + max(0, more_cantrips)
            if rules.get("spellbook"):
                character["pending_spell_picks"] = character.get("pending_spell_picks", 0) + rules["spellbook_per_level"]
    derive.recompute_all(character, records["classes"], records["equipment"])
    details = {"level_before": level_before, "level_after": character["level"]}
    entries.append(io_campaign.change_entry(command, character["id"], "xp", xp_before, character["xp"], details))
    if character["level"] == level_before:
        return None, entries
    summary = {"from": level_before, "to": character["level"], "hp_max": "%d->%d" % (hp_before, character["hp"]["max"]),
               "features_gained": gained_features, "pending_asi": character.get("pending_asi", 0),
               "pending_spell_picks": character.get("pending_spell_picks", 0),
               "pending_cantrip_picks": character.get("pending_cantrip_picks", 0)}
    return summary, entries


def xp(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    records = data.load_all(skill_root)
    character = party_ops.require_character(party, args.who)
    party_ops.require_active(character)
    if args.amount < 1:
        raise DmError("illegal_value", "--amount must be 1 or more.")
    if character["level"] >= MAX_LEVEL:
        raise DmError("level_cap_reached", "%s is already level %d. This build supports no higher level."
                      % (character["id"], MAX_LEVEL))
    summary, entries = award_xp(character, args.amount, records, rng, "xp")
    party_ops.commit(campaign_dir, party, entries)
    out = {"who": character["id"], "xp": character["xp"], "level": character["level"]}  # type: Dict[str, Any]
    if character["level"] < MAX_LEVEL:
        out["next_level_at"] = XP_THRESHOLDS[character["level"] + 1]
    if summary:
        out["level_up"] = summary
    return out


# ---------- retire / promote ----------

def retire(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    character = party_ops.require_character(party, args.who)
    party_ops.require_active(character)
    is_hero = party["hero_id"] == character["id"]
    if is_hero and args.status == "dead" and not args.player_accepted:
        raise DmError("hero_death_needs_confirmation",
                      "retiring the hero as dead needs --player-accepted, in every difficulty. Ask the player first.")
    before = character["life_state"]
    character["life_state"] = args.status
    party_ops.commit(campaign_dir, party, [io_campaign.change_entry(
        "character_retire", character["id"], "life_state", before, args.status,
        {"hero": is_hero, "player_accepted": bool(args.player_accepted)})])
    out = {"who": character["id"], "life_state": args.status}  # type: Dict[str, Any]
    if is_hero:
        out["next"] = "the campaign ends, or the player continues: character promote <companion>, or character create then promote"
    return out


def promote(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    character = party_ops.require_character(party, args.id)
    old = party["hero_id"]
    if old and party_ops.is_active(party["characters"][old]):
        raise DmError("promotion_not_allowed", "%s is still the hero and is %s. There is exactly one hero."
                      % (old, party["characters"][old]["life_state"]))
    party_ops.require_active(character)
    party["hero_id"] = character["id"]
    party_ops.commit(campaign_dir, party, [io_campaign.change_entry("character_promote", character["id"], "hero_id", old, character["id"])])
    return {"hero_id": character["id"], "previous_hero": old}
