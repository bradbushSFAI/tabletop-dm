# GRILL: Text-Based D&D with an AI Dungeon Master

Status: grill complete 2026-09-18, 15 questions. Awaiting Brad's confirmation before the PRD.

## One-paragraph summary

A text-only, fifth-edition-compatible tabletop game that runs as a Claude skill, with the session model (Fable) as the Dungeon Master, so it costs nothing beyond the player's Claude subscription. The primary host is Claude Cowork (local and cloud modes), and the same skill runs in Claude Code and claude.ai. A zero-install Python script, `dm.py`, owns every number (true dice, hit points, slots, gold, inventory) and refuses illegal changes. The model owns the fiction. The save game is a plain folder of JSON and markdown. The skill ships one original world with one hidden metaplot and 5 seeds, each a different front door into that metaplot.

## Fixed constraints (from Brad, opening brief)

- Text only. No graphics.
- The AI is the Dungeon Master.
- The DM must be a top-tier creative model (Claude Fable or GPT Astra).
- No pay-per-token API cost. The game must ride a subscription Brad already pays for.
- Personal use first. Distribution as a skill is a possible later goal.
- Open to architectures other than a Claude Code skill.

## Architecture

- **Host: Claude Cowork (desktop GUI), primary target.** Brad's choice, 2026-09-18. Reason: a GUI is more accessible than a terminal for people he may share it with later.
- **Shape: a skill (packaged as a plugin) plus a campaign directory.** The skill holds the DM instructions and the programmatic parts (dice, state). The directory the player opens in Cowork holds the save files.
- **The DM is the session model.** No API key, no server, no token bill. Each player uses their own Claude subscription.
- **Scripts: Python 3, standard library only** (no `pip install`, no third-party packages). Brad's choice, 2026-09-18, for shareability. Every script must run with a bare `python3`.
- Docs check (2026-09-18, Agent Skills overview, best practices, enterprise, code execution tool, Help Center): Python is the first-class script language for skills. Every official script example is Python. The documented container is Linux, Python 3.11, 5 GiB RAM, no internet on the API surface. This supports the Python choice.
- Open question on where Cowork executes: the Help Center "Get started with Claude Cowork" page says tasks run "in the cloud (in beta)" on Anthropic's servers. Brad's knowledge from June is a local VM. Both may exist as modes. The design must not depend on which one: no network, no install, no host paths.
- Resolved by Brad, 2026-09-18: Cowork has BOTH a local mode and a cloud mode. The skill must work in both.
- **Script scope: "state keeper" (option B), accepted 2026-09-18.** One CLI, `dm.py`, with subcommands (roll, damage, heal, cast, rest, item, gold, xp, condition, initiative, status). The model decides what happens. The script applies the change and refuses an illegal one (no slot left, not enough gold). Rejected: thin dice-only scripts (state drifts), full combat engine (large, and blocks creative rulings). Built with TDD: each subcommand is a pure function over a JSON file.
- Still to verify in a Cowork boot test, in local mode AND in cloud mode: `python3 --version` runs, and a file written by a script lands in the opened campaign folder and is there in the next session.

### Scripting constraints (from the skills docs)

- Standard library only. Target Python 3.9 syntax so it runs on the documented 3.11 container and on a Mac's system Python.
- No network calls. The API container has none, and network calls are what the enterprise skill scanner flags.
- Scripts never write inside the skill folder (it can be read-only or replaced on update). All state goes to a campaign directory passed as an argument.
- Scripts print compact JSON. Only script output enters the context, never the script code, so rules tables that live in the script cost zero tokens.
- "Solve, don't defer": a script repairs or reports a bad state with a specific message. It does not crash and leave the model to guess.
- Dice use the operating system's random source (`random.SystemRandom`).
- SKILL.md body under 500 lines. Reference files one level deep (rules, classes, spells, monsters, DM style), each with a table of contents if over 100 lines.
- Skill `name`: lowercase, hyphens, 64 characters or fewer, and must not contain "claude" or "anthropic".
- Forward slashes in every path.
- Dice and state commands are "low freedom" (run exactly this command). Narration is "high freedom".

### Path and portability rules (accepted 2026-09-18)

- `dm.py` finds `data/*.json` relative to its own file (`Path(__file__).parent`). No environment variables, no config.
- First step of every session: `dm.py --version` as a self-test. A failure gives a clear message.
- Every command takes `--campaign <dir>`. No hidden default, no "current campaign" file in the home folder.
- `dm.py init --campaign <dir>` creates the six files. **Strict guard:** `dm.py` writes only in an empty folder or a folder that has a `party.json` it made. Otherwise it stops and asks for a new subfolder.
- SKILL.md says: try `python3`, then `python` (Claude Code on Windows).
- One folder is one campaign. No save slots in code.

### Distribution facts (from the docs)

- Custom skills do not sync between surfaces. One Git repo is the source of truth, with a build step per surface.
- Claude Code: `~/.claude/skills/` or a plugin. Cowork: install a plugin from a file upload or a GitHub marketplace (all paid plans). claude.ai: zip upload under Customize > Skills (needs code execution turned on).
- In-app sharing to named people exists only on Team and Enterprise plans. For the public, the path is a GitHub repo that people add as a plugin marketplace, or a zip they upload.
- **Same skill must also run in Claude Code.** Skills are the same format in both hosts, so this is free if the scripts use no host-specific paths.
- Rejected: web app or standalone CLI (needs a paid API), claude.ai Project (no true dice, no save files).
- Deferred: Codex/Astra port. Keep rules and DM instructions in plain markdown so a port stays small.
- To verify in the first boot test: the skill's Node scripts run in Cowork, and the save files land in the opened folder.

## Rules system

- **D&D 5e SRD 5.1, trimmed core.** Accepted 2026-09-18.
- Licence: SRD 5.1 is CC-BY-4.0. Ship the attribution line. Use no Wizards product identity (no Beholder, Mind Flayer, Forgotten Realms names).
- First version scope: levels 1 to 5, four classes (Fighter, Rogue, Wizard, Cleric), a short spell list. More classes and spells are data files added later.
- Split of work: scripts own dice, hit points, spell slots, gold, inventory. The model owns story, characters, and rulings.
- Deferred: a rules-light mode for new players.
- **Rules data: JSON files in the skill, read through `dm.py lookup`** (accepted 2026-09-18). `data/classes.json`, `data/spells.json`, `data/monsters.json`, `data/equipment.json`. One source of truth for the script and the model. A lookup returns one compact record (about 100 tokens), never a whole file.
- First version data size: 4 classes to level 5, about 40 spells, about 40 monsters (challenge rating 0 to 5).
- The DM can invent monsters: `dm.py encounter add --custom` accepts made-up stats. The data is a base, not a cage.
- Prose reference files (markdown) only for rulings and style: how to run combat, when to call for a check, how to set a DC, DM voice.
- Rejected: markdown stat files (whole-file reads, numbers in two places), and relying on model memory (no source of truth to enforce).

## Game state and persistence

Accepted 2026-09-18. The campaign folder IS the save game. The player opens it in Cowork.

```
my-campaign/
  party.json        hero + companions: sheets, HP, slots, inventory, gold, XP
  encounter.json    the active fight only: initiative, monster HP. Deleted at fight end
  journal.md        the story so far, one short entry per scene. Player-readable
  world.md          characters, places, factions, open quests
  dm-secrets.md     plot twists and hidden facts. Honour system, not encrypted
  log.jsonl         every dice roll and state change, append-only
```

- **Numbers are JSON, written ONLY by `dm.py`.** The model never edits JSON directly. SKILL.md states this as a firm rule.
- **Fiction is markdown, written by the model.** Human-readable and hand-editable.
- Session start: `dm.py status` plus a read of `journal.md` and `world.md` restores the DM's memory without the old chat.
- `log.jsonl` is the audit trail for dice honesty and for debugging a bad state.
- Journal growth: `dm.py` reports file size. Past a limit, the DM folds old entries into a "previously" summary.

## Play experience

- **Party: one hero the player controls, plus 1 or 2 DM-played companions** (accepted 2026-09-18). Companions have full sheets in `party.json`. The player gives short orders in a fight, and the DM decides the details. Keeps SRD combat balance honest.
- At character creation the DM offers 2 or 3 possible companions, each with a hook. The player picks one or two, or starts alone and meets them in the story.
- Companions can die, leave, or betray. Their private motives live in `dm-secrets.md`.
- Deferred: hot-seat play for a second human.

### DM style, for `reference/dm-style.md` (accepted 2026-09-18)

- Short turns: 80 to 150 words as the norm. Longer only for an opening scene or a large revelation.
- Every turn ends on a moment that demands a player action. Never an empty "what do you do?".
- No option lists by default. The player types free text. A new player can ask "what can I do?" and get 3 ideas.
- The DM never acts, speaks, or feels for the hero. It plays companions and the world.
- Say yes to creative plans: set a DC, roll. A failure makes a new problem, and does not stop the scene.
- Named characters have a voice, a want, and one specific detail. They sometimes lie.
- Use all the senses. Plant clues early and pay them off later.
- The balance of fights, talk, and exploration follows the player's tone answers.
- The villain acts in the background between sessions. The world does not wait.
- **Content: "PG-13 adventure" default, player can set it darker at the start.** Violence and dread are in, gore kept short, no sexual content, cruelty to children and similar themes stay out of scene. The horror tone gets more dread and body horror, inside the model's normal limits. One field in `party.json` with the other tone answers.

### Session flow (accepted 2026-09-18)

- **First time:** the player opens an empty folder and says "let's play D&D" or similar. The skill description triggers on such phrases. The DM runs the self-test, `init`, the tone and difficulty questions, the 5 teasers, character creation, then the opening scene.
- **Character creation:** guided, about 5 minutes. Class, name, ability scores (standard array, or 4d6 rolled by the script), a one-sentence background, one bond, one flaw. A "quick start" option gives a ready hero in one step.
- **Continue:** the player opens the campaign folder and says "continue". The DM runs `status`, reads journal, world and secrets, gives a 3 or 4 sentence in-fiction recap, and resumes from the last scene.
- **Stop:** "let's stop here". The DM writes the journal entry, updates `world.md` and the plan in `dm-secrets.md` (including what the villain did in the background), and confirms the save.
- **Crash safety:** numbers are always safe, because `dm.py` writes each change to disk at once. The DM also writes one journal line at EVERY scene change, so a closed window or a full context costs one scene at most. A new chat can always resume from the files.
- **Out-of-fiction requests** are plain words, not slash commands ("show my sheet", "what do I know about the Baron"). No menu system.

### Stakes and death (accepted 2026-09-18)

- **Full 5e dice. Death changes the story and does not end it.** Death saves are real and script-rolled. On "death" the DM picks a cost that fits the fiction: captured, saved at a price, a permanent scar or loss, a companion dies in the hero's place, a debt to a dark power. True death is possible when the player accepts it or makes a reckless choice after a clear warning.
- **House rule, Brad's idea: the Grit save.** When the hero fails the third death save (or would die outright), the script rolls one Constitution saving throw. The DC depends on the situation (DC 10 base, higher for massive damage or a hostile place with no help near). Success: the hero lives with a LIGHT cost (stable at 0 HP, a scar, lost gear). Failure: the HEAVY cost from the list above, or true death in Iron mode. Once per long rest, so it cannot be farmed. Numbers are a first draft to tune in playtest. It lives in `dm.py` as `dm.py grit`, so it is a true roll in the log.
- Difficulty is one field in `party.json`, set at campaign start: **Story** (light costs), **Standard** (as above), **Iron** (full 5e, death is final, Grit save still applies once).
- **Dice are always open.** Every roll shows true numbers, for example `d20 (14) + 5 = 19 vs AC 15: hit`. No hidden DM rolls that change a result. `log.jsonl` proves it.
- **The DM never changes a roll.** Mercy comes from the fiction only (prisoners, a companion steps in, a way to run). SKILL.md states this as a firm rule.
- Companions can die in every mode.

### Adventure source (Brad's design, 2026-09-18)

- **One preset world, shipped with the skill, the same for every player and every campaign.**
- **One meta plot** that runs under the whole world.
- **Several seeds. Each seed is a "front door":** a different start point and local story that leads into the same meta plot. Replay means a new door into the same larger mystery, and a player learns more of the world each time.
- Shipped content structure (accepted 2026-09-18):
  - `world/bible.md`: regions, factions, gods, history, tone. Common knowledge. DM reads it, parts are safe for the player.
  - `world/metaplot.md`: the hidden truth, who is behind it, the clock (what happens as time passes), 4 or 5 revelations. DM only.
  - `seeds/<name>.md`: one front door, 1 or 2 pages. Start place, opening scene, local villain with a motive, 2 or 3 companion candidates, local secrets, and WHICH metaplot revelations this door leads to. DM only.
  - `seeds/teasers.md`: one spoiler-free sentence per door. The only seed text shown to the player.
- A seed is a situation, not a script. The DM improvises inside it.
- Each seed exposes a different slice of the metaplot. No single seed reveals all of it.
- At `init` the DM copies the seed into `dm-secrets.md` and adds a short plan for this campaign. The campaign folder is then self-contained, so a skill update cannot break a campaign in progress.
- Selection: the player picks from the teasers, or says "surprise me" and `dm.py` makes a true random pick.
- First version: 5 seeds. More seeds are more files, with no code change.
- **Authorship (accepted 2026-09-18):** Brad shapes and approves `world/bible.md` and `seeds/teasers.md`. Claude writes `world/metaplot.md` and the seeds, and Brad does NOT read them, so he can play his own game unspoiled. A review agent checks the secret files for quality, consistency, and SRD product-identity problems, and Brad sees the verdict only. Brad can open the files at any time.
- **Tone: broad** (Brad, 2026-09-18). Base world is a classic fantasy frontier with a wrong note under it, so 5e rules and SRD monsters fit unchanged. The metaplot is a slow mystery, not a dark lord. The world is wide enough that each seed can carry its own tone (one comic, one dread, one intrigue, and so on). The player's tone answers at campaign start tune the DM further.
- The world must be original. SRD 5.1 gives rules only, and no Wizards setting or product identity can be used.
- Rejected: pure improvisation (wanders, no payoff) and a fully generated plan per campaign (no shared world, no meta plot).

## Testing (accepted 2026-09-18)

1. **`dm.py` and data files:** Python `unittest` (stdlib, zero install), test-first. Every subcommand, every illegal change it must refuse, the `init` guard, the Grit save, dice with a seeded random source for repeatable results. Data tests check every monster, spell and class record is complete and legal. Hard gate before each commit.
2. **The skill in a host:** boot test in Claude Code first (fastest loop), then Cowork local mode and Cowork cloud mode. Checks: skill triggers, self-test runs, `init` makes the six files, a file is still there in the next session. **Brad runs the two Cowork tests** (Claude cannot drive Cowork).
3. **DM behaviour:** a player sub-agent plays 15 to 20 turns from only the skill and a campaign folder. A second agent audits the transcript and save files against a checklist: every number through `dm.py`, no direct JSON edits, no changed rolls, never acts for the hero, short turns, a journal line per scene change, a fight to 0 HP with the Grit save run. A failure becomes a SKILL.md change and a re-run.
- 3 trigger tests: two phrases that must start the skill, one that must not.
- "Is it fun" is reported as UNVERIFIED until Brad plays a real session in Cowork.
- The playtest agents run on the subscription. No API cost.

## Naming, repo layout, distribution (accepted 2026-09-18)

```
TextBasedDnD/                    Git repo, and also a Claude plugin
  .claude-plugin/plugin.json     plugin manifest for Cowork and Claude Code
  skills/tabletop-dm/
    SKILL.md
    scripts/dm.py
    data/*.json
    reference/*.md               combat, checks and DCs, dm-style
    world/bible.md, metaplot.md
    seeds/*.md, teasers.md
    LICENSE-SRD.md               CC-BY-4.0 attribution line
  tests/                         unittest files, NOT shipped inside the skill
  build.py                       makes dist/tabletop-dm.zip for claude.ai upload
  docs/, GRILL.md, PRD.md, README.md
```

- One repo serves all three surfaces with identical content. Claude Code and Cowork install it as a plugin (GitHub repo or file). claude.ai gets the zip from `build.py`.
- **Skill name: `tabletop-dm` for now.** Rename to the world's name before a public release (one folder, one line). The name avoids "claude", "anthropic", and the Wizards trademarks "D&D" and "Dungeons & Dragons". The description may mention D&D-style play so that "let's play D&D" triggers the skill. "Compatible with fifth edition" is the allowed phrase.
- **Private GitHub repo now.** The metaplot and seeds are spoilers, and the world is Brad's creative work. He makes it public when he decides to share.
- Licence for Brad's own content: decided at release time. SRD numbers stay CC-BY-4.0.
- No server and no Vercel deploy. App-flow Step 8 "deploy" means: tag a release, build the zip, install the plugin in Brad's Cowork.

## Refinements made while writing the PRD (2026-09-18)

A fresh-context reader test of `PRD.md` found gaps. These were resolved in the PRD, and they refine the entries above. `PRD.md` is the current spec.

- `init` creates FIVE files. `encounter.json` is created by `encounter start`, and its presence means a fight is active. `init` writes the three markdown files as heading-only templates, and after that only the model writes them.
- New commands: `settings set`, `sheet`, `equip` / `unequip`, `spells prepare`, `encounter add`. `companion remove` became `character retire` (it also covers an accepted true death of the hero).
- `roll` has a named form (`--who <id> --attack / --check / --save`), so the script supplies every modifier and the model never computes a bonus. Sheets store derived numbers.
- Every command except `--version` and `lookup` requires `--campaign`, so the log truly holds every roll.
- Life states defined: `alive`, `dying`, `stable`, `fallen`, `dead`, `departed`. The Grit save runs from `fallen`, is for the hero only, reads the difficulty, and returns `light_cost`, `heavy_cost`, or `dead`. Already used since the last long rest means no roll and an automatic failure. On `story` the hero cannot truly die.
- `encounter end` splits XP equally among living party members and applies it.
- "Empty folder" ignores hidden dot-files. The DM asks the player to make a subfolder and does not make one itself.
- **claude.ai was demoted to best effort, not a first-version target** (chat has no persistent campaign folder). Cowork and Claude Code are the targets.
- `build.py` makes two zips: a plugin zip (`.claude-plugin/` plus `skills/`) and a skill zip. Neither ships tests or docs. While the repo is private, sharing is by sending the plugin zip.
- The spoiler wall also covers test campaigns, playtest transcripts, auditor reports, and diffs. They live in a gitignored `playtests/` folder.
- The playtest has two runs: a free run, and a death run that starts the hero at 1 HP so the death path is reached with true dice.
- New milestone M0: Brad's 2-minute Cowork check comes before any code.
- Second reader pass: `fallen` is a hero-only state, and a companion goes straight to `dead`. Death saves follow 5e in full (natural 1, natural 20, damage while `dying`). `party.json` marks exactly one hero. New commands `seed choose` and `character promote`. A true hero death always needs `character retire --player-accepted`. One authoritative six-step setup order lives in PRD section 8. Internal functions take the skill root and the random source as parameters, so tests use fixtures with no environment variable.

## Open items (not blockers for the PRD)

1. Cowork boot test in local mode and cloud mode (Brad runs it): `python3 --version`, and a script-written file survives to the next session.
2. Grit save numbers (DC 10 base, once per long rest) are a first draft to tune in playtest.
3. The world's name, and with it the final skill name.
4. "Is it fun" stays unverified until Brad plays a real session.
