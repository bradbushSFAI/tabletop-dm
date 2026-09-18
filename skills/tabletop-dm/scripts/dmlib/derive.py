"""Recomputes every stored derived number on a sheet. Pure: dicts in, dicts out.

The model never computes a bonus. It reads these numbers, and dm.py keeps them true.
"""
from typing import Any, Dict, Optional

from .rules_tables import ABILITIES, SKILLS

UNARMORED_BASE_AC = 10
SHIELD_DEFAULT_BONUS = 2
DEFENSE_STYLE_AC = 1
ARCHERY_STYLE_ATTACK = 2
DUELING_STYLE_DAMAGE = 2
SPELL_DC_BASE = 8
PASSIVE_BASE = 10


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(character: Dict[str, Any], classes_data: Dict[str, Any]) -> int:
    return classes_data[character["class"]]["levels"][str(character["level"])]["proficiency_bonus"]


def _with_modifier(dice_expr: str, modifier: int) -> str:
    # A net deals no damage, so there is nothing for a modifier to add to.
    if dice_expr == "0":
        return "0"
    if modifier > 0:
        return "%s+%d" % (dice_expr, modifier)
    if modifier < 0:
        return "%s%d" % (dice_expr, modifier)
    return dice_expr


def derive_saves(character: Dict[str, Any], class_data: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for ability in ABILITIES:
        proficient = ability in class_data["saving_throw_proficiencies"]
        bonus = character["ability_modifiers"][ability] + (character["proficiency_bonus"] if proficient else 0)
        out[ability] = {"proficient": proficient, "bonus": bonus}
    return out


def derive_skills(character: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for skill, ability in SKILLS.items():
        proficient = skill in character["skill_proficiencies"]
        expertise = proficient and skill in character["expertise"]
        bonus = character["ability_modifiers"][ability]
        if proficient:
            bonus += character["proficiency_bonus"] * (2 if expertise else 1)
        out[skill] = {"proficient": proficient, "expertise": expertise, "bonus": bonus}
    return out


def derive_ac(character: Dict[str, Any], equipment_data: Dict[str, Any]) -> int:
    dex = character["ability_modifiers"]["dex"]
    armor_id = character["equipped"]["armor"]
    if armor_id:
        armor = equipment_data[armor_id]
        cap = armor.get("dex_bonus_max")
        ac = armor["armor_class_base"] + (dex if cap is None else min(dex, cap))
        if character.get("fighting_style") == "defense":
            ac += DEFENSE_STYLE_AC
    else:
        ac = UNARMORED_BASE_AC + dex
    shield_id = character["equipped"]["shield"]
    if shield_id:
        ac += equipment_data[shield_id].get("ac_bonus", SHIELD_DEFAULT_BONUS)
    return ac


def is_weapon_proficient(weapon: Dict[str, Any], class_data: Dict[str, Any]) -> bool:
    allowed = class_data["weapon_proficiencies"]
    return weapon["id"] in allowed or weapon["weapon_class"].split("-")[0] in allowed


def derive_attacks(character: Dict[str, Any], class_data: Dict[str, Any],
                   equipment_data: Dict[str, Any]) -> Dict[str, Any]:
    mods = character["ability_modifiers"]
    pb = character["proficiency_bonus"]
    style = character.get("fighting_style")
    weapons = character["equipped"]["weapons"]
    # 5e: an unarmed strike deals 1 + Strength modifier, and everyone is proficient.
    out = {"unarmed": {"attack_bonus": mods["str"] + pb, "damage_expr": str(max(1, 1 + mods["str"])),
                       "damage_type": "bludgeoning", "ability": "str", "proficient": True}}  # type: Dict[str, Any]
    for weapon_id in weapons:
        weapon = equipment_data[weapon_id]
        props = weapon.get("properties", [])
        if "ranged" in props:
            ability = "dex"
        elif "finesse" in props:
            ability = "dex" if mods["dex"] > mods["str"] else "str"
        else:
            ability = "str"
        proficient = is_weapon_proficient(weapon, class_data)
        attack = mods[ability] + (pb if proficient else 0)
        damage_mod = mods[ability]
        if style == "archery" and "ranged" in props:
            attack += ARCHERY_STYLE_ATTACK
        one_handed_melee = "ranged" not in props and "two-handed" not in props
        if style == "dueling" and one_handed_melee and len(weapons) == 1:
            damage_mod += DUELING_STYLE_DAMAGE
        entry = {"attack_bonus": attack, "damage_expr": _with_modifier(weapon["damage_expr"], damage_mod),
                 "damage_type": weapon["damage_type"], "ability": ability, "proficient": proficient,
                 "properties": props}
        if "versatile" in props and not character["equipped"]["shield"] and len(weapons) == 1:
            entry["versatile_damage_expr"] = _with_modifier(weapon["versatile_damage_expr"], mods[ability])
        out[weapon_id] = entry
    return out


def derive_spellcasting(character: Dict[str, Any], class_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rules = class_data.get("spellcasting")
    if not rules:
        return None
    current = character.get("spellcasting") or {}
    level_row = class_data["levels"][str(character["level"])]
    mod = character["ability_modifiers"][rules["ability"]]
    pb = character["proficiency_bonus"]
    old_slots = current.get("slots") or {}
    slots = {}
    for slot_level, maximum in sorted((level_row.get("slots") or {}).items()):
        used = (old_slots.get(slot_level) or {}).get("used", 0)
        slots[slot_level] = {"max": maximum, "used": max(0, min(used, maximum))}
    return {
        "ability": rules["ability"],
        "save_dc": SPELL_DC_BASE + pb + mod,
        "attack_bonus": pb + mod,
        "spellbook": bool(rules.get("spellbook")),
        "cantrips": list(current.get("cantrips") or []),
        "known": current.get("known"),
        "prepared": list(current.get("prepared") or []),
        "prepare_limit": max(1, mod + character["level"]),
        "cantrips_known_limit": level_row.get("cantrips_known", 0),
        "max_spell_level": max([int(k) for k in slots] or [0]),
        "slots": slots,
    }


def recompute_all(character: Dict[str, Any], classes_data: Dict[str, Any],
                  equipment_data: Dict[str, Any]) -> Dict[str, Any]:
    """The one function every mutator calls before it writes a sheet."""
    class_data = classes_data[character["class"]]
    character["ability_modifiers"] = {a: ability_modifier(character["abilities"][a]) for a in ABILITIES}
    character["proficiency_bonus"] = proficiency_bonus(character, classes_data)
    character["saves"] = derive_saves(character, class_data)
    character["skills"] = derive_skills(character)
    character["passive_perception"] = PASSIVE_BASE + character["skills"]["perception"]["bonus"]
    character["ac"] = derive_ac(character, equipment_data)
    character["attacks"] = derive_attacks(character, class_data, equipment_data)
    character["spellcasting"] = derive_spellcasting(character, class_data)
    character["hit_dice"]["max"] = character["level"]
    character["hit_dice"]["remaining"] = min(character["hit_dice"]["remaining"], character["level"])
    return character
