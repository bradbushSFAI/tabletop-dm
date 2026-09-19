"""Argument parsing and dispatch. Prints exactly one compact JSON line per run."""
import argparse
import json
import random
from pathlib import Path
from typing import Any, Callable, Dict, List

from . import (cmd_character, cmd_encounter, cmd_log, cmd_lookup, cmd_play, cmd_roll, cmd_seed, cmd_setup, data,
               io_campaign)
from .errors import DmError, error_envelope, success_envelope

Handler = Callable[[argparse.Namespace, Path, random.Random], Dict[str, Any]]

HANDLERS = {
    "version": cmd_setup.version,
    "init": cmd_setup.init,
    "settings set": cmd_setup.settings_set,
    "status": cmd_setup.status,
    "roll": cmd_roll.roll,
    "sheet": cmd_setup.sheet,
    "lookup": cmd_lookup.lookup,
    "character create": cmd_character.create,
    "character asi": cmd_character.asi,
    "equip": cmd_character.equip,
    "unequip": cmd_character.unequip,
    "spells prepare": cmd_character.spells_prepare,
    "spells learn": cmd_character.spells_learn,
    "xp": cmd_character.xp,
    "character retire": cmd_character.retire,
    "character promote": cmd_character.promote,
    "damage": cmd_play.damage,
    "heal": cmd_play.heal,
    "stabilize": cmd_play.stabilize,
    "cast": cmd_play.cast,
    "rest short": cmd_play.rest_short,
    "rest long": cmd_play.rest_long,
    "item add": cmd_play.item_add,
    "item remove": cmd_play.item_remove,
    "gold": cmd_play.gold,
    "condition add": cmd_play.condition_add,
    "condition remove": cmd_play.condition_remove,
    "deathsave": cmd_play.deathsave,
    "grit": cmd_play.grit,
    "encounter start": cmd_encounter.start,
    "encounter add": cmd_encounter.add,
    "encounter next": cmd_encounter.next_turn,
    "encounter end": cmd_encounter.end,
    "encounter flee": cmd_encounter.flee,
    "character set": cmd_character.set_hooks,
    "track": cmd_play.track,
    "beat": cmd_log.beat,
    "recent": cmd_log.recent,
    "seed list": cmd_seed.seed_list,
    "seed choose": cmd_seed.seed_choose,
    "seed pick": cmd_seed.seed_pick,
}  # type: Dict[str, Handler]


class _Parser(argparse.ArgumentParser):
    """argparse prints usage and exits. The model needs a JSON error instead."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise DmError("bad_arguments", "%s. Usage: %s" % (message, self.format_usage().strip()))

    def exit(self, status: int = 0, message: Any = None) -> None:  # type: ignore[override]
        raise DmError("bad_arguments", (message or "see the command table in SKILL.md").strip())


def _leaf(sub: Any, name: str, key: str, campaign: bool = True) -> argparse.ArgumentParser:
    parser = sub.add_parser(name, add_help=False)
    parser.set_defaults(handler_key=key)
    if campaign:
        parser.add_argument("--campaign", required=True)
    return parser


def _group(sub: Any, name: str) -> Any:
    parser = sub.add_parser(name, add_help=False)
    return parser.add_subparsers(dest=name + "_command", parser_class=_Parser, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="dm.py", add_help=False)
    sub = parser.add_subparsers(dest="command", parser_class=_Parser, required=True)

    _leaf(sub, "init", "init")
    _leaf(sub, "status", "status")

    settings = _group(sub, "settings")
    p = _leaf(settings, "set", "settings set")
    p.add_argument("--difficulty")
    p.add_argument("--content-level", dest="content_level")
    p.add_argument("--tone", action="append")

    p = _leaf(sub, "roll", "roll")
    p.add_argument("expr", nargs="?")
    p.add_argument("--adv", action="store_true")
    p.add_argument("--disadv", action="store_true")
    p.add_argument("--dc", type=int)
    p.add_argument("--ac", type=int)
    p.add_argument("--reason")
    p.add_argument("--who")
    p.add_argument("--attack")
    p.add_argument("--check")
    p.add_argument("--proficient", action="store_true")
    p.add_argument("--bonus")
    p.add_argument("--save")
    p.add_argument("--initiative", action="store_true")
    p.add_argument("--spell-attack", dest="spell_attack", action="store_true")

    p = _leaf(sub, "sheet", "sheet")
    p.add_argument("id")

    p = _leaf(sub, "lookup", "lookup", campaign=False)
    p.add_argument("kind", choices=["class", "spell", "monster", "equipment"])
    p.add_argument("name", nargs="?")
    p.add_argument("--list", action="store_true")
    p.add_argument("--level", type=int)
    p.add_argument("--class", dest="char_class")
    p.add_argument("--cr", type=float)

    character = _group(sub, "character")
    p = _leaf(character, "create", "character create")
    p.add_argument("--id")
    p.add_argument("--name", required=True)
    p.add_argument("--class", dest="char_class", required=True)
    p.add_argument("--scores")
    p.add_argument("--standard-array", dest="standard_array", action="store_true")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--level", type=int, default=1)
    p.add_argument("--skills")
    p.add_argument("--expertise")
    p.add_argument("--fighting-style", dest="fighting_style")
    p.add_argument("--cantrips")
    p.add_argument("--spells")
    p.add_argument("--background")
    p.add_argument("--bond")
    p.add_argument("--flaw")
    p = _leaf(character, "asi", "character asi")
    p.add_argument("--who", required=True)
    p.add_argument("--increase", required=True)

    for name in ("equip", "unequip"):
        p = _leaf(sub, name, name)
        p.add_argument("--who", required=True)
        p.add_argument("--slot", required=True, choices=["armor", "shield", "weapon"])
        p.add_argument("--item", required=(name == "equip"))

    spells = _group(sub, "spells")
    for name in ("prepare", "learn"):
        p = _leaf(spells, name, "spells " + name)
        p.add_argument("--who", required=True)
        p.add_argument("--spells", required=True)

    p = _leaf(sub, "xp", "xp")
    p.add_argument("--who")
    p.add_argument("--party", action="store_true")
    p.add_argument("--amount", type=int, required=True)

    p = _leaf(character, "retire", "character retire")
    p.add_argument("--who", required=True)
    p.add_argument("--status", required=True, choices=["dead", "departed"])
    p.add_argument("--player-accepted", dest="player_accepted", action="store_true")
    p = _leaf(character, "promote", "character promote")
    p.add_argument("id")

    for name in ("damage", "heal"):
        p = _leaf(sub, name, name)
        p.add_argument("--who", required=True)
        p.add_argument("--amount", type=int, required=True)
        if name == "damage":
            p.add_argument("--crit", action="store_true")
        else:
            p.add_argument("--temp", action="store_true")
    p = _leaf(sub, "stabilize", "stabilize")
    p.add_argument("--who", required=True)

    p = _leaf(sub, "cast", "cast")
    p.add_argument("--who", required=True)
    p.add_argument("--spell", required=True)
    p.add_argument("--slot", type=int)

    rest = _group(sub, "rest")
    p = _leaf(rest, "short", "rest short")
    p.add_argument("--dice")
    _leaf(rest, "long", "rest long")

    item = _group(sub, "item")
    p = _leaf(item, "add", "item add")
    p.add_argument("--who", required=True)
    p.add_argument("--item")
    p.add_argument("--name")
    p.add_argument("--note")
    p.add_argument("--qty", type=int, default=1)
    p = _leaf(item, "remove", "item remove")
    p.add_argument("--who", required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--give-to", dest="give_to")

    p = _leaf(sub, "gold", "gold")
    p.add_argument("--who", required=True)
    p.add_argument("--add")
    p.add_argument("--spend")
    p.add_argument("--give-to", dest="give_to")

    condition = _group(sub, "condition")
    for name in ("add", "remove"):
        p = _leaf(condition, name, "condition " + name)
        p.add_argument("--who", required=True)
        p.add_argument("--condition", required=True)

    p = _leaf(sub, "deathsave", "deathsave")
    p.add_argument("--who", required=True)
    p = _leaf(sub, "grit", "grit")
    p.add_argument("--dc", type=int, required=True)

    encounter = _group(sub, "encounter")
    for name in ("start", "add"):
        p = _leaf(encounter, name, "encounter " + name)
        p.add_argument("--monster", action="append")
        p.add_argument("--custom", action="append")
        p.add_argument("--average-hp", dest="average_hp", action="store_true")
    _leaf(encounter, "next", "encounter next")
    p = _leaf(encounter, "end", "encounter end")
    p.add_argument("--no-xp", dest="no_xp", action="store_true")

    p = _leaf(encounter, "flee", "encounter flee")
    p.add_argument("--who", required=True)

    p = _leaf(character, "set", "character set")
    p.add_argument("--who", required=True)
    for flag in ("--background", "--bond", "--flaw", "--name"):
        p.add_argument(flag)

    p = _leaf(sub, "track", "track")
    p.add_argument("--name")
    p.add_argument("--secret", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--set", type=int)
    p.add_argument("--add", type=int)
    p.add_argument("--clear", action="store_true")

    p = _leaf(sub, "beat", "beat")
    p.add_argument("--text", required=True)
    p = _leaf(sub, "recent", "recent")
    p.add_argument("--n", type=int, default=cmd_log.DEFAULT_RECENT)

    seed = _group(sub, "seed")
    _leaf(seed, "list", "seed list")
    p = _leaf(seed, "choose", "seed choose")
    p.add_argument("name")
    _leaf(seed, "pick", "seed pick")
    return parser


def dispatch(argv: List[str], skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    """Run one command. Returns the success envelope or raises DmError."""
    if argv == ["--version"]:
        return success_envelope("version", **HANDLERS["version"](argparse.Namespace(), skill_root, rng))
    args = build_parser().parse_args(argv)
    key = args.handler_key
    campaign = getattr(args, "campaign", None)
    if campaign is None:
        return success_envelope(key.replace(" ", "_"), **HANDLERS[key](args, skill_root, rng))
    with io_campaign.campaign_lock(Path(campaign)):
        io_campaign.refuse_symlinks(Path(campaign))
        if key != "init" and (Path(campaign) / io_campaign.PARTY_FILE).is_file():
            # Check the whole save once, up front, so a damaged file is diagnosed and never half-used.
            data.check_party_refs(io_campaign.load_party(Path(campaign)), data.load_all(skill_root))
            io_campaign.load_encounter(Path(campaign))
        return success_envelope(key.replace(" ", "_"), **HANDLERS[key](args, skill_root, rng))


def _command_name(argv: List[str]) -> str:
    words = [word for word in argv[:2] if not word.startswith("-")]
    joined = " ".join(words)
    if joined in HANDLERS:
        return joined.replace(" ", "_")
    if words and words[0] in HANDLERS:
        return words[0]
    return "version" if argv == ["--version"] else "unknown"


def run(argv: List[str], skill_root: Path, rng: random.Random) -> int:
    """dispatch, then print one compact JSON line. Returns the exit code."""
    try:
        out = dispatch(argv, skill_root, rng)
        code = 0
    except DmError as err:
        out = error_envelope(_command_name(argv), err)
        code = 1
    except Exception as exc:  # A bug must still reach the model as JSON, not a traceback.
        out = error_envelope(
            _command_name(argv),
            DmError("internal_error", "%s: %s. This is a bug in dm.py. No change was confirmed." % (type(exc).__name__, exc)),
        )
        code = 1
    print(json.dumps(out, separators=(",", ":")))
    return code
