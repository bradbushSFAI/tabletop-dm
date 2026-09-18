# Running a fight

## Contents

- Before the fight: is this a fight, and how hard
- Start
- A party member's turn
- A monster's turn
- Spells
- Special rules the script does not apply for you
- Dying, death saves and the Grit save
- When the whole party is down
- Ending the fight
- Rests
- Keeping a fight fast in text

`C` stands for `--campaign <folder>`.

## Before the fight: is this a fight, and how hard

Not every threat is a fight. Offer a way to talk, sneak, trick or run whenever the fiction allows it.

**Budget.** Add up the `xp_value` of the monsters (`lookup monster <name>`). Compare it with the party's budget: the sum, over every party member who can fight, of the value for their level.

| Level | Easy | Standard | Hard | Deadly |
|---|---|---|---|---|
| 1 | 25 | 50 | 75 | 100 |
| 2 | 50 | 100 | 150 | 200 |
| 3 | 75 | 150 | 225 | 400 |
| 4 | 125 | 250 | 375 | 500 |
| 5 | 250 | 500 | 750 | 1100 |

If the monsters outnumber the party, count their XP as one and a half times for this comparison. If they outnumber it two to one, count double. (The XP the party earns is never multiplied.)

A level 1 party is fragile: one hit can drop a character. Use Easy and Standard fights at level 1. Save Hard for a climax. Use Deadly only when the player walked into it after a clear warning.

**The warning** comes from the fiction and gives away no secret: what the hero can see, hear or smell, a companion who says plainly that this is a bad idea and why ("You can barely stand, and I count four of them"), the state the hero is in. Give it once, clearly. If the player goes ahead, run the fight honestly.

**Use `lookup monster --list --cr 0.25`** to find monsters of a rating. To invent one, copy the numbers of a monster of the same rating and change the skin: that is what `--custom` is for.

## Start

`encounter start C --monster goblin:3 --monster hobgoblin:1`

The script rolls initiative for every party member and one roll for each group of monsters, rolls each monster's hit points, and returns the order. `damage` and `encounter next` report monster hit points every time, so never carry them in your head. Add `--average-hp` to skip the hit-point rolls. Tell the player the order in one line. Never read out monster hit points: describe how hurt a monster looks. A monster's AC does appear in the open roll line (`vs AC 15`), and that is fine: the dice are open.

Surprise: if one side is unaware, give the other side a free round before you call `encounter start`, or simply skip the surprised creatures' first turns.

## A party member's turn

The hero acts as the player says. For a companion, the player may give a short order, and you decide the details.

**A weapon attack:**
1. `roll C --who mara-voss --attack rapier --ac 15` (use the target's `ac` from the encounter output). The script adds the bonus from the sheet and returns `damage_expr`.
2. On `hit`: `roll C "1d8+2" --reason "rapier damage on goblin-1"`, then `damage C --who goblin-1 --amount 7`.
3. On `critical_hit` (a natural 20): roll every damage die twice and add the modifier once. For `1d8+2`, roll `2d8+2`. For a Rogue's sneak attack of `1d6`, roll `2d6` more.
4. A natural 1 always misses.

Show it openly: `d20 (14) + 4 = 18 vs AC 15: hit. 1d8 (5) + 2 = 7 piercing.`

**Finish a turn before you advance it.** Roll the attack, roll the damage and run `damage` for the combatant whose turn it is, and only then run `encounter next`.

**Anything else** (shove, grapple, swing from a rope, throw sand): pick the ability or skill, set a DC or an opposed roll, and roll it. Say yes to creative plans. Give advantage for a good one.

**Class features** are on the sheet as rule text (`sheet <id> C`, under `feature_rules`). You apply them. Second Wind is a `roll` followed by `heal`. A feature with limited uses gets a counter when the character gains it (`track C --name "mara second wind" --set 1`), is spent with `--add -1`, and is set again after the rest its rule names.

**Sneak Attack without a map.** The script does not track positions, so use this ruling every time: the Rogue gets it, once per turn, when they attack with a finesse or ranged weapon AND either they have advantage, or a conscious ally is fighting the same enemy in melee. Hiding first, or a companion who was ordered to engage that enemy, is how the player earns it.

**0 hit points for a monster.** `"defeated": true` means out of the fight. Say "goes down" or "drops", and do not call it dead on your own: killing is the player's choice. Whether it is dead, dying or knocked out is settled by what the hero does next, or by a blow that leaves no doubt. A melee attacker may always choose to knock a foe out and not kill (5e), so ask the player when it could matter: prisoners talk.

Then `encounter next C`.

## A monster's turn

1. Decide what it does, from its `tactic`, its situation and its wits. Animals flee when hurt. Bandits surrender. Zealots do not. Not every monster fights to the death. When one runs or yields: `encounter flee C --who goblin-2`. It leaves the turn order and gives no XP.
2. Attack: `roll C "1d20+4" --ac 16 --reason "goblin-1 scimitar on mara-voss"`. Use the `attack_bonus` from the monster's record, and the target's `ac` from `status` or the sheet.
3. On a hit: `roll C "1d6+2" --reason "goblin-1 scimitar damage"`, then `damage C --who mara-voss --amount 5`. On a natural 20, double the dice, and add `--crit` to `damage` if the target is already at 0 HP.
4. An attack with `attack_bonus: null` uses a saving throw: the target rolls `roll C --who brann --save con --dc 11`.
5. A monster's own saving throw: `roll C "1d20+2" --dc 13 --reason "goblin-1 dex save"`. Use the modifier from its ability score: (score minus 10) divided by 2, rounded down.
6. `traits` on the record list multiattack, resistances, regeneration and similar. Apply them yourself: halve damage for a resistance before you call `damage`.

Spread attacks in a way that fits the fiction, not always on the hero and not always on the weakest.

**Who attacks a character who is down.** Decide it from the monster's nature, before you roll, and hold to it:

| The monster is | While someone still stands | When everyone is down |
|---|---|---|
| Mindless and made to kill (skeletons, zombies, animated armour, most undead), a hungry predator or eater (ghouls, wolves, oozes), or a sworn killer (an assassin, a zealot, a personal enemy) | It finishes a downed target only if no standing enemy is in reach | It keeps attacking the downed. Each hit is a failed death save (two on a critical, and a melee hit on an unconscious target is a critical). This is the road to the Grit save, and it is meant to be |
| Anything with a mind and a purpose (bandits, goblins, soldiers, cultists who want a captive, most humanoids) | It turns to the enemies still standing | It stops. It takes prisoners, robs the party, leaves them for dead, or drags them to its master |

Then `encounter next C`.

## Spells

1. `cast C --who brann --spell guiding-bolt` (add `--slot 2` to cast it with a higher slot). The script spends the slot, and returns the spell record, `save_dc` and `spell_attack_bonus`. If it refuses, the spell does not happen: tell the player why (no slot left, not prepared).
2. If the record says `attack_or_save` is `spell_attack`: `roll C --who brann --spell-attack --ac 13`.
3. If it says `save:dex`: each target rolls the save against `save_dc`. A monster: `roll C "1d20+2" --dc 13 --reason "goblin-2 dex save"`.
4. Roll `damage_expr` as a free roll. The caster's ability modifier is not in the string: add it only where the spell says so (for example Cure Wounds heals `1d8` plus the modifier: `roll C "1d8+3"`). `higher_levels` says what a higher slot adds. Then `damage` or `heal`.
5. One area spell, many targets: roll the damage once and apply it to each target, halved for a successful save where the spell says so.
6. **Concentration** (`"concentration": true`): a caster concentrates on one spell at a time. When a concentrating caster takes damage, they roll `--save con` with a DC of 10, or half the damage if that is higher. On a failure the spell ends.
7. Spells that the script cannot enforce (Sleep's pool of hit points, Shield's +5 AC for a round, Mage Armor's AC of 13 plus Dexterity): you apply the effect in the fiction and in your target numbers, and you say so openly.

## Special rules the script does not apply for you

- **Conditions.** `condition add` records them. You apply the effect: a prone target gives melee attackers advantage, a poisoned creature has disadvantage on attacks and checks, a restrained creature's attackers have advantage, and so on.
- **Cover.** Half cover is +2 to AC, three-quarters cover is +5. Add it to the `--ac` you pass.
- **Opportunity attacks.** A creature that leaves an enemy's reach without disengaging takes one melee attack. Warn the player before the hero provokes one.
- **Two weapons.** A second light weapon attacks as a bonus action, and its damage does not add the ability modifier: roll only the die.
- **Healing potions.** `item remove`, then `roll C "2d4+2"`, then `heal`.

## Dying, death saves and the Grit save

The script moves each character through these states. `damage` and `status` always tell you the current one.

| State | What it means | What you do |
|---|---|---|
| `alive` | Above 0 HP | |
| `dying` | 0 HP and unconscious | On that character's turn: `deathsave C --who id`. Any healing wakes them. Damage while dying is a failed save, or two with `--crit`. An ally can try a DC 10 Medicine check, and on a success: `stabilize` |
| `stable` | 0 HP, unconscious, no more saves | Healing or a rest wakes them |
| `fallen` | **Hero only.** By the 5e rules the hero is dead | Run the Grit save, at once |
| `dead` | True death | A companion: narrate it, and let it matter. The hero: see below |

**A companion has no Grit save.** Three failed death saves, or massive damage, and they are dead. Give the moment weight.

**The Grit save (`fallen` hero).** Stop the fight narration. This is the biggest moment of the session.
1. Set the DC. The base is **10**. Use 12 to 13 for massive damage, or 15 for a hostile place with no help near (deep water, a collapsing mine, alone among enemies). Say the DC aloud before the roll.
2. `grit C --dc 10`. It is one Constitution save, once per long rest. If it was already used, there is no roll and it fails. Show the roll.
3. Apply the `outcome`:

| Outcome | What happens |
|---|---|
| `light_cost` | The hero lives: stable at 0 HP. They lose something that stings but does not define them: a scar, a piece of gear, some gold, time |
| `heavy_cost` | The hero lives, and it changes the story. Choose the cost that fits best: captured, saved by someone at a price, a permanent loss, a companion dies in the hero's place, a debt to a dark power. Make it specific and lasting. True death happens only if the player asks for it, or made a reckless choice after a clear warning: then ask, and run `character retire ... --status dead --player-accepted` |
| `dead` | Iron difficulty only. The hero is dead. Give the death its scene |

4. Apply any part of the cost that is a number with the normal commands (`item remove`, `gold --spend`, `character retire` for a companion).
5. Write the cost into `journal.md`, and its long-term meaning into `dm-secrets.md`. A cost the story forgets was not a cost.

**If the hero is truly dead:** offer the player a choice. The campaign ends with an epilogue, or it goes on: a companion steps up (`character promote <id> C`), or a new hero arrives (`character create`, then `character promote`).

**Never soften a roll to avoid this.** The Grit save IS the safety net, and it only means something if the dice were true.

## When the whole party is down

Nobody is `alive`. Do not stop the dice and do not rescue anyone.

1. Keep going round by round: `encounter next`, a `deathsave` on each dying character's turn, and the monsters act by the table above.
2. It ends when every party member is `stable`, `dead`, or the hero is `fallen`. A `fallen` hero gets the Grit save at once.
3. Run `encounter end`. A party with nobody standing earns no XP: the script reports `"party_defeated": true`.
4. **A lost fight always costs something, even when everyone lives.** The enemy decides what happens to the bodies, by its nature: prisoners, robbed and left in a ditch, carried to a master, or simply left among the dead. Apply the numbers with the normal commands (`item remove`, `gold --spend`). Open the next scene where the enemy's choice put the hero. This is the one time the DM places the hero, because the hero was unconscious.
5. If the hero is dead, see "If the hero is truly dead" above.

**Waking up.** Any healing wakes a `stable` or `dying` character. With no healer, a `stable` character wakes on its own with 1 hit point after 1d4 hours: `roll C "1d4" --reason "hours until mara-voss wakes"`, then `heal C --who mara-voss --amount 1`. An unconscious character cannot spend hit dice, so a short rest helps only after they wake.

## Ending the fight

`encounter end C` adds up the XP of **defeated** monsters, splits it among the party members who are not dead or departed, applies it, and reports level-ups. It is refused while the hero is `fallen`.

- The party lost (nobody left standing): the script pays no XP on its own.
- If monsters survive and could return, note their remaining hit points in `dm-secrets.md` before you end the fight: `encounter.json` is deleted.
- The party fled, or the enemy surrendered or ran: monsters that were not defeated give no XP. If the party solved the fight by wit, give story XP of about the same size with `xp`.
- Use `--no-xp` when the fight was a story beat that should not pay out.
- A level-up rolls the hit die in the script. Tell the player the new HP and what is new. If the report shows `pending_asi`, ask the player and run `character asi`. If it shows spell or cantrip picks, offer choices and run `spells learn`.
- Loot: `gold --add` and `item add`. Invent loot that fits the monster. Most monsters carry little.

## Rests

- **Short rest** (about an hour, somewhere safe enough): each character may spend hit dice. Ask the player how many for the hero, and decide for companions. `rest short C --dice mara-voss:1,brann:1`. Some features recover on a short rest: their rule text says so.
- **Long rest** (8 hours): `rest long C`. Full HP, all spell slots, half the hit dice, and the Grit save is ready again. Casters may change their prepared spells: `spells prepare`. At most one long rest in 24 hours.
- A rest is a scene, not a button. Something can happen during one. The world moves while the party sleeps.

## Keeping a fight fast in text

- One turn of narration per combatant, two sentences. Group identical monsters that do the same thing. A whole round with its rolls shown may run to about 200 words, and no more.
- Run the monsters' turns and the companions' turns together, then stop at the hero's turn with the situation clear: who is hurt, who is where, what is about to happen.
- Describe, do not recite. "The goblin is bleeding and eyeing the door", not "goblin-1 has 2 HP".
- Most fights should be decided in three or four rounds. When the outcome is clear, end it: the last enemy runs, yields or falls. Then `encounter end`.
