# tabletop-dm Build Plan

Source: the code-architect blueprint of 2026-09-18. Schemas, module layout, command contracts and test layout are in `docs/ARCHITECTURE.md`.
M0 (before any code) is Brad's 2-minute Cowork check, PRD section 18.

## PART 5 — Task List Per Milestone

Each task is one thing, verified before the next task starts (TDD: test written and red, then made green). Task IDs `M<n>-T<k>`.

### M1 — script core

- **M1-T1** Scaffold `scripts/dm.py` + empty `dmlib/` modules with docstrings only. *Verify:* `python3 /abs/path/scripts/dm.py --help` runs with no `ImportError`, invoked from `/tmp` and from repo root.
- **M1-T2** `dmlib/errors.py` (`DmError`, envelopes). *Test:* `TestErrors`.
- **M1-T3** `dmlib/dice.py` free-expression roller (`NdM+K`, `khN`/`klN`). *Test:* `TestDiceExpr` (seeded, exact rolls asserted).
- **M1-T4** `dmlib/dice.py` d20 with advantage/disadvantage (keep-higher/lower of two rolls). *Test:* part of `TestDiceExpr` or a dedicated `TestDiceD20Advantage`.
- **M1-T5** `dmlib/io_campaign.py` write guard (empty / dotfiles-only / unrelated file / existing valid party.json / existing corrupt party.json). *Test:* `TestWriteGuard`.
- **M1-T6** `dmlib/io_campaign.py` atomic write + load + corrupt-file report. *Test:* `TestIoCampaign` (part of `test_io_campaign.py`).
- **M1-T7** `dmlib/io_campaign.py` `append_log` + line-count-based `seq`. *Test:* same file, log-append cases.
- **M1-T8** Minimal fixture `data/*.json` (2-3 records each) for M1-scope tests. *Verify:* `TestDataFixtures` loads without error.
- **M1-T9** `dmlib/cmd_setup.py: version()` self-test. *Test:* `TestVersionCommand`.
- **M1-T10** `dmlib/cmd_setup.py: init()` (five files, correct templates, write guard wired in). *Test:* `TestInitCommand`.
- **M1-T11** `dmlib/cmd_setup.py: settings_set()`. *Test:* `TestSettingsSet`.
- **M1-T12** `dmlib/cmd_roll.py`: free-form `roll <expr>` CLI wrapper, log-only write. *Test:* `TestRollFreeCommand`.
- **M1-T13** `dmlib/cmd_setup.py: status()` read-only summary (empty-party edge case). *Test:* `TestStatusCommand`.
- **M1-T14** `dmlib/cli.py` argparse wiring, `dispatch`/`run`, unknown-command handling. *Test:* `TestCliDispatch`.
- **M1-T15** format-version migration scaffold (`CURRENT_FORMAT_VERSION`, no-op chain, too-new refusal). *Test:* `TestFormatVersionMigration`.

### M2 — data and characters

- **M2-T1** `dmlib/rules_tables.py` constants. *Test:* `TestRulesTables`.
- **M2-T2** Real `data/classes.json` (4 classes, levels 1-5) + `data.load_classes`/validation. *Test:* `TestClassesDataCompleteness` (real), plus fixture-level `TestData`.
- **M2-T3** Real `data/spells.json` (~40 spells). *Test:* `TestSpellsDataLegality`.
- **M2-T4** Real `data/monsters.json` (~40 monsters, CR 0-5). *Test:* `TestMonstersDataCompleteness`.
- **M2-T5** Real `data/equipment.json` (SRD weapons/armor/gear). *Test:* `TestEquipmentDataLegality`.
- **M2-T6** Banned-names scan across all 4 real files. *Test:* `TestNoProductIdentityNames`.
- **M2-T7** `dmlib/derive.py`: ability modifiers, proficiency bonus. *Test:* `TestDeriveAbilityAndProficiency`.
- **M2-T8** `dmlib/derive.py`: saves, skills. *Test:* `TestDeriveSavesAndSkills`.
- **M2-T9** `dmlib/derive.py`: AC from equipped armor/shield/dex cap. *Test:* `TestDeriveAC`.
- **M2-T10** `dmlib/derive.py`: per-weapon attack bonus/damage. *Test:* `TestDeriveAttacks`.
- **M2-T11** `dmlib/derive.py`: spell save DC/attack bonus/slots for Wizard, Cleric. *Test:* `TestDeriveSpellcasting`.
- **M2-T12** `dmlib/cmd_character.py: character_create()` (standard array + explicit `--scores`, starting gear/gold roll, default spells, hero vs. companion, `--level N`, `--quick`). *Test:* `TestCharacterCreate`.
- **M2-T13** `dmlib/cmd_lookup.py: lookup()` (+ `--list`, near-match suggestions). *Test:* `TestLookupCommand`.
- **M2-T14** `dmlib/cmd_setup.py: sheet()`. *Test:* `TestSheetCommand`.
- **M2-T15** `dmlib/cmd_character.py: equip()/unequip()` (AC/attack recompute, non-proficiency reported not refused). *Test:* `TestEquipUnequip`.
- **M2-T16** `dmlib/cmd_character.py: spells_prepare()` (count limit, availability). *Test:* `TestSpellsPrepare`.
- **M2-T17** `dmlib/cmd_roll.py`: named forms (`--attack`/`--check`/`--save`/`--initiative`) pulling from the sheet. *Test:* `TestRollNamedCommand`.
- **M2-T18** `dmlib/cmd_character.py: xp()` + level-up application, level-cap refusal. *Test:* `TestXpAndLevelUp`.

### M3 — play state

- **M3-T1** `dmlib/life_states.py: apply_damage()` (alive→dying, repeat-failure-while-dying, stable→dying, massive-damage formula). *Test:* `TestLifeStatesDamage`.
- **M3-T2** `dmlib/life_states.py: apply_heal()`. *Test:* `TestLifeStatesHeal`.
- **M3-T3** `dmlib/cmd_play.py: damage()/heal()` CLI wrappers, incl. monster targeting during an active encounter. *Test:* `TestDamageHealCommand`.
- **M3-T4** `dmlib/life_states.py: apply_death_save()` (nat1, nat20, ≥10, <10, 3-success/3-failure per actor type). *Test:* `TestLifeStatesDeathSave`.
- **M3-T5** `dmlib/cmd_play.py: deathsave()`. *Test:* `TestDeathsaveCommand`.
- **M3-T6** `dmlib/life_states.py: apply_grit()` (per-difficulty table, already-used auto-failure). *Test:* `TestLifeStatesGrit`.
- **M3-T7** `dmlib/cmd_play.py: grit()`. *Test:* `TestGritCommand`.
- **M3-T8** `dmlib/cmd_play.py: cast()` (slot spend, cantrip zero-cost logging, `--slot N` upcast). *Test:* `TestCastCommand`.
- **M3-T9** `dmlib/cmd_play.py: rest_short()`. *Test:* `TestRestShortCommand`.
- **M3-T10** `dmlib/cmd_play.py: rest_long()` (incl. grit reset, stable-with-no-gain edge case). *Test:* `TestRestLongCommand`.
- **M3-T11** `dmlib/cmd_play.py: item_add()/item_remove()` (data-backed + DM-custom loot). *Test:* `TestItemCommands`.
- **M3-T12** `dmlib/cmd_play.py: gold()` (cp-integer backing). *Test:* `TestGoldCommand`.
- **M3-T13** `dmlib/cmd_play.py: condition_add()/condition_remove()`. *Test:* `TestConditionCommands`.
- **M3-T14** `dmlib/cmd_encounter.py: encounter_start()` (data monsters + `--custom`, CR→XP, initiative rolls). *Test:* `TestEncounterStart`.
- **M3-T15** `dmlib/cmd_encounter.py: encounter_add()` (reinforcements, slug counter continuation). *Test:* `TestEncounterAdd`.
- **M3-T16** `dmlib/cmd_encounter.py: encounter_next()` (auto-skip logic). *Test:* `TestEncounterNext`.
- **M3-T17** `dmlib/cmd_encounter.py: encounter_end()` (XP split, level-up cascade, `--no-xp`, hero-fallen refusal). *Test:* `TestEncounterEnd`.
- **M3-T18** `dmlib/cmd_seed.py: seed_choose()/seed_pick()` against fixture seeds only (real seeds arrive M5). *Test:* `TestSeedCommands`.
- **M3-T19** `dmlib/cmd_character.py: character_retire()` (dead/departed, hero `--player-accepted` gate in every difficulty). *Test:* `TestCharacterRetire`.
- **M3-T20** `dmlib/cmd_character.py: character_promote()` (exactly-one-hero invariant). *Test:* `TestCharacterPromote`.

### M4 — the skill

- **M4-T1** Write `SKILL.md` (firm rules from PRD §14, session-flow pointer, trigger `description`). *Verify:* line count <500 (`TestSkillMdLength`, a lightweight structural test, not gameplay logic).
- **M4-T2** Write the four `reference/*.md` files (`combat.md`, `checks.md`, `dm-style.md`, `session-flow.md`); any file >100 lines gets a table of contents. *Verify:* `TestReferenceFilesStructure` (TOC-present check for files over the threshold).
- **M4-T3** Claude Code boot test: skill triggers, `--version` runs, `init` makes five files, a file survives a fresh session. *Verify:* manual/agent-run checklist (PRD layer 2), not unittest.
- **M4-T4** Trigger tests: two phrases that must fire, one that must not. *Verify:* manual/agent-run, 3/3 (PRD layer 4) — this is host-trigger behavior, outside `dm.py`'s reach, so it cannot be a `unittest` case.

### M5 — the world (process only; no story content in this blueprint or in any task description)

- **M5-T1** Brad and Claude jointly shape and approve `world/bible.md` and `seeds/teasers.md` (visible to Brad throughout).
- **M5-T2** Claude drafts `world/metaplot.md` behind the spoiler wall. Brad does not read it. Commit message stays generic ("add metaplot draft").
- **M5-T3** Claude drafts the 5 `seeds/<name>.md` files behind the wall. Commit messages generic ("add seed 1" … "add seed 5"). No diffs shown to Brad.
- **M5-T4** Review agent audits `metaplot.md` + all 5 seeds for quality, internal consistency, bible consistency, and SRD product-identity problems (reusing the same banned-terms check as `TestNoProductIdentityNames`, applied to prose). Reports **verdict only** to Brad — pass/fail plus rule violations, zero plot content.
- **M5-T5** If the verdict fails, Claude revises behind the wall and the review agent re-checks; repeat until pass. *Verify:* review agent's pass verdict, nothing else.

### M6 — playtest loop

- **M6-T1** Free run: player sub-agent plays 15-20 turns from only the skill + a fresh campaign folder (in gitignored `playtests/`). Auditor agent checks the transcript + save files against the six firm rules (PRD §14) and turn-length norm. *Verify:* auditor checklist pass.
- **M6-T2** Death run: test setup uses normal `dm.py` commands to put the hero at 1 HP before a hard fight (true dice from there). Auditor checks life-state transitions and the Grit save ran per section 11. *Verify:* auditor checklist pass, cross-checked against `TestLifeStatesDamage`/`TestLifeStatesGrit` expectations.
- **M6-T3** Any auditor failure becomes a `SKILL.md`/reference change; re-run M6-T1/T2 until both pass.

### M7 — package

- **M7-T1** `.claude-plugin/plugin.json` manifest. *Verify:* valid JSON, name passes the lowercase/hyphen/64-char/no-"claude"/no-"anthropic" rule.
- **M7-T2** `build.py` — two zips (plugin: `.claude-plugin/`+`skills/`; skill: `skills/tabletop-dm/` only), neither containing `tests/`, `playtests/`, `GRILL.md`, `PRD.md`. *Verify:* unzip and list contents, assert exclusions.
- **M7-T3** `README.md`.
- **M7-T4** `LICENSE-SRD.md` (CC-BY-4.0 attribution).
- **M7-T5** Install the plugin zip in Brad's Cowork; Brad runs the two Cowork boot tests (local + cloud). *Verify:* Brad's own confirmation — reported as unverified until he runs it, per PRD §16 "done means."

### Traceability table

| PRD row (§9 / §11) | Task ID | Test class |
|---|---|---|
| `--version` | M1-T9 | `TestVersionCommand` |
| `init` + write guard | M1-T10, M1-T5 | `TestInitCommand`, `TestWriteGuard` |
| `settings set` | M1-T11 | `TestSettingsSet` |
| `status` | M1-T13 | `TestStatusCommand` |
| `sheet <id>` | M2-T14 | `TestSheetCommand` |
| `roll` (named + free) | M1-T12, M2-T17 | `TestRollFreeCommand`, `TestRollNamedCommand` |
| `lookup <kind> <name>` | M2-T13 | `TestLookupCommand` |
| `character create` | M2-T12 | `TestCharacterCreate` |
| `equip` / `unequip` | M2-T15 | `TestEquipUnequip` |
| `spells prepare` | M2-T16 | `TestSpellsPrepare` |
| `damage` / `heal` | M3-T3 (logic: M3-T1, M3-T2) | `TestDamageHealCommand` (+ `TestLifeStatesDamage`, `TestLifeStatesHeal`) |
| `cast` | M3-T8 | `TestCastCommand` |
| `rest short` / `rest long` | M3-T9, M3-T10 | `TestRestShortCommand`, `TestRestLongCommand` |
| `item add` / `item remove` | M3-T11 | `TestItemCommands` |
| `gold` | M3-T12 | `TestGoldCommand` |
| `xp` | M2-T18 | `TestXpAndLevelUp` |
| `condition add` / `condition remove` | M3-T13 | `TestConditionCommands` |
| `encounter start` | M3-T14 | `TestEncounterStart` |
| `encounter add` | M3-T15 | `TestEncounterAdd` |
| `encounter next` | M3-T16 | `TestEncounterNext` |
| `encounter end` | M3-T17 | `TestEncounterEnd` |
| `deathsave` | M3-T5 (logic: M3-T4) | `TestDeathsaveCommand` (+ `TestLifeStatesDeathSave`) |
| `grit` | M3-T7 (logic: M3-T6) | `TestGritCommand` (+ `TestLifeStatesGrit`) |
| `seed choose` / `seed pick` | M3-T18 | `TestSeedCommands` |
| `character retire` | M3-T19 | `TestCharacterRetire` |
| `character promote` | M3-T20 | `TestCharacterPromote` |
| Life state: damage transitions incl. massive damage | M3-T1 | `TestLifeStatesDamage` |
| Life state: heal transitions | M3-T2 | `TestLifeStatesHeal` |
| Life state: death saves (nat1/nat20/3-succ/3-fail) | M3-T4 | `TestLifeStatesDeathSave` |
| Life state: Grit per difficulty, already-used | M3-T6 | `TestLifeStatesGrit` |
| Life state: rest HP-gain vs. no-gain | M3-T9, M3-T10 | `TestRestShortCommand`, `TestRestLongCommand` |
| Life state: retire/promote hero invariants | M3-T19, M3-T20 | `TestCharacterRetire`, `TestCharacterPromote` |
| Data integrity: classes/spells/monsters/equipment | M2-T2..T5 | `TestClassesDataCompleteness`, `TestSpellsDataLegality`, `TestMonstersDataCompleteness`, `TestEquipmentDataLegality` |
| Data integrity: no product-identity names | M2-T6 | `TestNoProductIdentityNames` |
| Format-version migration | M1-T15 | `TestFormatVersionMigration` |
| SKILL.md / reference structure | M4-T1, M4-T2 | `TestSkillMdLength`, `TestReferenceFilesStructure` |
| Host boot test | M4-T3 | manual/agent checklist (not unittest) |
| Trigger tests | M4-T4 | manual/agent checklist (not unittest) |
| World/metaplot/seeds (process) | M5-T1..T5 | review-agent verdict only (not unittest) |
| DM behaviour playtest (free + death run) | M6-T1, M6-T2, M6-T3 | auditor checklist (not unittest) |
| Packaging | M7-T1..T4 | zip-content assertions (lightweight, not full unittest gate) |
| Cowork install/boot | M7-T5 | Brad's manual confirmation |

**Deferred rows: none.** Every row in PRD §9 and §11 has a task and a test class above; nothing was pushed out of scope.

---
