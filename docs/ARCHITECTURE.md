# tabletop-dm Architecture

Source: the code-architect blueprint of 2026-09-18, built from `PRD.md`. `PRD.md` says WHAT. This file says HOW.
The task list and the PRD-row traceability table are in `docs/PLAN.md`.
Spoiler wall (PRD section 13): this file holds no story content, and the test seeds are fakes.

## Review amendments (2026-09-18)

These correct or extend the blueprint below. Where an amendment and the blueprint disagree, the amendment wins.

1. **Weapon properties.** Each weapon record in `data/equipment.json` also carries `"properties"`, a list from `finesse, ranged, thrown, versatile, two-handed, light, heavy, reach, ammunition`, and `"versatile_damage_expr"` when it applies. `derive_attacks` uses Dexterity for a `ranged` weapon, the higher of Strength and Dexterity for a `finesse` weapon, and Strength for all others. Without this a Rogue's rapier and every bow get the wrong bonus.
2. **Class features carry rule text.** Each entry in a level's `features` list is an object, `{"id": "sneak-attack", "name": "Sneak Attack", "rule": "Once per turn, +2d6 damage ..."}`, and not a bare string. The script does not resolve attacks (PRD non-goal), so the DM reads the rule from `lookup class rogue --level 3` and adds the dice to a free-form `roll`. The sheet stores the feature ids. `sheet` returns the rule text.
3. **`status` also reports spell slots and hit dice** for each character (`"slots":{"1":"2/4"}`, `"hit_dice":"2/3"`). PRD section 9 lists slots, and the blueprint example left them out.
4. **`tests/base.py` adds `skills/tabletop-dm/scripts/` to `sys.path` once**, so that tests `import dmlib`. No test runs the script as a subprocess, except one smoke test in `TestCliDispatch` that runs `dm.py --version` by absolute path from a different working directory. That test proves the import mechanism of Part 1.
5. **Banned-names list** corrected to the real SRD 5.1 product-identity list (see Part 4).
6. **`atomic_write_json`** writes to a temp file in the SAME campaign folder and then uses `os.replace`. The temp name starts with a dot, so the write guard's "hidden dot-files do not count" rule ignores a stray one after a crash.

## Build amendments (2026-09-18, after M1 to M4, M7 and three playtests)

The blueprint below is the design as planned. The code is the truth where they differ. The differences:

1. **Modules added:** `party_ops.py` (shared helpers: slugs, `require_character`, `commit`), and `cmd_seed.py` gained `seed list`. `validate_data` became a light check inside `data.load_all`, and the deep checks live in `tests/test_data_real.py`, which also builds a character of every class at every level through the real command.
2. **Commands added:** `character set`, `character asi`, `spells learn`, `stabilize`, `track`, `encounter flee`, `roll --proficient`. See the table in `PRD.md` section 9.
3. **Sheet fields added:** `skill_proficiencies`, `expertise`, `fighting_style`, `features` (ids), `pending_asi`, `pending_spell_picks`, `pending_cantrip_picks`, `passive_perception`. `spellcasting` also holds `spellbook`, `prepare_limit`, `cantrips_known_limit`, `max_spell_level`. `party.json` gained an optional top-level `trackers` object.
4. **Class data fields added:** `default_skills`, `default_background_skills`, `quick_scores`, `armor_proficiencies`, `weapon_proficiencies`, `starting_equipped`, `starting_gold_cp` (a fixed amount, not `starting_gold_expr`), `fighting_styles`, `expertise`, and per level `cantrips_known`. HP gain is computed from the hit die, so `hp_gain_fixed` and `hp_gain_expr` are not stored.
5. **Monsters use group initiative:** one roll per `--monster` entry. Every `initiative_order` entry also carries `dex` (the tie-break) and `natural` (the die, so it can be shown).
6. **Dice:** an expression may end in `*N` (for example `5d4*10`). A lone `1d20` roll reports `natural` and honours advantage. Against an AC, a natural 20 is `critical_hit` and a natural 1 is `miss`.
7. **Life states:** `apply_death_save` and `apply_grit` return `(character, result)`. `apply_rest_hp_change` is named `apply_hp_gain_from_rest`. Temporary hit points absorb damage first.
8. **Tests use `ScriptedRng`**, a `random.Random` whose `randint` returns a fixed queue of dice, so a test states the exact dice it wants. Every dice call in `dmlib` goes through `rng.randint`.
9. **Mutation checks must run Python with `-B`** and clear `__pycache__`: a file restored within the same second and at the same size reuses the mutated bytecode.

## PART 1 — Structure Decision

**DECISION: (b) — `scripts/dm.py` as a thin entry point plus `scripts/dmlib/` as a package.** Reasoning: the ~25-command surface needs unit-testable seams smaller than "the whole CLI"; a single file would force every test through argparse and full-process I/O. Zip file size and line count cost nothing (only stdout enters the model's context — constraint 8), so there's no token-budget argument for a monolith. The upload audience is non-technical and never opens the code, so "readability as one file for a human browsing it" isn't a real constraint either. A package gives pure, disk-free unit tests for dice math, derived-number math, and life-state transitions, which is where most of the row-by-row test coverage in section 16 lives.

### Import mechanism

Python already inserts the invoked script's own directory at `sys.path[0]` when you run `python3 /abs/path/dm.py`, regardless of the caller's cwd — so `import dmlib` resolves correctly from any host, any cwd, purely from the fact that `dmlib/` is a sibling of `dm.py`. `dm.py` also does one defensive, explicit insert before the import, as insurance against a host that invokes the script in a nonstandard way (e.g. `runpy`):

```python
#!/usr/bin/env python3
import random
import sys
from pathlib import Path

def main(argv=None):
    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))          # defensive; usually already true
    from dmlib.cli import run
    skill_root = scripts_dir.parent                # skills/tabletop-dm/
    return run(sys.argv[1:] if argv is None else argv, skill_root, random.SystemRandom())

if __name__ == "__main__":
    sys.exit(main())
```

`skill_root` is `scripts/`'s parent (`skills/tabletop-dm/`), matching the repo layout where `data/` is a sibling of `scripts/`. **DECISION: `skill_root` = the folder containing both `data/` and `scripts/`, not `scripts/` itself** — this is the one path every data-loading and seed-loading function needs, so it's the parameter every internal function carries per constraint testability rule, not `Path(__file__)` directly.

### Module list

All modules are Python-3.9-safe: `Optional[X]`, `List[X]`, `Dict[str, Any]`, `Tuple[...]` from `typing`; no `match`, no `X | Y`. Every function that touches dice takes `rng: random.Random` explicitly (never imports `random` and calls it directly); every function that touches files takes `skill_root: Path` and/or `campaign_dir: Path` explicitly (never reads `Path(__file__)` itself — only `dm.py`'s `main()` does that, once).

**Pure modules — no filesystem I/O, tested with plain dicts:**

- **`dmlib/errors.py`** — the one error shape.
  - `class DmError(Exception): def __init__(self, code: str, message: str) -> None`
  - `def error_envelope(command: str, err: DmError) -> Dict[str, Any]`
  - `def success_envelope(command: str, **fields: Any) -> Dict[str, Any]`

- **`dmlib/rules_tables.py`** — small constant tables, centralized so no magic numbers live in command modules.
  - `ABILITIES: Tuple[str, ...]` (`str,dex,con,int,wis,cha`)
  - `SKILLS: Dict[str, str]` (skill slug → governing ability, all 18 5e skills)
  - `STANDARD_ARRAY: Tuple[int, ...]` (`15,14,13,12,10,8`)
  - `CR_TO_XP: Dict[str, int]` (SRD challenge-rating → XP table; generic 5e math, not product identity)
  - `XP_THRESHOLDS: Dict[int, int]` (level 1–5 → cumulative XP to reach it)
  - `LEGAL_CONDITIONS: Tuple[str, ...]` (the 14 SRD conditions)

- **`dmlib/dice.py`** — the roller. `rng` is always passed in, never instantiated here.
  - `def roll_expression(expr: str, rng: random.Random) -> Dict[str, Any]`
  - `def roll_d20(rng: random.Random, advantage: bool = False, disadvantage: bool = False) -> Dict[str, Any]`
  - `def roll_hit_die(die: str, rng: random.Random) -> int`

- **`dmlib/derive.py`** — recomputes every stored-derived number on a character sheet (PRD 8: "recomputes them whenever an input changes").
  - `def ability_modifier(score: int) -> int`
  - `def proficiency_bonus(level: int) -> int`
  - `def derive_saves(character: Dict[str, Any]) -> Dict[str, Any]`
  - `def derive_skills(character: Dict[str, Any]) -> Dict[str, Any]`
  - `def derive_ac(character: Dict[str, Any], equipment_data: Dict[str, Any]) -> int`
  - `def derive_attacks(character: Dict[str, Any], equipment_data: Dict[str, Any]) -> Dict[str, Any]`
  - `def derive_spellcasting(character: Dict[str, Any], class_data: Dict[str, Any]) -> Optional[Dict[str, Any]]`
  - `def recompute_all(character: Dict[str, Any], classes_data: Dict[str, Any], equipment_data: Dict[str, Any]) -> Dict[str, Any]` (the one function every mutator calls before writing)

- **`dmlib/life_states.py`** — the section 11 machine, pure transforms on a character dict copy.
  - `def apply_damage(character: Dict[str, Any], amount: int, is_crit: bool, is_hero: bool) -> Dict[str, Any]`
  - `def apply_heal(character: Dict[str, Any], amount: int) -> Dict[str, Any]`
  - `def apply_death_save(character: Dict[str, Any], d20_roll: int, is_hero: bool) -> Dict[str, Any]`
  - `def apply_grit(character: Dict[str, Any], save_total: int, dc: int, difficulty: str, already_used: bool) -> Dict[str, Any]`
  - `def apply_rest_hp_change(character: Dict[str, Any], hp_gained: int) -> str` (returns new life_state)

**Filesystem/orchestration modules:**

- **`dmlib/io_campaign.py`**
  - `def check_write_guard(campaign_dir: Path) -> None`
  - `def is_owned_campaign_dir(campaign_dir: Path) -> bool`
  - `def atomic_write_json(path: Path, data: Dict[str, Any]) -> None`
  - `def load_party(campaign_dir: Path) -> Dict[str, Any]`
  - `def save_party(campaign_dir: Path, party: Dict[str, Any]) -> None`
  - `def load_encounter(campaign_dir: Path) -> Optional[Dict[str, Any]]`
  - `def save_encounter(campaign_dir: Path, encounter: Dict[str, Any]) -> None`
  - `def delete_encounter(campaign_dir: Path) -> None`
  - `def append_log(campaign_dir: Path, entries: List[Dict[str, Any]]) -> None`
  - `def migrate_party_if_needed(party: Dict[str, Any]) -> Dict[str, Any]`
  - `def ensure_markdown_templates(campaign_dir: Path) -> List[str]` (repairs a missing journal/world/dm-secrets file, returns repair notes)

- **`dmlib/data.py`**
  - `def load_all(skill_root: Path) -> Dict[str, Dict[str, Any]]` (`classes`, `spells`, `monsters`, `equipment`)
  - `def validate_data(data: Dict[str, Dict[str, Any]]) -> List[str]`
  - `def lookup_record(kind: str, name: str, skill_root: Path, level: Optional[int] = None) -> Dict[str, Any]`
  - `def list_names(kind: str, skill_root: Path) -> List[str]`
  - `def list_seed_names(skill_root: Path) -> List[str]`

- **`dmlib/cmd_setup.py`** — `version`, `init`, `settings_set`, `status`, `sheet`
- **`dmlib/cmd_roll.py`** — `roll` (named + free forms)
- **`dmlib/cmd_lookup.py`** — `lookup`
- **`dmlib/cmd_character.py`** — `character_create`, `character_retire`, `character_promote`, `equip`, `unequip`, `spells_prepare`, `xp`
- **`dmlib/cmd_play.py`** — `damage`, `heal`, `cast`, `rest_short`, `rest_long`, `item_add`, `item_remove`, `gold`, `condition_add`, `condition_remove`, `deathsave`, `grit`
- **`dmlib/cmd_encounter.py`** — `encounter_start`, `encounter_add`, `encounter_next`, `encounter_end`
- **`dmlib/cmd_seed.py`** — `seed_choose`, `seed_pick`

  Every function in these seven modules has the shape:
  `def <name>(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]` — returns the success dict or raises `DmError`. None of them print or call `sys.exit`.

- **`dmlib/cli.py`**
  - `def build_parser() -> argparse.ArgumentParser`
  - `def dispatch(argv: List[str], skill_root: Path, rng: random.Random) -> Dict[str, Any]` (raises `DmError`; used directly by most tests)
  - `def run(argv: List[str], skill_root: Path, rng: random.Random) -> int` (calls `dispatch`, prints exactly one compact JSON line via `json.dumps(..., separators=(",", ":"))`, returns exit code — this is what `dm.py.main()` calls)

- **`dmlib/__init__.py`** — `__version__ = "0.1.0"`.

---

## PART 2 — JSON Schemas

### `party.json`

```json
{
  "format": "tabletop-dm/party",
  "format_version": 1,
  "hero_id": "kira",
  "settings": {
    "difficulty": "standard",
    "content_level": "pg13",
    "tone_answers": { "pace": "balanced", "danger": "standard" },
    "seed": null
  },
  "characters": {
    "kira": {
      "id": "kira",
      "name": "Kira Ashwood",
      "class": "fighter",
      "level": 3,
      "xp": 900,
      "background": "",
      "bond": "",
      "flaw": "",
      "abilities": { "str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8 },
      "ability_modifiers": { "str": 3, "dex": 2, "con": 2, "int": 0, "wis": 1, "cha": -1 },
      "proficiency_bonus": 2,
      "saves": {
        "str": { "proficient": true, "bonus": 5 },
        "dex": { "proficient": false, "bonus": 2 },
        "con": { "proficient": true, "bonus": 4 },
        "int": { "proficient": false, "bonus": 0 },
        "wis": { "proficient": false, "bonus": 1 },
        "cha": { "proficient": false, "bonus": -1 }
      },
      "skills": {
        "athletics": { "proficient": true, "expertise": false, "bonus": 5 },
        "stealth": { "proficient": false, "expertise": false, "bonus": 2 }
      },
      "ac": 16,
      "hp": { "current": 24, "max": 28, "temp": 0 },
      "hit_dice": { "die": "d10", "max": 3, "remaining": 2 },
      "life_state": "alive",
      "death_saves": { "successes": 0, "failures": 0 },
      "grit_used_since_long_rest": false,
      "conditions": [],
      "spellcasting": null,
      "attacks": {
        "longsword": { "attack_bonus": 5, "damage_expr": "1d8+3", "damage_type": "slashing", "proficient": true }
      },
      "equipped": { "armor": "chain-shirt", "shield": null, "weapons": ["longsword"] },
      "inventory": [
        { "item": "longsword", "quantity": 1 },
        { "item": "chain-shirt", "quantity": 1 },
        { "item": "torch", "quantity": 3 }
      ],
      "gold_cp": 1500
    }
  }
}
```

| Field | Type | Required | Legal values | Computed by |
|---|---|---|---|---|
| `format` | string | yes | `"tabletop-dm/party"` | `init` |
| `format_version` | int | yes | ≥1 | `init`, bumped by migrations |
| `hero_id` | string | yes | key into `characters` whose entry is not `dead`/`departed` at creation | `character create` (first char), `character promote` |
| `settings.difficulty` | string | yes | `story`, `standard`, `iron` | `settings set` |
| `settings.content_level` | string | yes | `pg13`, `pg13-dark` | `settings set` |
| `settings.tone_answers` | object of string→string | yes | any keys/values (DECISION below) | `settings set` |
| `settings.seed` | string or null | yes | a seed name, or null before setup step 3 | `seed choose`/`seed pick` |
| `characters.<id>.*` | see rows below | | | |
| `abilities.*` | int | yes | 1–20 (3–18 at creation) | `character create` |
| `ability_modifiers.*` | int | yes | derived | `derive.py`, on every write |
| `proficiency_bonus` | int | yes | 2–3 (levels 1–5) | `derive.py` |
| `saves.*.bonus`, `skills.*.bonus` | int | yes | derived | `derive.py` |
| `ac` | int | yes | derived from `equipped` | `derive.py` |
| `hp.current/max` | int | yes | `current` 0..max | `character create`, `damage`, `heal`, `xp` (level-up), `rest` |
| `hit_dice.remaining` | int | yes | 0..max | `rest short/long` |
| `life_state` | string | yes | `alive,dying,stable,fallen,dead,departed` | `damage`, `heal`, `deathsave`, `grit`, `rest`, `character retire/promote` |
| `death_saves.*` | int | yes | 0–3 | `deathsave` |
| `grit_used_since_long_rest` | bool | yes | | `grit`, reset by `rest long` |
| `conditions` | list of string | yes | subset of `LEGAL_CONDITIONS` | `condition add/remove` |
| `spellcasting` | object or null | yes (present, may be null) | null for Fighter/Rogue | `derive.py` |
| `attacks` | object keyed by equipment id | yes | only currently-equipped weapons | `derive.py`, on `equip`/`unequip` |
| `equipped.*` | id or null / list | yes | must exist in `inventory` | `equip`/`unequip` |
| `inventory` | list of `{item, quantity}` | yes | `quantity` ≥ 0 (0-qty lines pruned) | `item add/remove`, `character create` |
| `gold_cp` | int | yes | ≥0 | `gold`, `character create` |

**DECISION — gold storage: a single gp figure, stored internally as an integer of copper pieces (`gold_cp`).** Full multi-denomination coinage (cp/sp/ep/gp/pp tracked separately) is bookkeeping weight this hobby game doesn't need, matching the PRD's other complexity cuts (no feats, no multiclass). Storing the *single number* in integer cp rather than a float gp avoids rounding drift across many small item costs (torches cost 1 cp). `gold --add/--spend` take a gp amount (may have up to 2 decimals) and the script converts to cp; `sheet`/`status` report back in gp.

**DECISION — `settings.tone_answers` is validated loosely (must be an object of string→string), not against a hardcoded enum in `dm.py`.** The legal tone question keys/values are DM-facing narrative tuning defined in `reference/dm-style.md` and `reference/session-flow.md`, not a game-legality rule — this keeps tone questions a content/data change, never a code change, matching the PRD's stated philosophy for classes/spells/monsters.

**DECISION — format-version migration rule.** On every load, `io_campaign.migrate_party_if_needed` compares `format_version` to `dmlib.CURRENT_FORMAT_VERSION`:
- equal → proceed unchanged.
- lower → run the chain of pure `migrate_vN_to_vN+1(party: dict) -> dict` functions in order, write the result back atomically with the bumped `format_version`, then proceed. Migrations only ever *add* fields with safe defaults; they never delete or reinterpret numbers.
- higher → refuse with `format_version_too_new` ("this campaign was made by a newer version of the skill; update the skill before continuing"), no write.
- `format` field absent or wrong value entirely → refuse with `not_a_campaign` (this is also the check every non-`init` command uses to detect "no campaign here yet").

### `encounter.json`

```json
{
  "format": "tabletop-dm/encounter",
  "format_version": 1,
  "round": 1,
  "turn_index": 0,
  "initiative_order": [
    { "id": "kira", "kind": "party", "initiative": 17 },
    { "id": "goblin-1", "kind": "monster", "initiative": 12 },
    { "id": "thorn", "kind": "party", "initiative": 9 },
    { "id": "goblin-2", "kind": "monster", "initiative": 4 }
  ],
  "monsters": {
    "goblin-1": {
      "id": "goblin-1",
      "name": "Goblin",
      "source": "goblin",
      "custom": false,
      "hp": { "current": 4, "max": 7 },
      "ac": 15,
      "xp_value": 50,
      "defeated": false
    },
    "goblin-2": { "id": "goblin-2", "name": "Goblin", "source": "goblin", "custom": false, "hp": { "current": 7, "max": 7 }, "ac": 15, "xp_value": 50, "defeated": false }
  }
}
```

| Field | Type | Required | Legal values | Computed by |
|---|---|---|---|---|
| `round` | int | yes | ≥1 | `encounter start` (=1), `encounter next` |
| `turn_index` | int | yes | valid index into `initiative_order` | `encounter next` |
| `initiative_order` | list | yes | one entry per party member + monster in the fight | `encounter start`/`add` |
| `initiative_order[].kind` | string | yes | `party`, `monster` | |
| `monsters.<id>.id` | string | yes | slug like `goblin-1` (source name + 1-based counter, counter never resets within one encounter) | `encounter start`/`add` |
| `monsters.<id>.custom` | bool | yes | true only for `--custom` monsters | |
| `monsters.<id>.hp` | object | yes | `current` 0..max | `encounter start`, `damage`/`heal` |
| `monsters.<id>.defeated` | bool | yes | true when `hp.current == 0` | `damage` |
| `monsters.<id>.xp_value` | int | yes | ≥0 | `CR_TO_XP` lookup, or `--custom`'s `xp_value` |

**DECISION — party members never get an HP entry in `encounter.json`.** `party.json` stays the sole source of truth for party HP even mid-fight (matches section 8's table: encounter.json holds "initiative order, monster HP" only). `damage`/`heal --who <id>` resolves `<id>` against `party.json` first, then against `encounter.json`'s `monsters` if not a known character.

### `log.jsonl` — one line per event, append-only

Roll line:
```json
{"seq":142,"ts":"2026-09-18T14:32:01Z","command":"roll","type":"roll","payload":{"who":"kira","kind":"attack","expr":"1d20+5","rolls":[14],"modifier":5,"total":19,"advantage":false,"disadvantage":false,"target":{"ac":15},"result":"hit","reason":"longsword vs goblin-1"}}
```

State-change line:
```json
{"seq":143,"ts":"2026-09-18T14:32:02Z","command":"damage","type":"state_change","payload":{"target":"goblin-1","field":"hp.current","before":7,"after":3,"life_state_before":null,"life_state_after":null,"details":{"amount":4,"crit":false}}}
```

**DECISION — `seq` is the 1-based line number in `log.jsonl`, computed by counting existing lines before append, not a counter stored in `party.json`.** One less piece of state to keep in sync; campaign logs for a hobby game stay small enough that an O(n) count per write is free.

**DECISION — a command that both rolls dice and changes state (deathsave, grit, rest's hit-die spends, encounter start's initiative rolls) appends one `"roll"` line per die roll, then one `"state_change"` line summarizing the resulting mutation — all in the same disk-write batch as the state file write.** Keeps the two `type`s pure and lets an auditor reconstruct exactly which rolls produced which number, per firm rule 3 ("dice are always open").

### `--custom` monster input (to `encounter start`/`encounter add`)

```json
{
  "name": "Swamp Brute",
  "count": 1,
  "ac": 14,
  "hp": 27,
  "abilities": { "str": 17, "dex": 10, "con": 15, "int": 6, "wis": 10, "cha": 6 },
  "attacks": [ { "name": "slam", "attack_bonus": 5, "damage_expr": "2d6+3", "damage_type": "bludgeoning" } ],
  "tactic": "Grapples the nearest foe.",
  "challenge_rating": 2
}
```
`challenge_rating` OR `xp_value` is required (one or the other). If only `challenge_rating` is given, `xp_value` is looked up from `rules_tables.CR_TO_XP`.

### `data/classes.json`

```json
{
  "format": "tabletop-dm/classes",
  "format_version": 1,
  "classes": {
    "fighter": {
      "id": "fighter", "name": "Fighter", "hit_die": "d10", "primary_ability": "str",
      "saving_throw_proficiencies": ["str", "con"],
      "skill_choices": { "count": 2, "options": ["acrobatics", "athletics", "history", "insight", "intimidation", "perception", "survival"] },
      "starting_gold_expr": "5d4*10",
      "starting_equipment": ["chain-mail", "shield", "longsword"],
      "spellcasting": null,
      "levels": {
        "1": { "proficiency_bonus": 2, "hp_gain_fixed": 6, "hp_gain_expr": "1d10", "features": ["fighting-style", "second-wind"], "slots": null },
        "5": { "proficiency_bonus": 3, "hp_gain_fixed": 6, "hp_gain_expr": "1d10", "features": ["extra-attack"], "slots": null }
      }
    }
  }
}
```
Wizard/Cleric additionally carry `spellcasting: {"ability": "int"|"wis", "type": "known"|"prepared_from_class_list", "cantrips_known_by_level": {...}}` and each level's `slots: {"1": 2}` etc. **DECISION — `levels` stores BOTH `hp_gain_fixed` (the 5e average, half-die-rounded-up) and `hp_gain_expr`: `hp_gain_fixed` is used for levels granted at companion creation (deterministic, no rng consumed for paperwork), `hp_gain_expr` is used for XP-earned level-ups during play (rolled, matching real 5e feel).**

### `data/spells.json`

```json
{
  "format": "tabletop-dm/spells",
  "format_version": 1,
  "spells": {
    "magic-missile": { "id": "magic-missile", "name": "Magic Missile", "level": 1, "classes": ["wizard"], "attack_or_save": null, "damage_expr": "1d4+1", "damage_type": "force", "description": "Three darts of magical force strike unerringly." },
    "fire-bolt": { "id": "fire-bolt", "name": "Fire Bolt", "level": 0, "classes": ["wizard"], "attack_or_save": "spell_attack", "damage_expr": "1d10", "damage_type": "fire", "description": "A mote of fire streaks to a target." }
  }
}
```

### `data/monsters.json`

```json
{
  "format": "tabletop-dm/monsters",
  "format_version": 1,
  "monsters": {
    "goblin": { "id": "goblin", "name": "Goblin", "challenge_rating": 0.25, "xp_value": 50, "ac": 15, "hp_expr": "2d6", "abilities": { "str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8 }, "attacks": [ { "name": "scimitar", "attack_bonus": 4, "damage_expr": "1d6+2", "damage_type": "slashing" } ], "tactic": "Attacks from range or in numbers; flees below a quarter HP." }
  }
}
```

### `data/equipment.json`

```json
{
  "format": "tabletop-dm/equipment",
  "format_version": 1,
  "equipment": {
    "longsword": { "id": "longsword", "name": "Longsword", "category": "weapon", "cost_cp": 1500, "damage_expr": "1d8", "damage_type": "slashing", "weapon_class": "martial-melee" },
    "chain-shirt": { "id": "chain-shirt", "name": "Chain Shirt", "category": "armor", "cost_cp": 5000, "armor_class_base": 13, "dex_bonus_max": 2, "armor_type": "medium" },
    "torch": { "id": "torch", "name": "Torch", "category": "gear", "cost_cp": 1 }
  }
}
```
**DECISION — equipment cost stored as `cost_cp` (integer), matching the `gold_cp` decision above, so a purchase never needs float math.**

---

## PART 3 — Command Contracts

Consistent shapes used throughout:
- Success: `{"ok": true, "command": "<name>", ...fields}`
- Error: `{"ok": false, "command": "<name>", "error": {"code": "<code>", "message": "<specific, actionable text>"}}`, exit code **1** for every refusal (PRD asks only for "non-zero exit," so one uniform code keeps the contract simple — **DECISION**).
- "Refuses" always means: no write to `party.json`/`encounter.json`, nothing appended to `log.jsonl`, exit 1. Validation always runs to completion before the single write.

### 1. `--version`
`python3 dm.py --version`
Success: `{"ok":true,"command":"version","dm_version":"0.1.0","python_version":"3.11.4","format_version":1,"data":{"classes":4,"spells":42,"monsters":41,"equipment":38}}`
Refuses: `data_invalid` — "data/monsters.json: entry 'goblin' missing 'attacks'" (lists every problem `validate_data` finds).
Log: read-only, no `--campaign`, nothing to append.

### 2. `init`
`python3 dm.py init --campaign <dir>`
Success: `{"ok":true,"command":"init","campaign":"<dir>","files_created":["party.json","log.jsonl","journal.md","world.md","dm-secrets.md"]}`
Refuses: `write_guard_failed` — "the folder is not empty" (unrelated non-dotfile present) or "this folder already has a campaign — point at it directly, or use a new empty folder" (a `party.json` already exists, parseable or not).
Log: creates `log.jsonl` itself; first line is a `state_change` for `init` (`before: null, after: "campaign created"`).

### 3. `settings set`
`python3 dm.py settings set --campaign <dir> [--difficulty story|standard|iron] [--content-level pg13|pg13-dark] [--tone <key>=<value> ...]`
Success: `{"ok":true,"command":"settings_set","settings":{...updated block...}}`
Refuses: `unknown_key` — "settings has no field 'god-mode'"; `illegal_value` — "difficulty must be one of story, standard, iron".
Log: `state_change`, one line per changed field.

### 4. `status`
`python3 dm.py status --campaign <dir>`
Success: `{"ok":true,"command":"status","characters":{"kira":{"hp":"24/28","life_state":"alive","conditions":[],"gold_gp":15.0,"level":3,"xp":900}},"settings":{...},"encounter_active":false,"journal_bytes":842,"repairs":[]}`
Refuses: `not_a_campaign` — "<dir> has no party.json — run init first".
Log: read-only (a missing markdown template it silently repairs still counts as read-only for `party.json`/`log.jsonl` purposes; the repair itself is reported in `"repairs"`, not logged to `log.jsonl`, since it touches only prose templates).

### 5. `sheet <id>`
`python3 dm.py sheet <id> --campaign <dir>`
Success: full character object as in Part 2's `party.json` schema, wrapped `{"ok":true,"command":"sheet","character":{...}}`.
Refuses: `unknown_id` — "no character 'grog'. Known: kira, thorn."
Log: read-only.

### 6. `roll`
Named forms:
```
dm.py roll --campaign <dir> --who <id> --attack <weapon> [--adv|--disadv] [--ac N] [--reason STR]
dm.py roll --campaign <dir> --who <id> --check <skill-or-ability> [--adv|--disadv] [--dc N] [--reason STR]
dm.py roll --campaign <dir> --who <id> --save <ability> [--adv|--disadv] [--dc N] [--reason STR]
dm.py roll --campaign <dir> --who <id> --initiative [--adv|--disadv]
```
Free form: `dm.py roll --campaign <dir> "<expr>" [--adv|--disadv] [--dc N] [--ac N] [--reason STR]`
Success: `{"ok":true,"command":"roll","expr":"1d20+5","rolls":[14],"modifier":5,"total":19,"advantage":false,"target":{"ac":15},"result":"hit"}`
Refuses: `bad_expression` — "'2d' is not a legal dice expression"; `unknown_id`; `unknown_weapon` — "longbow is not on kira's sheet (not equipped)"; `advantage_invalid_for_expression` — "advantage/disadvantage only applies to a single d20 roll."
Log: exactly one `"roll"` line, always (this is the one command whose only disk effect IS the log — **DECISION**: `roll` never touches `party.json`).

### 7. `lookup <kind> <name>`
`dm.py lookup <class|spell|monster|equipment> <name> [--level N]` (works WITHOUT `--campaign`) or `dm.py lookup <kind> --list`
Success: `{"ok":true,"command":"lookup","kind":"monster","record":{...~100 tokens...}}` or `{"ok":true,"command":"lookup","kind":"spell","names":["fire-bolt","magic-missile",...]}`
Refuses: `unknown_name` — "no spell 'magik missile'. Did you mean: magic-missile?" (via `difflib.get_close_matches`).
Log: read-only, no `--campaign` needed.

### 8. `character create`
`dm.py character create --campaign <dir> --id <slug> --name <str> --class <fighter|rogue|wizard|cleric> --scores <s,s,s,s,s,s in str,dex,con,int,wis,cha order> [--level N] [--background STR] [--bond STR] [--flaw STR] [--spells <id,id,...>] [--quick]`
**DECISION — no separate "roll ability scores" subcommand.** The DM obtains the six numbers either from the fixed standard array (a constant it already knows) or by calling the existing free-form `roll 4d6kh3` six times and choosing an assignment, then passes the six numbers to `--scores`. Reuses the existing `roll` command instead of adding a parallel mechanism.
Success: `{"ok":true,"command":"character_create","character":{...full sheet...}}`
Refuses: `illegal_ability_scores` — "6 scores required, in str,dex,con,int,wis,cha order"; `unknown_class`; `illegal_spell_pick` — "magic-missile is not on the wizard level-1 list."
Log: `state_change` (`characters.<id>` created).

### 9. `equip` / `unequip`
`dm.py equip --campaign <dir> --who <id> --slot armor|shield|weapon --item <equipment-id>`
`dm.py unequip --campaign <dir> --who <id> --slot armor|shield|weapon [--item <equipment-id>]`
Success: `{"ok":true,"command":"equip","who":"kira","ac":16,"attacks":{...},"warnings":["not proficient with chain-shirt"]}` (warnings present only when relevant — not proficient is reported, never refused).
Refuses: `item_not_in_inventory` — "chain-shirt is not in kira's inventory."
Log: `state_change` on `equipped`, `ac`, `attacks`.

### 10. `spells prepare`
`dm.py spells prepare --campaign <dir> --who <id> --spells <id,id,...>`
Success: `{"ok":true,"command":"spells_prepare","who":"thorn","prepared":["magic-missile","shield"]}`
Refuses: `too_many_spells_prepared` — "level 3 wizard can prepare 5, tried 6"; `spell_not_available` — "sacred-flame is not a wizard spell."
Log: `state_change`.

### 11. `damage` / `heal`
`dm.py damage --campaign <dir> --who <id> --amount N [--crit]`
`dm.py heal --campaign <dir> --who <id> --amount N`
**Monster target:** reduces `encounter.json`'s `monsters.<id>.hp.current` (floor 0), sets `defeated: true` at 0; monsters carry no life-state machinery. **Party/companion target:** runs `life_states.apply_damage`/`apply_heal`.
Success (party): `{"ok":true,"command":"damage","who":"kira","hp":"0/28","life_state":"dying","death_saves":{"successes":0,"failures":1},"note":"massive damage"}` (note present only when the massive-damage branch fired).
Success (monster): `{"ok":true,"command":"damage","who":"goblin-1","hp":"0/7","defeated":true}`
Refuses: `unknown_id`; `heal` on `fallen`/`dead`/`departed` → `not_eligible_for_heal`.
Log: `state_change` on `hp.current` (+ `life_state` if changed), plus a second `state_change` for `death_saves` if `damage` added a forced failure.

### 12. `cast`
`dm.py cast --campaign <dir> --who <id> --spell <id> [--slot N]`
Success: `{"ok":true,"command":"cast","who":"thorn","spell":"magic-missile","slot_used":1,"slots":{"1":{"max":4,"used":2}}}`
Refuses: `no_slot_available`; `spell_not_prepared`; `slot_too_low` — "shield is a 1st-level spell, can't be cast at slot 0."
Log: `state_change` on `spellcasting.slots.<n>.used` (cantrips still log a `state_change` with `before==after`, per PRD: "a cantrip spends nothing but is still logged").

### 13. `rest short` / `rest long`
`dm.py rest short --campaign <dir> --dice <id>:<n>[,<id>:<n>...]`
`dm.py rest long --campaign <dir>`
Success (short): `{"ok":true,"command":"rest_short","results":{"kira":{"dice_spent":1,"hp_gained":7,"hp":"31/28→28/28"}}}`
Success (long): `{"ok":true,"command":"rest_long","results":{"kira":{"hp":"28/28","hit_dice_restored":1,"slots_reset":true},"thorn":{"hp":"18/18","hit_dice_restored":1,"grit_reset":true}}}`
Refuses (both): `encounter_active` — "end the fight before resting." Refuses (short only): `insufficient_hit_dice` — "kira has 2 hit dice remaining, tried to spend 3."
Log: one `"roll"` line per hit die spent (short rest only — long rest's HP restoration isn't a roll, it's a flat full heal), then one `state_change` summarizing HP/slot/hit-dice/grit changes per character. Spending `--dice id:0` (or a character with 0 remaining) restores 0 HP and is logged as a `state_change` with `before==after` — the documented "rest that restores no HP" case.

### 14. `item add` / `item remove`
`dm.py item add --campaign <dir> --who <id> --item <equipment-id> [--qty N]` OR `--name "<free text>" [--value-gp N]` (DM-invented loot; **DECISION** — extends the PRD's "data is a base, not a cage" principle from monsters to items, for the same reason: the DM must be able to hand the party a found item that isn't in `equipment.json` without dm.py blocking the scene).
`dm.py item remove --campaign <dir> --who <id> --item <equipment-id-or-name> [--qty N]`
Success: `{"ok":true,"command":"item_add","who":"kira","inventory":[...]}`
Refuses: `item_not_in_inventory` (remove only) — "torch not in kira's pack."
Log: `state_change` on `inventory`.

### 15. `gold`
`dm.py gold --campaign <dir> --who <id> --add <gp>` OR `--spend <gp>` (mutually exclusive)
Success: `{"ok":true,"command":"gold","who":"kira","gold_gp":15.0}`
Refuses: `insufficient_gold` — "kira has 15 gp, tried to spend 20."
Log: `state_change` on `gold_cp`.

### 16. `xp`
`dm.py xp --campaign <dir> --who <id> --amount N`
Success: `{"ok":true,"command":"xp","who":"kira","xp":1150,"level_up":{"from":3,"to":4,"hp_max":"28→34","features_gained":["ability-score-improvement"]}}`
Refuses: `level_cap_reached` — "kira is already level 5; this build supports no higher level" (**DECISION**: once level 5, `xp` refuses outright rather than silently tracking XP with no mechanical effect — see the "level above 5" resolution below).
Log: `state_change` on `xp` (+ `level`, `hp.max`, `proficiency_bonus`, `spellcasting.slots` if a level-up occurred).

### 17. `condition add` / `condition remove`
`dm.py condition add --campaign <dir> --who <id> --condition <name>`
`dm.py condition remove --campaign <dir> --who <id> --condition <name>`
Success: `{"ok":true,"command":"condition_add","who":"kira","conditions":["poisoned"]}`
Refuses: `unknown_condition` — "'stunned-ish' is not a 5e condition. Legal: blinded, charmed, ... ."
Log: `state_change` on `conditions`.

### 18. `encounter start`
`dm.py encounter start --campaign <dir> [--monster <name>:<count> ...] [--custom <json> ...]`
Success: `{"ok":true,"command":"encounter_start","round":1,"initiative_order":[...],"monsters":{"goblin-1":{...},"goblin-2":{...}}}`
Refuses: `encounter_active` — "a fight is already active; run encounter end first."
Log: one `"roll"` line per initiative roll (party AND monsters), then one `state_change` line (`encounter.json created`).

### 19. `encounter add`
`dm.py encounter add --campaign <dir> [--monster <name>:<count> ...] [--custom <json> ...]`
Success: `{"ok":true,"command":"encounter_add","added":["goblin-3"],"initiative_order":[...]}`
Refuses: `no_active_encounter`.
Log: one `"roll"` line per new initiative roll, one `state_change` for the merge.

### 20. `encounter next`
`dm.py encounter next --campaign <dir>`
Success: `{"ok":true,"command":"encounter_next","round":2,"turn":{"id":"kira","kind":"party"}}`
Refuses: `no_active_encounter`.
Log: `state_change` on `round`/`turn_index`.
**DECISION — auto-skips any combatant who can't act** (party member in `dying/stable/fallen/dead/departed`, or a defeated monster), incrementing `round` on wraparound; if none can act, still returns the next slot with `"note":"no combatants can currently act"` rather than refusing.

### 21. `encounter end`
`dm.py encounter end --campaign <dir> [--no-xp]`
Success: `{"ok":true,"command":"encounter_end","xp_awarded":150,"xp_per_member":75,"level_ups":{}}`
Refuses: `no_active_encounter`; `hero_not_resolved` — "kira is fallen; run grit first."
Log: `state_change` for `encounter.json` deletion, plus one `state_change` per XP-recipient character (or none if `--no-xp`).

### 22. `deathsave`
`dm.py deathsave --campaign <dir> --who <id>`
Success: `{"ok":true,"command":"deathsave","who":"thorn","roll":14,"result":"success","successes":2,"failures":0,"life_state":"dying"}`
Refuses: `not_dying` — "thorn is alive, not dying."
Log: `"roll"` line (the d20), then `state_change` on `death_saves`/`life_state`.

### 23. `grit`
`dm.py grit --campaign <dir> --dc <N>` (no `--who` — **DECISION**: grit only ever targets `hero_id`, there is exactly one hero at a time, so requiring the id would be redundant ceremony).
Success: `{"ok":true,"command":"grit","who":"kira","roll":16,"outcome":"light_cost","life_state":"stable","hp":0}` or, when already used: `{"ok":true,"command":"grit","who":"kira","roll":null,"outcome":"heavy_cost","note":"grit already used since last long rest — no roll, automatic failure","life_state":"stable","hp":0}`
Refuses: `not_hero` — "grit only applies to the hero"; `not_fallen` — "kira is alive, not fallen."
Log: `"roll"` line ONLY when a roll actually happens (already-used case appends only a `state_change`, since no die was rolled — matches "the script makes no roll"), then `state_change` on `life_state`/`hp`/`grit_used_since_long_rest`.

### 24. `seed choose <name>` / `seed pick`
`dm.py seed choose --campaign <dir> <name>`
`dm.py seed pick --campaign <dir>`
Success: `{"ok":true,"command":"seed_choose","seed":"fixture-seed-a"}`
Refuses: `seed_unknown`; `no_seeds_found`; `seed_already_set` — "this campaign already chose fixture-seed-a."
Log: `seed pick` appends a `"roll"` line (the random-index roll) then `state_change`; `seed choose` appends only `state_change` (no die rolled — a player pick isn't a random event).

### 25. `character retire`
`dm.py character retire --campaign <dir> --who <id> --status dead|departed [--player-accepted]`
Success: `{"ok":true,"command":"character_retire","who":"thorn","life_state":"dead"}`
Refuses: `unknown_id`; `hero_death_needs_confirmation` — "retiring the hero as dead needs --player-accepted, in every difficulty."
Log: `state_change`.

### 26. `character promote <id>`
`dm.py character promote --campaign <dir> <id>`
Success: `{"ok":true,"command":"character_promote","hero_id":"thorn"}`
Refuses: `promotion_not_allowed` — "kira is alive; nothing to promote into"; `unknown_id`.
Log: `state_change` on `hero_id` (old hero's `life_state` is untouched — it stays `dead`/`departed` "for the record," per PRD).

---

### Life-state transition table (function-level contract)

Both `party.json` life states AND grit outcomes derive from **one** massive-damage formula, applied identically whether the target was `alive` or already at 0 HP:

**DECISION — massive damage formula** (resolves the one genuine implementation gap in section 11, using the standard SRD instant-death rule): `overkill = amount - current_hp_before_floor` (only meaningful once `amount >= current_hp`); if `overkill >= max_hp`, death is instant and bypasses `dying` entirely. This single formula covers *both* "an alive character dropped past 0 in one hit" and "an already-0-HP `dying`/`stable` character takes more damage" — the SRD's "damage at 0 hit points" rule and its "massive damage" rule are the same equation with `current_hp` already at 0 for the second case, so no separate special-casing is needed.

| Trigger | Actor | Sub-case | Before | After | Command |
|---|---|---|---|---|---|
| `damage` drops HP to 0, no overkill | hero or companion | | `alive` | `dying`, 0 successes/failures | `damage` |
| `damage` drops HP to 0, overkill ≥ max HP | hero | massive damage | `alive` | `fallen` | `damage` |
| same | companion | massive damage | `alive` | `dead` | `damage` |
| `damage` on an already-`dying` character | either | non-crit | `dying` | `dying`, +1 failure | `damage` |
| same | either | `--crit` | `dying` | `dying`, +2 failures | `damage` |
| `damage` on an already-`dying` character | either | overkill ≥ max HP | `dying` | hero→`fallen`, companion→`dead` | `damage` |
| `damage` on a `stable` character | either | normal | `stable` | `dying`, 0/0 | `damage` |
| `damage` on a `stable` character | either | overkill ≥ max HP | `stable` | hero→`fallen`, companion→`dead` | `damage` |
| `heal` (any amount > 0) | either | | `dying` or `stable` | `alive` | `heal` |
| `deathsave` roll ≥10 | either | 3rd success | `dying` | `stable` | `deathsave` |
| `deathsave` roll <10 | either | natural 1 | `dying` | +2 failures; at 3 → hero `fallen`, companion `dead` | `deathsave` |
| `deathsave` roll = 20 | either | natural 20 | `dying` | `alive`, HP=1 | `deathsave` |
| `rest short`, ≥1 HP gained | either | | `stable` | `alive` | `rest short` |
| `rest short`, 0 HP gained (0 dice spent) | either | | `stable` | `stable` (unchanged) | `rest short` |
| `rest long` | either | always restores to max HP | `stable` | `alive` | `rest long` |
| `grit`, success | hero only | any difficulty | `fallen` | `stable`, HP 0 | `grit` |
| `grit`, failure, story | hero only | | `fallen` | `stable`, HP 0 (light_cost) | `grit` |
| `grit`, failure, standard | hero only | | `fallen` | `stable`, HP 0 (heavy_cost) | `grit` |
| `grit`, failure, iron | hero only | | `fallen` | `dead` | `grit` |
| `grit`, already used this long rest | hero only | any difficulty | `fallen` | same as that difficulty's failure row, no roll | `grit` |
| `character retire --status dead --player-accepted` | hero | | any | `dead` | `character retire` |
| `character retire --status dead` | hero, no flag | | any | refused | `character retire` |
| `character retire` | companion | | any | `dead` or `departed` | `character retire` |
| `character promote <id>` | companion | hero is `dead`/`departed` | companion's own state unchanged | becomes `hero_id` | `character promote` |

**Contradiction check across the two section-11 tables (life states vs. Grit difficulty):** no direct disagreement found — the Grit table's `dead` outcome exists only on `iron` failure, exactly matching the life-states table's `dead`-entry condition ("a grit outcome of dead"); `story`'s "hero cannot truly die" matches the life-states table never routing `story` to `dead` via grit. The one genuine gap (not a contradiction, an underspecification) was massive damage against an already-0-HP character, resolved above.

---

## PART 4 — Test Layout

```
tests/
  __init__.py
  base.py                    DmTestCase base class + helpers
  fixtures/
    skill_root/
      data/classes.json      2 classes (fighter, wizard), levels 1-3 only
      data/spells.json       3 spells
      data/monsters.json     3 monsters ("fixture-goblin", "fixture-wolf", "fixture-brute")
      data/equipment.json    5 items
      seeds/fixture-seed-a.md   "FIXTURE SEED A. Placeholder text for tests. Not real content."
      seeds/fixture-seed-b.md   "FIXTURE SEED B. Placeholder text for tests. Not real content."
      seeds/teasers.md          one placeholder line per fixture seed
  test_errors.py
  test_rules_tables.py
  test_dice.py
  test_derive.py
  test_life_states.py
  test_io_campaign.py
  test_data.py                  (fixture data completeness/shape, NOT the real data)
  test_data_real.py             (the REAL skills/tabletop-dm/data/*.json — integrity + product-identity ban)
  test_cmd_setup.py
  test_cmd_roll.py
  test_cmd_lookup.py
  test_cmd_character.py
  test_cmd_play.py
  test_cmd_encounter.py
  test_cmd_seed.py
  test_cli.py
```

**Fixture skill root design:** `tests/fixtures/skill_root/` is a tiny, checked-in, read-only stand-in for `skills/tabletop-dm/`. It never needs `scripts/` (tests `import dmlib` directly since `tests/` and `skills/tabletop-dm/scripts/` are both reachable once the test runner adds `skills/tabletop-dm/scripts/` to `sys.path` — done once in `tests/base.py`, not per test). Fixture data is deliberately minimal (2-3 records per file) so a test asserting "derive.py computed X correctly" has an obviously-traceable input.

**Seeded RNG injection:** every test that needs dice gets `random.Random(<fixed-seed>)`, never `random.SystemRandom()`. `tests/base.py`:

```python
class DmTestCase(unittest.TestCase):
    SKILL_ROOT = Path(__file__).resolve().parent / "fixtures" / "skill_root"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.campaign_dir = Path(self._tmp.name)
        self.rng = random.Random(20260918)

    def run_cli(self, argv: List[str]) -> Tuple[int, Dict[str, Any]]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = dmlib.cli.run(argv, self.SKILL_ROOT, self.rng)
        return exit_code, json.loads(buf.getvalue())

    def init_campaign(self, **overrides) -> None:
        self.run_cli(["init", "--campaign", str(self.campaign_dir)])
        ...
```

Each test gets a fresh temp campaign directory per test method (never shared, never reused across tests) via `tempfile.TemporaryDirectory()` in `setUp`, auto-removed by `addCleanup`.

**The one command that runs the whole suite, from the repo root:**

```
python3 -m unittest discover -s tests -p "test_*.py" -t . -v
```

Exit code 0 = every test passed (standard `unittest` behavior); any failure or error → non-zero exit. This is the "hard gate before every commit" PRD layer 1 names, and CI/pre-commit can rely on the bare exit code with no output parsing.

### Test-group-per-row mapping (class names)

| Command-table row | `TestCase` class |
|---|---|
| `--version` | `TestVersionCommand` |
| `init` (+ write guard) | `TestInitCommand`, `TestWriteGuard` |
| `settings set` | `TestSettingsSet` |
| `status` | `TestStatusCommand` |
| `sheet` | `TestSheetCommand` |
| `roll` (named + free) | `TestRollNamedCommand`, `TestRollFreeCommand` |
| `lookup` | `TestLookupCommand` |
| `character create` | `TestCharacterCreate` |
| `equip`/`unequip` | `TestEquipUnequip` |
| `spells prepare` | `TestSpellsPrepare` |
| `damage`/`heal` | `TestDamageHealCommand` |
| `cast` | `TestCastCommand` |
| `rest short`/`rest long` | `TestRestShortCommand`, `TestRestLongCommand` |
| `item add`/`item remove` | `TestItemCommands` |
| `gold` | `TestGoldCommand` |
| `xp` | `TestXpAndLevelUp` |
| `condition add`/`remove` | `TestConditionCommands` |
| `encounter start` | `TestEncounterStart` |
| `encounter add` | `TestEncounterAdd` |
| `encounter next` | `TestEncounterNext` |
| `encounter end` | `TestEncounterEnd` |
| `deathsave` | `TestDeathsaveCommand` |
| `grit` | `TestGritCommand` |
| `seed choose`/`seed pick` | `TestSeedCommands` |
| `character retire` | `TestCharacterRetire` |
| `character promote` | `TestCharacterPromote` |

### Test-group-per-life-state-row mapping

| Life-state row | `TestCase` class |
|---|---|
| Damage/heal transitions, massive-damage formula | `TestLifeStatesDamage`, `TestLifeStatesHeal` |
| Death saves (nat1, nat20, 3-success, 3-failure) | `TestLifeStatesDeathSave` |
| Grit per difficulty, already-used | `TestLifeStatesGrit` |
| Rest HP-gain vs no-gain | covered inside `TestRestShortCommand`/`TestRestLongCommand` |
| Retire/promote hero-only invariants | `TestCharacterRetire`, `TestCharacterPromote` |

### Data-integrity tests (`test_data_real.py`, against the real `skills/tabletop-dm/data/`)

- `TestClassesDataCompleteness` — all 4 classes present, levels 1–5 fully populated, every level row has `proficiency_bonus`/`hp_gain_fixed`/`hp_gain_expr`/`features`.
- `TestSpellsDataLegality` — every spell's `level` ∈ 0–3, `classes` ⊆ {wizard, cleric}, referenced by no class-list entry that doesn't exist.
- `TestMonstersDataCompleteness` — every monster has `ac`, `hp_expr`, `abilities` (6 keys), `attacks` (≥1), `challenge_rating` ∈ 0–5.
- `TestEquipmentDataLegality` — every item has `category` ∈ {weapon, armor, gear}, `cost_cp` ≥ 0.
- `TestNoProductIdentityNames` — case-insensitive substring scan of every string value across all four real data files against a banned-terms list (the SRD 5.1 product-identity list plus setting names: `beholder, gauth, carrion crawler, displacer beast, githyanki, githzerai, kuo-toa, mind flayer, illithid, slaad, umber hulk, yuan-ti, tanar'ri, baatezu, forgotten realms, faerun, greyhawk, eberron, ravenloft, dragonlance, dungeons & dragons`). Owlbear, drow and tarrasque ARE in SRD 5.1 and are allowed; fails loudly with the offending file+field if any hit.

---

## Remaining contradictions or gaps resolved

1. **§11, massive damage against an already-0-HP character (gap, not a contradiction).** The life-states table's `dying`/`fallen`/`dead` entries both invoke "massive damage" but never state the formula, and it's unclear whether it applies only to a hit from full health or also to a second hit on an unconscious character. Resolved in Part 3 by applying the single SRD instant-death formula (`overkill = amount - current_hp; overkill >= max_hp → instant death`) uniformly to both cases — it's the same rule with `current_hp` already at 0 in the second case, so one formula, no special-casing needed.

2. **§11 life-states table vs. §11 Grit-difficulty table: no direct disagreement found.** Checked explicitly: the `dead` life-state's entry condition ("a grit outcome of dead") only ever fires on `iron`-difficulty failure, matching the Grit table exactly; `story`'s "hero cannot truly die" is consistent with the life-states table never routing `story` to `dead` via `grit`. Flagged per the brief's instruction, resolved as "no fix needed."

3. **§9, `xp` refusal "Level above 5" (gap).** The PRD doesn't say whether XP still accumulates silently past the level-5 cap or the command refuses outright. Resolved as: once a character is level 5, `xp` refuses any further add (`level_cap_reached`) rather than tracking XP with no mechanical effect, since `classes.json` has no level-6 data to compute against.

4. **§9, `damage`/`heal` amount input (gap).** The PRD never states whether `damage`/`heal` take a dice expression or a fixed number. Resolved as a fixed `--amount N` integer: the model already rolls the damage/heal dice via the separate `roll` command (open, logged) and passes the resulting total, keeping "the model never invents a roll" intact while `damage`/`heal` stay pure HP arithmetic.

5. **§9, `character create` ability-score generation (gap).** No subcommand is specified for "script-rolled 4d6-drop-lowest." Resolved by reusing the existing free-form `roll 4d6kh3` (already in the `roll` row) six times, with the six totals fed into `character create --scores`, rather than adding a parallel roll mechanism.

6. **§8, gold representation (explicitly flagged as open in the task brief).** Resolved as a single gp figure for all player/DM-facing purposes, backed internally by an integer `gold_cp` field to avoid float rounding on sub-gp item costs — not full cp/sp/ep/gp/pp denomination tracking.

7. **§19 item 6, format-version migration mechanics (gap).** The PRD says `party.json` "carries a format version so `dm.py` can migrate or refuse clearly" but doesn't specify the rule. Resolved with a linear `migrate_vN_to_vN+1` chain for older campaigns, an explicit `format_version_too_new` refusal for campaigns from a newer skill, and `not_a_campaign` for a missing/wrong `format` marker.
