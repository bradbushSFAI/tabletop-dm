# tabletop-dm

A text-only tabletop role-playing game, compatible with fifth edition. The AI is your Dungeon Master. A small Python script keeps every number honest: true dice, hit points, spell slots, gold and inventory.

It runs in Claude (the desktop app and Claude Code), in the ChatGPT desktop app, and in OpenAI Codex. It uses the plan you already have. There is no API key and no server.

What you get: levels 1 to 5, four classes (Fighter, Rogue, Wizard, Cleric), 43 spells and 44 monsters from SRD 5.1, and five starting adventures in one shared world. Every number is saved the moment it changes, and the story at every scene, so you can stop and pick the game up days later.

> **Want to play it unspoiled?** Do not open `skills/tabletop-dm/seeds/` or `skills/tabletop-dm/world/metaplot.md`. They hold the story's secrets. `world/bible.md` and `seeds/teasers.md` are safe to read.

## Install

| App | Works? |
|---|---|
| Claude desktop app (Cowork) | Yes |
| Claude Code | Yes |
| ChatGPT desktop app, in a project with a folder | Yes |
| OpenAI Codex: the CLI and the IDE extension | Yes |
| claude.ai chat | **No.** A plain chat has no folder, so the game has nowhere to keep its save files |
| ChatGPT in a web browser | Not tested. The game needs a folder that keeps its save files between chats |

The game also needs Python 3.9 or newer wherever the app runs its commands. The DM tests for it at the start of every session. If it says Python is missing, install it from [python.org](https://www.python.org/downloads/). Nothing else to install.

### Claude desktop app (Cowork)

1. Open **Customize > Plugins**.
2. Select **Add > Add marketplace**, and enter `bradbushSFAI/tabletop-dm`.
3. Find **tabletop-dm** in the list, and select **Add**.

To get a new version later, select **Check for updates** on the marketplace, or turn on **Sync automatically**. A plugin you add here also shows up in Claude Code when you sign in with the same account.

No marketplace? Download `tabletop-dm-plugin.zip` from the [latest release](https://github.com/bradbushSFAI/tabletop-dm/releases/latest), then use **Add > Upload plugin**.

### Claude Code

Inside Claude Code:

```
/plugin marketplace add bradbushSFAI/tabletop-dm
/plugin install tabletop-dm@tabletop-dm
```

Then run `/reload-plugins`, or start a new session. From a terminal, the same two steps are `claude plugin marketplace add bradbushSFAI/tabletop-dm` and `claude plugin install tabletop-dm@tabletop-dm`.

### ChatGPT desktop app and OpenAI Codex

Install it as a plugin, from a terminal:

```
codex plugin marketplace add bradbushSFAI/tabletop-dm
codex plugin add tabletop-dm@tabletop-dm
```

Then start a new thread. To update later, run `codex plugin marketplace upgrade`, then the second line again.

Or install it as a skill. Inside Codex, type:

```
$skill-installer install https://github.com/bradbushSFAI/tabletop-dm/tree/main/skills/tabletop-dm
```

Approve the download when Codex asks, then restart Codex. To update later, delete `~/.codex/skills/tabletop-dm` and run the same line again (the installer stops if the folder already exists).

To install by hand instead, copy the `skills/tabletop-dm` folder from this repo into `~/.agents/skills/`.

**The game needs permission to save.** In the ChatGPT desktop app, select your game folder for the project and trust it. The Codex CLI may open a folder that is not a git repository read-only, and then the DM cannot save. So make your game folder a git repository before you start (the game ignores the hidden `.git` folder), or run `/permissions` inside Codex and allow edits.

## Play

1. Make a **new empty folder**. That folder becomes your save game.
2. Open it. In the Claude desktop app, start a Cowork task in that folder. In the ChatGPT desktop app, use a project with that folder selected. In Claude Code or the Codex CLI, `cd` into it and start the app there.
3. Say: **let's play D&D**.
4. To come back later, open the same folder and say: **continue**.

In the Codex CLI, the first steps look like this:

```
mkdir my-campaign && cd my-campaign && git init && codex
```

You type what your hero does, in your own words. There are no menus. Useful things to say out of the fiction: "show my sheet", "what's in my pack", "what can I do?", "let's stop here".

## Before you install

A skill is software: it gives the AI instructions and a script to run. Install one only from a person you trust, and check it first. For this one:

- **What it runs:** one Python script, `skills/tabletop-dm/scripts/dm.py`, with the package next to it. Nothing runs at install time, and there are no hooks.
- **What it writes:** only files inside the folder you open to play. It refuses to start a game in a folder that is not empty, and it refuses to write through a symbolic link.
- **What it cannot do:** it has no network code, no credentials, and uses only Python's standard library. To check: `grep -rnE "^(import|from) " skills/tabletop-dm/scripts` lists every import, and none of them is a network module.
- **What the instructions say:** read `skills/tabletop-dm/SKILL.md`. Its "Two safety rules" tell the DM to treat save files as data and to run nothing but this script. A security scanner will still note that the skill contains a script and asks the AI to run shell commands. That is how the game works.
- **A campaign folder from someone else** is only data. The skill tells the DM never to follow instructions found in one. The audit behind these points is in `docs/security-audit-2026-09-18.md`.

## How it works

| Part | Owns |
|---|---|
| `skills/tabletop-dm/scripts/dm.py` | Every number. It rolls the dice, applies each change, refuses an illegal one, and logs every roll |
| The AI, following `SKILL.md` | The story, the characters, the rulings |
| Your campaign folder | The save game: `party.json`, `log.jsonl`, `journal.md`, `world.md`, `dm-secrets.md` (do not read that one), and `encounter.json` during a fight |

The dice are always open, and the DM never changes a roll. `log.jsonl` is the proof.

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
- **Spoilers:** `skills/tabletop-dm/world/metaplot.md` and `skills/tabletop-dm/seeds/<name>.md` hold the story's secrets. Other players read the issues, so do not quote or summarise those files in an issue or a pull request. See `PRD.md` section 13.

## Licence

The code, the DM instructions and the story are MIT licensed. See `LICENSE`.

The rules data in `skills/tabletop-dm/data/` is derived from the System Reference Document 5.1 under CC-BY-4.0. See `skills/tabletop-dm/LICENSE-SRD.md`. This product is compatible with fifth edition. It is not affiliated with Wizards of the Coast.
