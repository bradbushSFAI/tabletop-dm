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
| Claude Cowork | Customize > Plugins > upload `dist/tabletop-dm-plugin.zip` |
| Claude Code | Add this repo as a plugin, or link `skills/tabletop-dm` into `~/.claude/skills/` |
| claude.ai (best effort) | Customize > Skills > upload `dist/tabletop-dm-skill.zip`. Chat has no lasting folder, so a campaign cannot continue across chats |

Requirement: a Python 3 that the host can run (3.9 or newer). Nothing to install.

## How it works

| Part | Owns |
|---|---|
| `skills/tabletop-dm/scripts/dm.py` | Every number. It rolls the dice, applies each change, refuses an illegal one, and logs every roll |
| Claude, following `SKILL.md` | The story, the characters, the rulings |
| Your campaign folder | The save game: `party.json`, `log.jsonl`, `journal.md`, `world.md`, `dm-secrets.md` (do not read that one), and `encounter.json` during a fight |

The dice are always open, and the DM never changes a roll. `log.jsonl` is the proof.

Scope of this version: levels 1 to 5. Fighter, Rogue, Wizard, Cleric. About 40 spells and 40 monsters from SRD 5.1.

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
