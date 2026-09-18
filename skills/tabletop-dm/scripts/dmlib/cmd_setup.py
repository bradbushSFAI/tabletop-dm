"""version, init, settings set, status, sheet."""
import argparse
import platform
import random
from pathlib import Path
from typing import Any, Dict

from . import CURRENT_FORMAT_VERSION, __version__, data, io_campaign, party_ops
from .errors import DmError

DIFFICULTIES = ("story", "standard", "iron")
CONTENT_LEVELS = ("pg13", "pg13-dark")


def version(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    """The self-test the DM runs first in every session."""
    records = data.load_all(skill_root)
    return {
        "dm_version": __version__,
        "python_version": platform.python_version(),
        "format_version": CURRENT_FORMAT_VERSION,
        "data": {kind: len(records[kind]) for kind in data.KINDS},
        "seeds": len(data.list_seed_names(skill_root)),
    }


def init(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    io_campaign.check_write_guard(campaign_dir)
    party = {
        "format": io_campaign.PARTY_FORMAT,
        "format_version": CURRENT_FORMAT_VERSION,
        "hero_id": None,
        "settings": {"difficulty": "standard", "content_level": "pg13", "tone_answers": {}, "seed": None},
        "characters": {},
    }
    io_campaign.save_party(campaign_dir, party)
    for name, text in io_campaign.MARKDOWN_TEMPLATES.items():
        (campaign_dir / name).write_text(text)
    io_campaign.append_log(campaign_dir, [io_campaign.change_entry("init", None, "campaign", None, "created")])
    created = [io_campaign.PARTY_FILE, io_campaign.LOG_FILE] + sorted(io_campaign.MARKDOWN_TEMPLATES)
    return {"campaign": str(campaign_dir), "files_created": created}


def settings_set(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    settings = party["settings"]
    entries = []
    if args.difficulty is None and args.content_level is None and not args.tone:
        raise DmError("nothing_to_set", "give at least one of --difficulty, --content-level, --tone key=value.")
    if args.difficulty is not None and args.difficulty not in DIFFICULTIES:
        raise DmError("illegal_value", "difficulty must be one of %s." % ", ".join(DIFFICULTIES))
    if args.content_level is not None and args.content_level not in CONTENT_LEVELS:
        raise DmError("illegal_value", "content-level must be one of %s." % ", ".join(CONTENT_LEVELS))
    tones = {}
    for pair in args.tone or []:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise DmError("illegal_value", "--tone takes key=value, for example --tone genre=horror. Got '%s'." % pair)
        tones[key.strip()] = value.strip()
    for field, value in (("difficulty", args.difficulty), ("content_level", args.content_level)):
        if value is not None and settings.get(field) != value:
            entries.append(io_campaign.change_entry("settings_set", None, "settings." + field, settings.get(field), value))
            settings[field] = value
    for key, value in tones.items():
        before = settings["tone_answers"].get(key)
        if before != value:
            entries.append(io_campaign.change_entry("settings_set", None, "settings.tone_answers." + key, before, value))
            settings["tone_answers"][key] = value
    io_campaign.save_party(campaign_dir, party)
    io_campaign.append_log(campaign_dir, entries)
    return {"settings": settings}


def gp(cp: int) -> float:
    """Gold is stored as whole copper pieces and shown as gp."""
    return round(cp / 100.0, 2)


def summarize(character: Dict[str, Any]) -> Dict[str, Any]:
    """The compact per-character line for status."""
    out = {
        "name": character["name"],
        "class": character["class"],
        "level": character["level"],
        "xp": character["xp"],
        "hp": "%d/%d" % (character["hp"]["current"], character["hp"]["max"]),
        "ac": character["ac"],
        "life_state": character["life_state"],
        "conditions": character["conditions"],
        "hit_dice": "%d/%d" % (character["hit_dice"]["remaining"], character["hit_dice"]["max"]),
        "gold_gp": gp(character["gold_cp"]),
    }  # type: Dict[str, Any]
    if character["life_state"] == "dying":
        out["death_saves"] = character["death_saves"]
    casting = character.get("spellcasting")
    if casting:
        out["slots"] = {
            level: "%d/%d" % (slot["max"] - slot["used"], slot["max"]) for level, slot in sorted(casting["slots"].items())
        }
    return out


def status(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    repairs = io_campaign.ensure_markdown_templates(campaign_dir)
    encounter = io_campaign.load_encounter(campaign_dir)
    out = {
        "hero_id": party["hero_id"],
        "characters": {cid: summarize(ch) for cid, ch in party["characters"].items()},
        "settings": party["settings"],
        "encounter_active": encounter is not None,
        "trackers": party.get("trackers", {}),
        "journal_bytes": (campaign_dir / "journal.md").stat().st_size,
        "repairs": repairs,
    }  # type: Dict[str, Any]
    if encounter is not None:
        order = encounter["initiative_order"]
        out["encounter"] = {
            "round": encounter["round"],
            "turn": order[encounter["turn_index"]]["id"] if order else None,
            "monsters": {
                mid: "%d/%d" % (m["hp"]["current"], m["hp"]["max"]) for mid, m in encounter["monsters"].items()
            },
        }
    return out


def sheet(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    """One full sheet, with the rule text of every feature and gold shown as gp."""
    campaign_dir = Path(args.campaign)
    party = io_campaign.load_party(campaign_dir)
    character = dict(party_ops.require_character(party, args.id))
    class_data = data.load_all(skill_root)["classes"][character["class"]]
    rules = []
    for level in range(1, character["level"] + 1):
        for feature in class_data["levels"][str(level)]["features"]:
            if feature["id"] in character["features"] and feature not in rules:
                rules.append(feature)
    character["feature_rules"] = rules
    character["gold_gp"] = gp(character["gold_cp"])
    return {"character": character, "is_hero": party["hero_id"] == character["id"]}
