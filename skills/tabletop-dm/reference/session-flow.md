# Session flow

## Contents

- First time: the six setup steps
- The format of seeds/teasers.md
- Character creation
- Companions
- The opening scene
- Continue
- Stop
- Journal format and growth
- After a crash or a full context
- Out-of-fiction requests

`C` stands for `--campaign <folder>`.

## First time: the six setup steps

Do these in order. Keep it friendly and quick: the player came to play, not to fill in forms.

**Step 1. Self-test and init.** Run `--version`, then `init C`. If `init` is refused with `write_guard_failed`, the folder is not empty. Ask the player to make a new empty subfolder, open it, and say "let's play" again. Do not make the folder yourself.

**Step 2. Four setup questions, then `settings set`.** Ask them together, in one short message. State each default, and say the player can answer "defaults" to take all four:

| Question | Choices | Default | Recorded as |
|---|---|---|---|
| Tone | heroic, grim, comic, horror, intrigue, or a mix in the player's words | heroic | `--tone genre=<their word or words>` |
| Balance of play | fights, talk, exploration, even | even | `--tone balance=<choice>` |
| Difficulty | `story` (the hero cannot truly die, costs are light), `standard` (death changes the story, costs are real), `iron` (death is final) | standard | `--difficulty <choice>` |
| Length | one-shot (one session), campaign (about 10 sessions) | campaign | `--tone length=<choice>` |

The content level is `pg13` and you do not ask about it. Only if the player's tone answer was grim or horror, ask ONE follow-up: "Do you want it darker than PG-13: heavier dread and bleaker costs?" A yes is `--content-level pg13-dark`.

The `--tone` values are free text for you to read back later. Keep each one short, and use the player's own words when they gave some ("grim but hopeful" becomes `genre=grim-but-hopeful`).

Record the answers in one command:
`settings set C --difficulty standard --tone genre=grim --tone balance=talk --tone length=campaign`

**Step 3. The doors.** Read `seeds/teasers.md` (its format is below). Show the player every teaser, numbered 1, 2, 3 and so on: show the teaser text only, and never the seed's file name. Say that every door leads into the same larger world, so a later campaign can take a different door. The player picks one, or says "surprise me".
- A pick: `seed choose <name> C`.
- Surprise me: `seed pick C`. Show the roll.

**Step 4. Prepare in secret.** Read `world/bible.md`, `world/metaplot.md`, and the chosen `seeds/<name>.md`. Then write `dm-secrets.md`:
- Under `## Seed`: copy the whole seed file.
- Under `## Campaign plan`: 8 to 12 lines for THIS campaign, shaped by the tone answers. The local villain's next three moves if nobody stops them. Three scenes you expect. Which metaplot revelations this door can reach, and the clue that points to each. What the villain does between sessions.
- Under `## Companion motives`: leave empty until step 5.

Say nothing about this file to the player. From now on, the copy in `dm-secrets.md` is the truth for this campaign, even if the skill's seed files change later.

**Step 5. Character creation and companions.** See the sections below.

**Step 6. The opening scene.** See below. Then write the first journal line.

## The format of seeds/teasers.md

One line for each door: `<seed file name without .md>: <the teaser sentence>`. For example `the-mill: A mill town where the goblins steal only grain.` The part before the colon is what you pass to `seed choose`. The part after the colon is the only seed text a player may see.

## Character creation

About five minutes. Ask one thing at a time, and offer "quick start" first: a ready hero in one step.

**Quick start:** ask only for a name and a class. Run
`character create C --name "..." --class rogue --quick`
Then ask for a one-sentence background, one bond and one flaw, in the player's words. (If they shrug, offer two of each that fit the seed's start place.) Save them on the sheet:
`character set C --who mara-voss --background "..." --bond "..." --flaw "..."`

**Guided:**
1. **Class.** Fighter, Rogue, Wizard or Cleric. One line each on how it plays. `lookup class <name> --level 1` gives you the facts.
2. **Name and look.** Any ancestry the player likes. It shapes the story and not the numbers.
3. **Ability scores.** The player chooses:
   - The standard array 15, 14, 13, 12, 10, 8, assigned as they like. Add `--standard-array`.
   - Rolled: run `roll C "4d6kh3" --reason "ability score"` six times, show every roll, and let the player assign the six totals.
   Pass them as `--scores str,dex,con,int,wis,cha`.
4. **Skills.** Offer the class defaults. A player who wants to choose picks the class's number from the class list, plus any two more for their background: `--skills a,b,c,d`.
5. **Class choices.** Fighter: a fighting style (`--fighting-style`). Rogue: two skills for expertise (`--expertise`). Wizard and Cleric: offer the default spells, or let the player pick with `--cantrips` and `--spells` (`lookup spell --list --class wizard --level 1`).
6. **Background, bond, flaw.** One sentence each: `--background`, `--bond`, `--flaw`. Use the bond and the flaw in play. They are hooks, not decoration.

Show the finished sheet in a short, readable form: abilities, AC, HP, attacks, skills, spells, gear, gold. Not the raw JSON.

## Companions

The seed names two or three companion candidates. Introduce each in two sentences **in the fiction**, with a reason to travel with the hero. Do not show their secrets. The player picks one or two, or none.

For each pick, run `character create` with a class that fits, `--quick`, and the hero's level. Then write their private motive under `## Companion motives` in `dm-secrets.md`: what they want, what they hide, and what would make them leave or turn.

The player can also start alone and meet companions later. A companion who joins later is made at the hero's current level with `--level N`.

**Playing companions.** They have opinions, and they speak up without being asked, briefly. In a fight the player gives short orders ("Kira, flank him"), and you decide the details and roll for them with the script. A companion never solves the hero's problem for them, and never makes the hero's choices.

## The opening scene

Start in motion, at the seed's start place, with a problem already arriving. Use the hero's bond or flaw within the first three turns. This is the one turn that may run long: up to about 250 words. End it on a choice.

## Continue

1. Run `--version`, then `status C`.
2. Read `journal.md`, `world.md` and `dm-secrets.md`. Read the DM style reference that SKILL.md links to before the first scene.
3. If `status` shows an active fight, the session stopped in the middle of it. Read the last journal lines, and resume the fight on the turn that `status` reports.
4. Give a recap of three or four sentences, **in the fiction** ("Previously..."), and end it on the situation the hero is in right now.
5. Move the world forward first: in `dm-secrets.md`, note what the villain did while the hero rested. Let one sign of it show in the first scene.
6. Ask what the hero does.

## Stop

When the player says "let's stop here", or similar:

1. Bring the scene to a resting point if one is a turn away. Do not force one.
2. Under today's date heading in `journal.md`, add a session summary of one short paragraph: what happened, what changed, what is unresolved. **Then re-read that paragraph and delete anything the hero does not know.** This is the moment a secret most easily leaks: a villain's deadline, a companion's motive, the true cause of something. The journal is the player's file.
3. Update `world.md`: new people, places and factions, and the list of open quests.
4. Update `dm-secrets.md`: which clues were found, what the villain does next, how each companion's motive moved.
5. Run `status C`, and tell the player in one line that the game is saved and how to come back: open this folder and say "continue".

## Journal format and growth

```
## 2026-09-18, session 3

- A dockside tavern. Mara took the ledger job from the fixer. Brann distrusts him.
- The customs house, night. Got the ledger. A guard saw Mara's face. Fled over the roofs.

Session summary: one short paragraph, written at Stop.
```

- **One line at every scene change**: where, what happened, what changed. Write it the moment the scene changes, before you describe the next one.
- The journal is for the player to read. Never put a secret in it.
- `status` reports `journal_bytes`. When it passes **30000**, fold every session except the last two into one section at the top, `## Previously`, of 15 lines at most. Keep names, debts, promises and open threads. Drop the blow-by-blow.

## After a crash or a full context

The numbers are always safe, because the script writes each change to disk at once. A new chat resumes with **Continue**. The most the player can lose is the scene that was in progress. If the last journal line and `status` disagree (for example the journal says the fight ended but `status` shows it active), trust `status` for the numbers, tell the player briefly what you see, and ask how the scene ended.

## Out-of-fiction requests

The player uses plain words, and there are no menus.

| The player says | You do |
|---|---|
| "Show my sheet", "what's in my pack", "how many slots do I have" | `sheet <id> C` or `status C`, shown in a short readable form |
| "What do I know about the Baron?" | Answer from `world.md` and the journal. Only what the hero has learned |
| "What can I do?" | Three concrete ideas that fit the scene. Then ask again |
| "Can I roll for that?", a rules question | A short, plain answer. Then back to the scene |
| "Make it harder / lighter / darker" | `settings set C ...`, and say what changed |
| "Undo that" | The log is append-only and there is no undo. If a number is wrong because of YOUR mistake, fix it openly with the normal commands and say so. Never rewrite a roll |
