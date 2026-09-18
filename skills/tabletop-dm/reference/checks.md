# Checks outside a fight

`C` stands for `--campaign <folder>`.

## When to roll

Roll only when **all three** are true:

1. The outcome is uncertain.
2. Failure would be interesting, not a dead end.
3. There is a cost to trying, or the hero cannot simply try again.

If the hero has time, tools and no pressure, they succeed. If the thing is impossible, say so in the fiction. Never roll to find the clue the story needs: give it, and roll for how much more the hero learns, or what it costs.

## The roll

`roll C --who mara-voss --check stealth --dc 13`

The script adds the bonus from the sheet. Pass a skill (`stealth`, `persuasion`, `sleight-of-hand`) or a bare ability (`str`, `int`) when no skill fits. Say the DC aloud before the roll when the hero could judge the difficulty, and show the result openly: `d20 (9) + 6 = 15 vs DC 13: success`.

## Setting a DC

| DC | Difficulty | An example |
|---|---|---|
| 5 | Very easy | Climb a knotted rope |
| 10 | Easy | Calm a nervous horse |
| 13 | Moderate | Pick a decent lock, track a day-old trail |
| 15 | Hard | Talk a guard into breaking a small rule |
| 18 | Very hard | Leap a wide gap in armour |
| 20 | Formidable | Forge a royal seal from memory |
| 25 | Nearly impossible | Swim up a waterfall |

Most checks at levels 1 to 5 sit between 10 and 15. Set the DC from the fiction, and never from what the hero's bonus happens to be.

## Advantage and disadvantage

Add `--adv` when the hero has a real edge: a clever plan, the right tool, help from a companion, leverage over the person they are talking to. Add `--disadv` for a real handicap: darkness, a wound, rushing, a hostile crowd. One of each cancels. Reward a good idea with advantage more often than with a lower DC: the player can see advantage, and it feels earned.

## Failing forward

A failed check never means "nothing happens". Choose one:

- **Success at a cost.** The lock opens, and the pick snaps inside it. The guard agrees, and wants a favour later.
- **A new problem.** The hero is over the wall, and the dogs are awake.
- **Partial truth.** The hero reads half the inscription, and the wrong half.
- **The clock moves.** It worked, and it took all night. Note what the villain did with the time.

Do not allow the same check twice in the same situation. A second try needs a new approach, and the first failure has already changed the situation.

## Kinds of check

- **Opposed.** Two rolls, the higher wins: the hero's `--check stealth` against a guard's `roll C "1d20+2" --reason "guard perception"`. A tie keeps things as they were.
- **Passive Perception.** Every sheet has `passive_perception`. Use it, with no roll, to decide what a character notices without looking. Monsters have 10 plus their Wisdom modifier. Roll only when someone is actively searching.
- **Group.** Everyone rolls, and the group succeeds if at least half do. Use it for sneaking or travelling together.
- **Helping.** A companion who could plausibly help gives the hero advantage.
- **Knowledge** (`arcana`, `history`, `religion`, `nature`). A success gives a true and useful fact. A failure gives less, never a lie, unless a lie is what the source would tell.
- **Social** (`persuasion`, `deception`, `intimidation`, `insight`). First decide what the character wants and fears. No roll makes someone act against their nature. A success moves them one step: hostile to wary, wary to helpful. Play the conversation first, and roll at the moment it could go either way. The player's actual words set the DC, or earn advantage.
- **Tools.** Picking a lock or disarming a trap is a `dex` check, and thieves' tools are needed to try at all. A Rogue with the tools is proficient, so add `--proficient`: `roll C --who mara-voss --check dex --proficient --dc 15`. The script adds the proficiency bonus. Use the same flag for any tool or kit a character's background makes them good with.

## Travel, time and money

- Keep travel short unless the journey is the adventure. One scene per leg of a journey is enough: a choice, an encounter or a discovery.
- Track days loosely in `journal.md`. The villain's plan in `dm-secrets.md` runs on that clock.
- Prices come from `lookup equipment <name>` (`cost_cp`: 100 cp is 1 gp). A night at a modest inn is about 5 sp, and a good meal about 3 sp. Buying: `gold --spend`, then `item add`. Selling used gear pays half.
