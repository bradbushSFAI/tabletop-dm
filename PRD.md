# PRD: tabletop-dm

A text-only, fifth-edition-compatible tabletop role-playing game that runs as a Claude skill, with the session model as the Dungeon Master.

- Owner: Brad Bush
- Date: 2026-09-18
- Status: draft for review
- This PRD is self-sufficient. `GRILL.md` is the decision history behind it (15 resolved questions, with the rejected options and the reasons). If the two disagree, stop and ask Brad.

## 1. Problem and goal

Brad wants to play a Dungeons-and-Dragons-style game where a top-tier creative model (Claude Fable) is the Dungeon Master. A web app or standalone CLI would have to call a model API and pay per token, which is not acceptable for a hobby game.

**Goal:** a game that costs nothing beyond the Claude subscription the player already has, feels like real fifth-edition play (true dice, real stakes, state that stays correct for a campaign of many sessions), and can be shared later with other people who have their own subscriptions.

**The core idea:** a Claude skill. The model that already runs the session is the DM. A small zero-install Python script owns every number. The model owns the fiction. The save game is a plain folder.

## 2. Users

| User | Need |
|---|---|
| Brad (first and main player) | A creative, surprising DM. He must be able to play his own game unspoiled |
| A person Brad shares it with later | Installs a plugin in a GUI. No terminal, no package install, no API key. Plays on their own Claude subscription. The only requirement beyond the host is a Python 3 that the host can run (see Risk 1) |

## 3. Hosts

| Host | Priority | Notes |
|---|---|---|
| Claude Cowork, local mode | Primary | Desktop GUI. The player opens a campaign folder |
| Claude Cowork, cloud mode | Primary | Same skill. Tasks run on Anthropic's servers |
| Claude Code | Secondary, and the development loop | Same skill format. Fastest place to test |
| claude.ai chat | **Not supported** | Plain claude.ai chat has no folder, so the save game has nowhere to live and the game does not work there (confirmed by Brad, 2026-09-18). No test layer covers it |

The design must not depend on which host or mode runs it. That gives the hard constraints in section 6.

## 4. Non-goals (first version)

- No web app, no server, no database, no API calls, no deploy to a hosting platform.
- No graphics, maps, or sound.
- No multiplayer and no hot-seat second human.
- No levels above 5. No classes beyond Fighter, Rogue, Wizard, Cleric. No feats, no multiclassing.
- No full combat engine. The script does not resolve whole attacks or run monster turns.
- No rules-light mode.
- No Codex or GPT port. (Rules and DM instructions stay in plain markdown and JSON so a port stays small.)
- No save slots. One folder is one campaign.
- No encryption of DM secrets. It is an honour system.
- No slash-command or menu interface. The player types plain words.

## 5. How the work is split

This split is the central design rule. Every other requirement follows from it.

| Owner | Owns | Must never |
|---|---|---|
| `dm.py` (the script) | Dice, hit points, spell slots, gold, inventory, XP and level, conditions, initiative, rests, death saves, the Grit save, the roll log | Narrate, or make a story decision |
| The model (the DM) | Story, characters, rulings, DCs, what happens next, all markdown files | Invent a dice result, do hit-point or gold arithmetic itself, edit a JSON file directly, change a roll after it is made |

The model decides **what happens**. The script **applies it** and refuses an illegal change (no slot left, not enough gold, item not in the pack) with a specific message.

## 6. Hard technical constraints

These come from the Agent Skills documentation and from the need to run in every host.

1. **Python 3, standard library only.** No `pip install`. No third-party imports.
2. **Python 3.9-compatible syntax.** The documented skill container is Python 3.11. A Mac's system Python can be 3.9.
3. **No network calls** anywhere in the skill. The API container has no network, and network calls are what enterprise skill scanners flag.
4. **Scripts never write inside the skill folder.** It can be read-only or replaced on update. All state goes to the campaign directory.
5. **`dm.py` finds its data relative to its own file** (`Path(__file__).parent`). No environment variables, no config file, no host-specific paths.
6. **Every state command takes `--campaign <dir>`.** No hidden default. No "current campaign" pointer in the home folder.
7. **The write guard.** `dm.py` writes only into (a) an empty folder, or (b) a folder that holds a `party.json` that `dm.py` itself created (marked by a format field). "Empty" means no entries other than hidden dot-files such as `.DS_Store`. Anything else: stop with a message that asks for a new empty subfolder. The DM then asks the player to make and open one. It does not create a subfolder itself. This protects a player who opens their Documents folder by mistake.
8. **Scripts print compact JSON to stdout.** Only script output enters the model's context. Errors are JSON too, with a specific, actionable message, and a non-zero exit code.
9. **"Solve, don't defer."** A script handles a missing or damaged file with a clear report or a safe repair. It does not crash with a traceback and leave the model to guess.
10. **Dice use the operating system's random source** (`random.SystemRandom`). Tests inject a seeded source.
11. **Every state change is written to disk at once**, and appended to `log.jsonl`. A closed window never loses a number.
12. **`SKILL.md` body under 500 lines.** Reference files are one level deep from `SKILL.md`. A reference file over 100 lines starts with a table of contents.
13. **Skill name rules:** lowercase letters, numbers, hyphens, 64 characters or fewer, no "claude", no "anthropic".
14. **Forward slashes in every path** in every file.
15. `SKILL.md` tells the model to try `python3` first, then `python` (Claude Code on Windows).

## 7. Repo layout

```
TextBasedDnD/                    Git repo, and also a Claude plugin
  .claude-plugin/plugin.json     plugin manifest for Cowork and Claude Code
  skills/tabletop-dm/
    SKILL.md
    scripts/dm.py
    data/classes.json
    data/spells.json
    data/monsters.json
    data/equipment.json
    reference/combat.md          how to run a fight with dm.py
    reference/checks.md          when to call for a check, how to set a DC
    reference/dm-style.md        voice, pacing, content level
    reference/session-flow.md    first time, continue, stop, scene-change saves
    world/bible.md
    world/metaplot.md            DM only
    seeds/teasers.md             player-safe
    seeds/<name>.md              DM only, 5 files
    LICENSE-SRD.md               CC-BY-4.0 attribution
  tests/                         unittest files. NOT shipped inside the skill
  playtests/                     gitignored. Test campaigns and transcripts (they hold spoilers)
  build.py                       makes dist/tabletop-dm-plugin.zip and dist/tabletop-dm-skill.zip
  docs/
  GRILL.md  PRD.md  README.md
```

One repo serves every host with identical content. There are no per-host variants.

`build.py` makes two files. `tabletop-dm-plugin.zip` holds only `.claude-plugin/` and `skills/`, and is the file a person installs in Cowork or Claude Code. `tabletop-dm-skill.zip` holds only the `skills/tabletop-dm/` folder, for a claude.ai upload. Neither holds `tests/`, `playtests/`, `GRILL.md`, or `PRD.md`. During development (before M7) the skill is loaded in Claude Code by linking `skills/tabletop-dm/` into a scratch project's `.claude/skills/`.

## 8. The campaign folder (the save game)

```
my-campaign/
  party.json        hero + companions: sheets, HP, slots, inventory, gold, XP, settings
  encounter.json    the active fight only: initiative order, monster HP. Deleted at fight end
  journal.md        the story so far, one short entry per scene. Player-readable
  world.md          characters met, places, factions, open quests (this campaign's view)
  dm-secrets.md     the chosen seed, the campaign plan, companion motives. Honour system
  log.jsonl         every dice roll and state change, append-only
```

| File | Created by | Written after that by | Format |
|---|---|---|---|
| `party.json`, `log.jsonl` | `dm.py init` | `dm.py` ONLY | JSON / JSON lines |
| `encounter.json` | `dm.py encounter start` (NOT `init`). Its presence means a fight is active | `dm.py` ONLY | JSON |
| `journal.md`, `world.md`, `dm-secrets.md` | `dm.py init`, as templates with headings only | The model ONLY | Markdown |

So `init` creates five files, and a campaign folder holds six while a fight is active.

`party.json` also holds the campaign settings: a format marker and version, difficulty (`story`, `standard`, `iron`), tone answers, content level, and the chosen seed name. The model sets them with `dm.py settings set`, which validates the values. It never edits them by hand.

**Campaign setup order (the one authoritative sequence; section 15 repeats it):**

1. `--version`, then `init`.
2. The setup questions, then `settings set`.
3. The teasers, then `seed choose <name>` or `seed pick`. The script records the seed name.
4. The DM copies the chosen seed file into `dm-secrets.md` and adds a short plan for this campaign.
5. Character creation, then companion choice (the candidates come from the seed).
6. The opening scene.

After step 4 the campaign folder is self-contained. A later skill update cannot break a campaign in progress.

**Identifiers.** Every character and monster has a stable slug id. A character's id comes from its name (`kira`). Monsters in a fight are numbered (`goblin-1`, `goblin-2`). Every command that needs a target takes an id.

**Schemas.** The exact JSON shapes of `party.json`, `encounter.json`, a `log.jsonl` line, the `--custom` monster input, and each data file are a required deliverable of the architecture step, before any code. A character sheet **stores its derived numbers** (ability modifiers, proficiency bonus, attack bonuses per weapon, save bonuses, skill bonuses, AC, spell save DC, spell attack bonus), and `dm.py` recomputes them whenever an input changes (level-up, equip).

**Journal format.** During play, one line per scene change (what happened, where the party is now). At Stop, the DM adds a short summary paragraph for the session under a dated heading. "Entry" in this PRD means those lines plus that paragraph.

## 9. `dm.py` command surface

Every command prints JSON. Only `--version` and `lookup` work without a campaign. **Every other command, including `roll` and `seed pick`, requires `--campaign <dir>`.** Commands that change state or roll dice validate, write to disk at once, and append to `log.jsonl`, so that the log holds every roll. `status` and `sheet` only read. "Refuses" means: non-zero exit, a JSON error with a specific message, and no change on disk.

**Testability.** The CLI finds the skill root from its own file (constraint 5), but every internal function takes the skill root and the random source as parameters. Tests pass a fixture folder (with fixture data and fixture seeds) and a seeded random source. This needs no environment variable and no extra CLI flag. M3 tests `seed pick` against fixture seeds, because the real seeds arrive in M5.

| Command | Does | Refuses when |
|---|---|---|
| `--version` | Self-test: prints version, Python version, and that the data files load | Data files missing or invalid |
| `init` | Creates the five starting campaign files (section 8) | The write guard fails |
| `settings set` | Sets difficulty, tone answers, content level. (The seed name is set only by the `seed` commands) | Unknown key or illegal value |
| `status` | Compact summary for re-grounding: each character's HP, slots, conditions, gold, level, XP, life state. Settings. Active encounter if any. Size of `journal.md` | Not a campaign folder |
| `sheet <id>` | One character's full sheet: abilities, skills, saves, attacks, AC, spells, inventory, equipped items. Answers "show my sheet" and "what's in my pack" | Unknown id |
| `roll` | Two forms. **Named:** `roll --who <id> --attack <weapon>`, `--check <skill or ability>`, `--save <ability>`, `--initiative`. The script supplies the modifier from the sheet, so the model never computes a bonus. **Free:** `roll <expr>` for damage and anything else, such as `2d6+3`, `4d6kh3`. Flags for advantage and disadvantage. Optional `--dc` or `--ac` target and a `--reason` label. Output shows every die | Bad expression, unknown id, weapon not on the sheet |
| `lookup <kind> <name>` | One compact record from the data files: monster, spell, class level, equipment item. `lookup <kind> --list` gives names only | Unknown name (the error lists near matches) |
| `character create` | Builds a legal sheet from class, name, and ability scores (standard array or script-rolled 4d6-drop-lowest). Applies the class's starting gear package, starting gold, and default spell choices from `classes.json` (the player may override the spell picks). `--level N` (1 to 5) for a companion who joins later. Used for the hero and for companions. `--quick` makes a ready hero in one step | Illegal scores, unknown class, illegal spell pick |
| `equip` / `unequip` | Sets worn armour, shield, and wielded weapons from the inventory. The script derives AC and attack numbers | Item not in inventory, not proficient is allowed but reported |
| `spells prepare` | Sets a Wizard's or Cleric's prepared list, within the 5e count limit | Too many spells, spell not available to the character |
| `damage` / `heal` | Changes a character's or monster's HP, and moves a character through the life states in section 11. `damage` on a `dying` character adds one death-save failure (two with `--crit`), as in 5e. `damage` on a `stable` character makes it `dying` again | Unknown target. `heal` on a `fallen`, `dead`, or `departed` character |
| `cast` | Spends a spell slot for a caster. A cantrip spends nothing but is still logged. `--slot N` casts at a higher level | No slot of that level left, spell not known or prepared, slot below the spell's level |
| `rest short` / `rest long` | Applies 5e rest rules. Short rest: `--dice <id>:<n>` says how many hit dice each character spends, and the script rolls them. Long rest: HP, slots, half the hit dice, and the once-per-long-rest Grit save | An encounter is active, more hit dice than the character has |
| `item add` / `item remove` | Inventory changes | Removing an item that is not there |
| `gold` | Add or spend gold | Spending more than the character has |
| `xp` | Adds XP. Reports a level-up and applies it from `classes.json` (HP, slots, proficiency, features) up to level 5 | Level above 5 |
| `condition add` / `condition remove` | Standard 5e conditions | Unknown condition |
| `encounter start` | Creates `encounter.json`. Adds monsters from `monsters.json` by name and count, or with `--custom` and DM-supplied stats (which must include a challenge rating or an XP value). Rolls initiative for all | An encounter is already active |
| `encounter add` | Adds combatants to a fight in progress (reinforcements) and rolls their initiative | No active encounter |
| `encounter next` | Advances the turn. Reports whose turn it is | No active encounter |
| `encounter end` | Deletes `encounter.json`. Adds up the XP of defeated monsters, **splits it equally among party members who are not `dead` or `departed` (hero and companions), applies it**, and reports any level-up. `--no-xp` for a fight that was fled or talked down. Story XP goes through `xp` | No active encounter. The hero is `fallen` (run `grit` first) |
| `deathsave` | Rolls one death save for a `dying` character, by the 5e rules: 10 or more is a success, a natural 1 is two failures, a natural 20 gives 1 HP and `alive`. Three successes: `stable`. Three failures: `fallen` for the hero, `dead` for a companion | Character is not `dying` |
| `grit` | The Grit save (section 11). `--dc` is always required. Reads the difficulty and returns the outcome. Any roll, success or failure, uses it up until the next long rest | Character is not the hero, or is not `fallen` |
| `seed choose <name>` / `seed pick` | Records the campaign's seed name in `party.json`. `choose` takes the player's pick. `pick` makes a true random pick, for "surprise me" | Unknown seed name, no seeds found, a seed is already set |
| `character retire` | Marks a character `dead` or `departed`. The sheet stays in the file for the record. For the hero, `--status dead` needs the `--player-accepted` flag, in every difficulty | Unknown id. Hero death without the flag |
| `character promote <id>` | Makes a companion the new hero after the hero is `dead` or `departed`. `party.json` marks exactly one character as the hero at all times | The current hero is not `dead` or `departed`, unknown id |

The architect may merge or rename commands. The table is the required **behaviour**, row by row. Any row that is deferred must be named as deferred in the plan.

**Commands added during the build (2026-09-18).** Each closed a gap that legal 5e play or a playtest exposed. `SKILL.md` is the current command reference, and a test fails if it misses a command.

| Command | Why it was needed |
|---|---|
| `character set` | Quick start could not save background, bond and flaw (playtest 1) |
| `character asi` | The level 4 ability score improvement had no command. A Constitution increase raises HP for every level |
| `spells learn` | A level-up grants cantrip picks and Wizard spellbook picks, and nothing could spend them |
| `stabilize` | A DC 10 Medicine check or a healer's kit must be able to stop death saves |
| `roll --check <ability> --proficient` | Tool proficiency (thieves' tools) adds the bonus in the script, not in the DM's head |
| `track` | Named counters for what the rules engine does not model: the in-world day, a seed's deadline, uses of a feature, item charges. Never below zero. Shown in `status` (playtest 1) |
| `encounter flee` | A monster that runs or yields leaves the turn order and gives no XP (playtest 1) |
| `seed list`, `heal --temp`, `--give-to` on `item remove` and `gold` | Small things a DM needs often |

**Behaviour added by the playtests:** `encounter next` reports the HP of every monster still in the fight. `encounter start` shows each natural initiative die. `rest short` shows the modifier and the sum. `status` shows `grit_available` for the hero. `encounter end` pays no XP when nobody in the party is left standing (`party_defeated`).

**Simplifications, stated so nobody mistakes them for bugs:** monsters use group initiative (one roll per `--monster` entry). Ancestry (race) has no mechanical effect. Starting gold is a fixed 10 gp on top of the class's gear. Each class has its one SRD subclass, with no choice. Skills are the class's count from the class list plus any two for the background.

## 10. Rules scope and data

- **Rules:** D&D 5e SRD 5.1, trimmed core. Six abilities, proficiency, AC, HP, advantage and disadvantage, saving throws, skills, spell slots, conditions, rests, death saves, XP levelling.
- **Licence:** SRD 5.1 is CC-BY-4.0. Ship the attribution in `LICENSE-SRD.md`. Use **no Wizards product identity**: no Beholder, Mind Flayer, Forgotten Realms names, or similar. The world is original.
- **Data size, first version:** 4 classes (Fighter, Rogue, Wizard, Cleric) for levels 1 to 5. About 40 spells (cantrips to level 3, Wizard and Cleric lists). About 40 monsters, challenge rating 0 to 5. SRD weapons, armour, and basic gear.
- **One source of truth.** The script and the model use the same numbers. `dm.py cast` knows a level 3 Wizard has two 2nd-level slots because `classes.json` says so.
- A lookup returns one compact record of about 100 tokens (for a monster: AC, HP, speed, attacks, saves, a one-line tactic), never a whole file.
- Adding a class, spell, or monster is a data change with no code change.
- The DM may invent monsters with `encounter start --custom`. The data is a base, not a cage.

## 11. Stakes

- **Dice are always open.** Every roll is shown with true numbers, for example `d20 (14) + 5 = 19 vs AC 15: hit`. There are no hidden DM rolls that change an outcome. `log.jsonl` is the proof.
- **The DM never changes a roll.** Mercy comes only from the fiction: the enemy takes prisoners, a companion steps in, there is a way to run. `SKILL.md` states this as a firm rule, because a model's instinct is to be kind and that makes the game soft.
- **Death saves** are standard 5e and script-rolled.

**Life states.** Each character has one life state in `party.json`, and only `dm.py` changes it.

| State | Meaning | Enters when | Leaves when |
|---|---|---|---|
| `alive` | Above 0 HP | Start, or any gain of HP from 0 | HP reaches 0 |
| `dying` | 0 HP, unconscious, making death saves | `damage` takes HP to 0, or `damage` hits a `stable` character | 3 successes (`stable`). Any gain of HP, including a natural 20 (`alive`). 3 failures, or outright death by massive damage (hero: `fallen`, companion: `dead`) |
| `stable` | 0 HP, unconscious, no more saves | 3 death-save successes, or a Grit outcome of `light_cost` or `heavy_cost` | Any gain of HP, from `heal` or from a rest that restores HP (`alive`). A rest that restores no HP leaves the character `stable`. New damage (`dying`) |
| `fallen` | **Hero only.** By the 5e rules the hero is dead. The Grit save decides what that means | 3 death-save failures, or `damage` that kills outright by the 5e massive-damage rule | `grit` is run |
| `dead` | True death. Final | The hero: a `grit` outcome of `dead`, or `character retire --player-accepted`. A companion: wherever the hero would become `fallen`, or `character retire` | Never |
| `departed` | Left the party | `character retire` | Never |

- **The Grit save (house rule, the hero only).** When the hero is `fallen`, the DM runs `dm.py grit --dc N`. Base DC 10. The DM may raise it for massive damage or a hostile place with no help near. The script rolls one Constitution saving throw, reads the difficulty, and returns one outcome. It is available once per long rest. If it was already used since the last long rest, the script makes **no roll** and treats it as a failure. The numbers are a first draft to tune in playtest.

| Difficulty | Grit success | Grit failure (or already used) |
|---|---|---|
| `story` | `light_cost` | `light_cost`. The hero cannot truly die |
| `standard` | `light_cost` | `heavy_cost`. True death only if the player accepts it, or made a reckless choice after a clear warning. The DM then runs `character retire` |
| `iron` | `light_cost` | `dead` |

- After `light_cost` or `heavy_cost` the script sets the hero to `stable` at 0 HP. The DM narrates the cost and applies any part of it that is a number through the normal commands (`item remove`, `gold`, `character retire` for a companion).
- **Light costs:** a scar, lost gear, lost gold, lost time.
- **Heavy costs** the DM chooses from, to fit the fiction: captured, saved at a price, a permanent loss, a companion dies in the hero's place, a debt to a dark power.
- **Companions** have no Grit save and never enter `fallen`. Where the hero would become `fallen`, the script sets a companion straight to `dead`, in every mode.
- If the hero is `dead`, the campaign ends, or the player continues with a promoted companion (`character promote`) or a new hero (`character create`, then `character promote`). The DM offers these.
- On `story` difficulty the Grit save can never return `dead`. A true death is still possible in every difficulty if the player asks for it, through `character retire --player-accepted`.

## 12. The party

- One hero the player controls, plus 1 or 2 companions the DM plays. Companions have full sheets in `party.json`, made with the same `character create` command.
- At character creation the DM offers the 2 or 3 companion candidates from the chosen seed, each with a hook. The player picks one or two, or starts alone and meets them in the story.
- In a fight the player gives short orders ("Kira, flank him"). The DM decides the details and the script rolls.
- Companions can die, leave, or betray. Their private motives live in `dm-secrets.md`.

## 13. World, metaplot, and seeds

Brad's design. The skill ships **one original world**, the same for every player and every campaign, with **one hidden metaplot** and **5 seeds**. Each seed is a front door: a different start place and local story that leads into the same metaplot. Replay means a new door into the same larger mystery.

| File | Contents | Audience |
|---|---|---|
| `world/bible.md` | Regions, factions, gods, history, tone. What a person who lives there knows | The DM. Parts are safe to tell the player |
| `world/metaplot.md` | The hidden truth, who is behind it, what they want, the clock (what happens as time passes), 4 or 5 revelations | DM only |
| `seeds/<name>.md` | 1 or 2 pages. Start place, opening scene, a local villain with a motive, 2 or 3 companion candidates, local secrets, what happens if the hero does nothing, and **which metaplot revelations this door leads to** | DM only |
| `seeds/teasers.md` | One spoiler-free sentence per door | The only seed text shown to the player |

- A seed is a **situation, not a script**. The DM improvises inside it.
- Each seed exposes a different slice of the metaplot. No single seed reveals all of it.
- **Tone: broad.** The base is a classic fantasy frontier with a wrong note under it, so 5e rules and SRD monsters fit unchanged. The metaplot is a slow mystery, not a dark lord. Each seed can carry its own tone (one comic, one dread, one intrigue, and so on). The player's tone answers tune the DM further.
- **Authorship and the spoiler wall.** Brad shapes and approves `world/bible.md` and `seeds/teasers.md`. Claude writes `world/metaplot.md` and the 5 seed files, and **Brad does not read them**. A review agent checks those files for quality, internal consistency, consistency with the bible, and SRD product-identity problems. Brad sees the verdict, not the text. **Any agent or session working in this repo must not quote or summarise the contents of `metaplot.md` or `seeds/<name>.md` to Brad** unless he asks to open them.
- **The wall covers derived material too:** the `dm-secrets.md` of any test campaign, playtest transcripts, auditor reports, and diffs of the secret files. Test campaigns and transcripts live in the gitignored `playtests/` folder. Auditor and reviewer reports to Brad give verdicts and rule violations with no plot content. Commit messages for the secret files are generic ("add seed 3"). Do not show Brad a diff of a secret file.

## 14. DM behaviour (content of `SKILL.md` and `reference/`)

**Firm rules (low freedom):**

1. Run `dm.py --version` first in every session.
2. Every number goes through `dm.py`. Never invent a roll. Never do state arithmetic in prose. Never edit a JSON file.
3. Never change a roll. Show every roll openly.
4. Never act, speak, or feel for the hero.
5. Write one line to `journal.md` at **every scene change**, not only at session end.
6. Never reveal `dm-secrets.md`, `metaplot.md`, or seed files to the player.

**Style (high freedom), for `reference/dm-style.md`:**

- Turns of 80 to 150 words as the norm. Longer only for an opening scene or a large revelation.
- Every turn ends on a moment that demands a player action.
- No option lists by default. If the player asks "what can I do?", give 3 ideas.
- Say yes to creative plans: set a DC and roll. A failure makes a new problem and does not stop the scene.
- Named characters have a voice, a want, and one specific detail. They sometimes lie.
- Use all the senses. Plant clues early and pay them off later.
- The balance of fights, talk, and exploration follows the player's tone answers.
- The villain acts in the background between sessions. The world does not wait.
- **Content:** "PG-13 adventure" by default. Violence and dread are in, gore is kept short, no sexual content, cruelty to children and similar themes stay out of scene. The player can set it darker at campaign start (the horror tone gets more dread and body horror, inside the model's normal limits).

## 15. Session flow

| Moment | Behaviour |
|---|---|
| First time | The player opens an empty folder and says "let's play D&D" or similar. Then the six setup steps in section 8: self-test and `init`, the 3 or 4 questions on tone, difficulty and content with `settings set`, the 5 teasers with `seed choose` or `seed pick` ("surprise me"), the seed copy into `dm-secrets.md`, character creation and companion choice, the opening scene |
| Character creation | Guided, about 5 minutes: class, name, ability scores (standard array or script-rolled), a one-sentence background, one bond, one flaw. `--quick` for a ready hero |
| Continue | The player opens the campaign folder and says "continue". The DM runs `status`, reads `journal.md`, `world.md`, `dm-secrets.md`, gives a 3 or 4 sentence in-fiction recap, and resumes from the last scene |
| Stop | "Let's stop here." The DM writes the journal entry, updates `world.md`, updates the plan in `dm-secrets.md` (including what the villain did in the background), and confirms the save |
| Crash or full context | Numbers are already on disk. The fiction loses at most the scene in progress. A new chat resumes from the files |
| Out-of-fiction requests | Plain words: "show my sheet", "what's in my pack", "what do I know about the Baron". Answered from `sheet` and `world.md` |
| Journal growth | `status` reports the size of `journal.md`. Past a limit set in `session-flow.md`, the DM folds old entries into a "previously" summary |

The skill `description` must trigger on phrases such as "let's play D&D", "start a campaign", "continue my campaign", and must not trigger on an unrelated D&D rules question.

## 16. Testing and acceptance

| Layer | Method | Pass condition |
|---|---|---|
| 1. `dm.py` and data | `unittest` (stdlib), test-first. One test group per row of the section 9 table, including every "refuses when" case. The write guard. The Grit save. Seeded dice. Data tests: every class, spell, and monster record is complete and legal, and no record uses a product-identity name | All pass. Hard gate before every commit |
| 2. Host boot test | In Claude Code, then Cowork local, then Cowork cloud: the skill triggers, `--version` runs, `init` makes the five files, a script-written file is present in the next session | Checklist passes in all three. **Brad runs the two Cowork tests** |
| 3. DM behaviour | Two runs by a player sub-agent that works from only the skill and a campaign folder. **Free run:** 15 to 20 turns from a new campaign. **Death run:** the test setup uses the normal commands to put the hero at 1 HP at the start of a hard fight, so that the death path is reached with true dice and no seeding. An auditor agent checks both transcripts and the save files against the six firm rules in section 14, plus: turns are short, and in the death run the life states and the Grit save ran as section 11 says | Checklist passes. A failure becomes a `SKILL.md` change and a re-run |
| 4. Trigger tests | Two phrases that must start the skill, one that must not | 3 of 3 |
| 5. Secret content review | The review agent's verdict on `metaplot.md` and the seeds | Pass, with no spoilers shown to Brad |

**Done means:** layers 1, 3, 4, 5 pass, the Claude Code boot test passes, and the plugin is installed in Brad's Cowork. **"Is it fun" is reported as unverified** until Brad plays a real session. The Cowork boot results are reported as unverified until Brad runs them.

## 17. Distribution

- Private GitHub repo now. The metaplot and seeds are spoilers and the world is Brad's creative work. He makes it public when he decides to share.
- While the repo is private, a person installs from a **file**: Brad sends them `dist/tabletop-dm-plugin.zip`, and they upload it as a custom plugin in Cowork (Customize > Plugins) or add it in Claude Code. When the repo goes public, they can also add the GitHub repo as a plugin marketplace. The exact upload format Cowork accepts is confirmed in M7.
- claude.ai chat: not supported (no folder for the save game). The skill zip is for Cowork, or for any host that takes a bare skill.
- Skill name is `tabletop-dm` for now. Rename to the world's name before a public release. The **name** avoids the Wizards trademarks "D&D" and "Dungeons & Dragons". The **description** may mention D&D-style play for triggering. "Compatible with fifth edition" is the allowed phrase.
- Licence for Brad's own content is decided at release time. SRD-derived numbers stay CC-BY-4.0.
- "Deploy" for this project means: tag a release, build the zip, install the plugin in Brad's Cowork.

## 18. Build order

0. **M0, the Cowork check (Brad, 2 minutes, before any code):** in Cowork local mode and again in cloud mode, ask it to run `python3 --version` and to write a small file into the opened folder. Open a new session and look for the file. A failure here changes the script language or the save design, so it comes first.
1. **M1, the script core:** the JSON schemas, then `dm.py` with `--version`, `init` and the write guard, `settings set`, free-form `roll`, `status`, the log. Tests first.
2. **M2, data and characters:** the four data files, `lookup`, `character create`, `sheet`, `equip`, `spells prepare`, named `roll`, `xp` and levelling.
3. **M3, play state:** `damage`, `heal`, the life states, `cast`, `rest`, `item`, `gold`, `condition`, `encounter` (start, add, next, end), `deathsave`, `grit`, `seed choose` and `seed pick` (tested against fixture seeds), `character retire`, `character promote`.
4. **M4, the skill:** `SKILL.md` and the four `reference/` files. Claude Code boot test. Trigger tests.
5. **M5, the world:** Brad shapes `bible.md` and `teasers.md` with Claude. Claude writes `metaplot.md` and 5 seeds behind the spoiler wall. Review agent.
6. **M6, playtest loop:** player agent and auditor. Fix `SKILL.md`. Repeat until the checklist passes.
7. **M7, package:** `plugin.json`, `build.py`, `README.md`, `LICENSE-SRD.md`. Install in Cowork. Brad runs the two Cowork boot tests.

M5 does not depend on M1 to M4 and can run in parallel.

## 19. Risks and open items

| # | Item | Plan |
|---|---|---|
| 1 | Python or file persistence could fail in a Cowork mode | **Closed for the mode Brad uses** (2026-09-19): the skill loaded, Python ran, a full session was played, and "continue" resumed the save after `/new`. The second Cowork mode is untested. The Node port fallback was not needed |
| 2 | The model drifts from the firm rules in a long session (does arithmetic itself, skips journal lines) | The M6 playtest audits exactly this. `status` output is compact so that re-grounding is cheap |
| 3 | The model is too kind and softens the stakes | Firm rule 3, the Grit save as a real mechanic, and the auditor check |
| 4 | Grit save numbers are a first draft | Tune in playtest |
| 5 | The world's name, and with it the final skill name | Decided in M5 |
| 6 | A skill update changes data under a campaign in progress | The seed and plan are copied into the campaign during setup (section 8, step 4). `party.json` carries a format version so `dm.py` can migrate or refuse clearly |
