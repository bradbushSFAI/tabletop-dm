# tabletop-dm

A text-only, fifth-edition-compatible tabletop game that runs as a Claude skill. The session model is the Dungeon Master. `skills/tabletop-dm/scripts/dm.py` owns every number. Spec: `PRD.md`. Design: `docs/ARCHITECTURE.md`. Decision history: `GRILL.md`.

## THE SPOILER WALL (read this first)

Brad plays this game. He must not be spoiled.

- **Never quote, summarise, or hint at the contents of `skills/tabletop-dm/world/metaplot.md` or any `skills/tabletop-dm/seeds/<name>.md` file to Brad**, unless he asks to open them. `world/bible.md` and `seeds/teasers.md` are player-safe.
- The wall covers derived material too: the `dm-secrets.md` of any test campaign, playtest transcripts, auditor reports, and diffs of the secret files. Reports to Brad give verdicts and rule violations with no plot content.
- Commit messages for the secret files are generic ("add seed 3"). Do not show Brad a diff of a secret file.
- Playtest campaigns and transcripts go in the gitignored `playtests/` folder, or in the session scratchpad.

## Hard constraints on the script (tests enforce the first three)

- Python standard library only. Python 3.9 syntax (no `match`, no `X | Y` types). No network imports.
- The script never writes inside the skill folder. All state goes to the `--campaign` folder.
- Every internal function takes `skill_root` and `rng` as parameters. Only `dm.py`'s `main()` reads `__file__` and makes `random.SystemRandom()`. Every dice call goes through `rng.randint`.
- A refusal raises `DmError(code, message)` BEFORE any write: no change on disk, nothing in the log, exit 1.
- Every state change is written at once and appended to `log.jsonl`. The model never edits JSON.

## Conventions

- TDD. Write the failing test first. `tests/base.py` has `DmTestCase` (`self.ok(...)`, `self.refused(code, ...)`, `self.snapshot()`) and `ScriptedRng([dice...])` for exact dice.
- Tests run against a tiny fixture skill root in `tests/fixtures/skill_root/`. `tests/test_data_real.py` checks the real data.
- A new command needs: a handler in `dmlib/cmd_*.py`, an entry in `cli.HANDLERS` and `build_parser`, tests, and a row in `SKILL.md` (a test fails if `SKILL.md` misses a command).
- `SKILL.md` stays under 500 lines. Reference files are one level deep and do not link to each other. No em-dashes in skill prose.
- Adding a class, spell, monster or item is a data change in `skills/tabletop-dm/data/`, with no code change. SRD 5.1 content only, and no Wizards product identity (the ban list is in `tests/test_data_real.py`).
- Mutation checks must run Python with `-B` and clear `__pycache__`, or a restored file reuses the mutated bytecode.

## Verification

- Whole suite, from the repo root: `python3 -B -m unittest discover -s tests -p "test_*.py" -t .` (exit 0 is green). Join it to a commit with `&&`.
- Build the release zips: `python3 build.py` (writes `dist/`).
- There is no dev server, no port, and no browser surface. No browser tools are needed or authorized here.
- DM behaviour is checked by a playtest: a DM sub-agent follows only a copy of the skill folder and keeps a transcript, and an auditor sub-agent checks the transcript and `log.jsonl` against the firm rules. See `PRD.md` section 16.
- Cowork (local and cloud) can only be verified by Brad. Report those results as unverified until he runs them.
