"""roll: the free form (any expression) and the named forms (from a sheet)."""
import argparse
import random
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import dice, io_campaign, party_ops
from .errors import DmError
from .rules_tables import ABILITIES, SKILLS

# "1d20", "1d20+5", "1d20+2-1": the only shape advantage can apply to.
_SINGLE_D20 = re.compile(r"^1d20((?:[+-]\d+)*)$")


def resolve(total: int, natural: Optional[int], dc: Optional[int], ac: Optional[int]) -> Optional[str]:
    """Success or failure against a DC. Hit or miss against an AC (5e: natural 20 and 1)."""
    if ac is not None:
        if natural == 20:
            return "critical_hit"
        if natural == 1:
            return "miss"
        return "hit" if total >= ac else "miss"
    if dc is not None:
        return "success" if total >= dc else "failure"
    return None


def roll_with_d20_rules(expr: str, rng: random.Random, adv: bool, disadv: bool) -> Dict[str, Any]:
    """Roll an expression. A lone d20 also reports its natural value and honours advantage."""
    text = expr.replace(" ", "").lower()
    match = _SINGLE_D20.match(text)
    if not match:
        if adv or disadv:
            raise DmError(
                "advantage_invalid_for_expression",
                "advantage and disadvantage only apply to a single d20 roll, not to '%s'." % expr,
            )
        return dice.roll_expression(expr, rng)
    modifier = dice.roll_expression(match.group(1) or "0", rng)["total"] if match.group(1) else 0
    d20 = dice.roll_d20(rng, advantage=adv, disadvantage=disadv)
    return {
        "expr": expr.strip(),
        "dice": [{"term": "1d20", "rolls": d20["rolls"], "kept": [d20["kept"]]}],
        "modifier": modifier,
        "total": d20["kept"] + modifier,
        "d20": d20,
        "natural": d20["kept"],
    }


def roll(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    forms = [name for name in NAMED_FORMS if getattr(args, name)]
    if len(forms) + (1 if args.expr else 0) > 1:
        raise DmError("bad_arguments", "one roll at a time: an expression, or one of --attack, --check, "
                                       "--save, --initiative, --spell-attack.")
    if not forms:
        if not args.expr:
            raise DmError("bad_arguments", "give a dice expression, for example: roll 2d6+3")
        out = roll_with_d20_rules(args.expr, rng, args.adv, args.disadv)
        return finish(campaign_dir, out, args, who=args.who, kind="free")
    if not args.who:
        raise DmError("bad_arguments", "a named roll needs --who <id>, so the bonus can come from the sheet.")
    character = party_ops.require_character(party, args.who)
    modifier, kind, extra = named_modifier(character, forms[0], getattr(args, forms[0]))
    out = roll_with_d20_rules("1d20%+d" % modifier, rng, args.adv, args.disadv)
    out.update(extra)
    return finish(campaign_dir, out, args, who=character["id"], kind=kind)


NAMED_FORMS = ("attack", "check", "save", "initiative", "spell_attack")


def named_modifier(character: Dict[str, Any], form: str, value: Any) -> Tuple[int, str, Dict[str, Any]]:
    """The modifier the sheet gives for a named roll. The model never computes one."""
    if form == "attack":
        weapon = party_ops.slugify(value)
        if weapon not in character["attacks"]:
            raise DmError("unknown_weapon", "%s is not in %s's hands. Ready to use: %s. Use equip first."
                          % (value, character["id"], ", ".join(sorted(character["attacks"]))))
        attack = character["attacks"][weapon]
        extra = {"damage_expr": attack["damage_expr"], "damage_type": attack["damage_type"]}
        if "versatile_damage_expr" in attack:
            extra["versatile_damage_expr"] = attack["versatile_damage_expr"]
        return attack["attack_bonus"], "attack:" + weapon, extra
    if form == "check":
        name = party_ops.slugify(value)
        if name in SKILLS:
            return character["skills"][name]["bonus"], "check:" + name, {}
        if name in ABILITIES:
            return character["ability_modifiers"][name], "check:" + name, {}
        raise DmError("unknown_skill", "'%s' is not a skill or an ability. Skills: %s." % (value, ", ".join(sorted(SKILLS))))
    if form == "save":
        name = party_ops.slugify(value)
        if name not in ABILITIES:
            raise DmError("unknown_skill", "a save takes an ability: %s." % ", ".join(ABILITIES))
        return character["saves"][name]["bonus"], "save:" + name, {}
    if form == "initiative":
        return character["ability_modifiers"]["dex"], "initiative", {}
    casting = character.get("spellcasting")
    if not casting:
        raise DmError("not_a_caster", "%s casts no spells." % character["id"])
    return casting["attack_bonus"], "spell_attack", {"save_dc": casting["save_dc"]}


def finish(campaign_dir: Path, out: Dict[str, Any], args: argparse.Namespace,
           who: Optional[str], kind: str) -> Dict[str, Any]:
    """Add the target and result, log the roll, and return the output."""
    if args.dc is not None:
        out["target"] = {"dc": args.dc}
    elif args.ac is not None:
        out["target"] = {"ac": args.ac}
    result = resolve(out["total"], out.get("natural"), args.dc, args.ac)
    if result is not None:
        out["result"] = result
    if args.reason:
        out["reason"] = args.reason
    payload = dict(out)
    payload["who"] = who
    payload["kind"] = kind
    io_campaign.append_log(campaign_dir, [io_campaign.roll_entry("roll", payload)])
    return out
