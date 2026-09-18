# tabletop-dm

A text-only tabletop role-playing game, compatible with fifth edition, that runs as a Claude skill. Claude is the Dungeon Master. A small Python script keeps every number honest: true dice, hit points, spell slots, gold and inventory. It costs nothing beyond the Claude subscription you already have. There is no API key and no server.

## Play

1. Install the plugin (see below).
2. In Claude Cowork or Claude Code, open a **new empty folder**. That folder becomes your save game.
3. Say: **let's play D&D**.
4. To come back later, open the same folder and say: **continue**.

You type what your hero does, in your own words. There are no menus. Useful things to say out of the fiction: "show my sheet", "what's in my pack", "what can I do?", "let's stop here".

## Install

| Host | How |
|---|---|
| Claude Cowork | Add `dist/tabletop-dm-skill.zip` as a skill, or upload `dist/tabletop-dm-plugin.zip` under Customize > Plugins. Same game either way |
| Claude Code | Add this repo as a plugin, or link `skills/tabletop-dm` into `~/.claude/skills/` |
| claude.ai chat | **Not supported.** Plain chat has no folder, so the game has nowhere to keep its save files |

Requirement: a Python 3 that the host can run (3.9 or newer). Nothing to install.

## Before you install (if someone sent you this)

A skill is software: it gives Claude instructions and a script to run. Install one only from a person you trust, and check it first. For this one:

- **What it runs:** one Python script, `skills/tabletop-dm/scripts/dm.py`, with the package next to it. Nothing runs at install time, and there are no hooks.
- **What it writes:** only files inside the folder you open to play. It refuses to start a game in a folder that is not empty, and it refuses to write through a symbolic link.
- **What it cannot do:** it has no network code, no credentials, and uses only Python's standard library. To check: `grep -rnE "^(import|from) " skills/tabletop-dm/scripts` lists every import, and none of them is a network module.
- **What the instructions say:** read `skills/tabletop-dm/SKILL.md`. Its "Two safety rules" tell Claude to treat save files as data and to run nothing but this script. A security scanner will still note that the skill contains a script and asks Claude to run shell commands. That is how the game works.
- **A campaign folder from someone else** is only data. The skill tells Claude never to follow instructions found in one. The audit behind these points is in `docs/security-audit-2026-09-18.md`.

## How it works

| Part | Owns |
|---|---|
| `skills/tabletop-dm/scripts/dm.py` | Every number. It rolls the dice, applies each change, refuses an illegal one, and logs every roll |
| Claude, following `SKILL.md` | The story, the characters, the rulings |
| Your campaign folder | The save game: `party.json`, `log.jsonl`, `journal.md`, `world.md`, `dm-secrets.md` (do not read that one), and `encounter.json` during a fight |

The dice are always open, and the DM never changes a roll. `log.jsonl` is the proof.

Scope of this version: levels 1 to 5. Fighter, Rogue, Wizard, Cleric. About 40 spells and 40 monsters from SRD 5.1.

## If something goes wrong

| What you see | What to do |
|---|---|
| The session stops with a message that the model's safeguards flagged the conversation | This can happen in a normal game, more often in dark or horror play. Open a new chat in the same folder and say **continue**. Every number was saved the moment it changed, and the story is saved at every scene change, so you lose one scene at most |
| The chat gets very long and the DM starts to forget things | Say "let's stop here", then open a new chat and say **continue**. The DM reloads everything from the save files |
| `campaign_file_damaged` | A save file was edited by hand or broken by a sync tool. The message names the exact field. Fix that field, or restore the file from a backup. `log.jsonl` holds every change ever made, including each full character sheet at creation |
| `write_guard_failed` | The folder is not empty. Make a new empty folder, open it, and start again |
| `campaign_busy` | Two commands ran at once. It clears on its own. Say "try that again" |
| The DM says the save holds text that looks like an instruction | Someone put it there. The DM ignores it and removes it. If you got the folder from another person, that is worth knowing |

## Develop

```
python3 -B -m unittest discover -s tests -p "test_*.py" -t .    # the whole suite. Exit 0 means green
python3 build.py                                                # writes the two zips into dist/
```

- Standard library only, Python 3.9 syntax, no network. The suite checks all three.
- Tests come first. Every command and every life-state rule in `PRD.md` maps to a named test class (`docs/PLAN.md`).
- `PRD.md` is the spec. `docs/ARCHITECTURE.md` is the design. `GRILL.md` is the decision history.
- **Spoiler wall:** `skills/tabletop-dm/world/metaplot.md` and `skills/tabletop-dm/seeds/<name>.md` hold the story's secrets. The owner plays this game, so do not quote or summarise those files to him. See `PRD.md` section 13.

## Licence

Rules data in `skills/tabletop-dm/data/` is derived from the System Reference Document 5.1 under CC-BY-4.0. See `skills/tabletop-dm/LICENSE-SRD.md`. This product is compatible with fifth edition. It is not affiliated with Wizards of the Coast.
