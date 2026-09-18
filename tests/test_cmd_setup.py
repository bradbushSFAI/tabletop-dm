import json

from tests.base import DmTestCase, ScriptedRng


class TestVersionCommand(DmTestCase):
    def test_version_needs_no_campaign_and_counts_the_data(self):
        code, out = self.run_cli(["--version"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["command"], "version")
        self.assertEqual(out["data"], {"classes": 3, "spells": 8, "monsters": 3, "equipment": 8})
        self.assertEqual(out["seeds"], 2)
        self.assertIn("python_version", out)

    def test_version_refuses_when_a_data_file_is_missing(self):
        import shutil
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            shutil.copytree(str(self.SKILL_ROOT), str(root))
            (root / "data" / "monsters.json").unlink()
            from dmlib import cli
            import contextlib
            import io

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli.run(["--version"], root, self.rng)
            out = json.loads(buf.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(out["error"]["code"], "data_invalid")
        self.assertIn("monsters.json", out["error"]["message"])


class TestInitCommand(DmTestCase):
    def test_init_creates_exactly_the_five_starting_files(self):
        out = self.ok("init")
        names = sorted(p.name for p in self.campaign_dir.iterdir())
        self.assertEqual(names, ["dm-secrets.md", "journal.md", "log.jsonl", "party.json", "world.md"])
        self.assertEqual(sorted(out["files_created"]), names)

    def test_init_does_not_create_encounter_json(self):
        self.ok("init")
        self.assertFalse((self.campaign_dir / "encounter.json").exists())

    def test_party_json_carries_the_format_marker_and_default_settings(self):
        self.ok("init")
        party = self.party()
        self.assertEqual(party["format"], "tabletop-dm/party")
        self.assertIsNone(party["hero_id"])
        self.assertEqual(party["settings"]["difficulty"], "standard")
        self.assertEqual(party["settings"]["content_level"], "pg13")
        self.assertIsNone(party["settings"]["seed"])
        self.assertEqual(party["characters"], {})

    def test_markdown_templates_have_headings_only(self):
        self.ok("init")
        for name in ["journal.md", "world.md", "dm-secrets.md"]:
            text = (self.campaign_dir / name).read_text()
            body = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#") and not ln.startswith("<!--")]
            self.assertEqual(body, [], name)

    def test_init_is_refused_in_a_folder_of_real_documents(self):
        (self.campaign_dir / "resume.docx").write_text("real")
        before = self.snapshot()
        self.refused("write_guard_failed", "init")
        self.assertEqual(before, self.snapshot())

    def test_init_is_refused_when_a_campaign_already_exists(self):
        self.ok("init")
        before = self.snapshot()
        out = self.refused("write_guard_failed", "init")
        self.assertIn("already", out["error"]["message"])
        self.assertEqual(before, self.snapshot())

    def test_init_logs_its_first_line(self):
        self.ok("init")
        self.assertEqual(self.log_lines()[0]["command"], "init")

    def test_commands_refuse_before_init(self):
        self.refused("not_a_campaign", "status")


class TestSettingsSet(DmTestCase):
    def setUp(self):
        super().setUp()
        self.init_campaign()

    def test_sets_difficulty_content_and_tone(self):
        self.ok("settings", "set", "--difficulty", "iron", "--content-level", "pg13-dark", "--tone", "genre=horror", "--tone", "pace=slow")
        settings = self.party()["settings"]
        self.assertEqual(settings["difficulty"], "iron")
        self.assertEqual(settings["content_level"], "pg13-dark")
        self.assertEqual(settings["tone_answers"], {"genre": "horror", "pace": "slow"})

    def test_illegal_difficulty_is_refused_with_no_change(self):
        before = self.snapshot()
        self.refused("illegal_value", "settings", "set", "--difficulty", "nightmare")
        self.assertEqual(before, self.snapshot())

    def test_tone_without_equals_sign_is_refused(self):
        self.refused("illegal_value", "settings", "set", "--tone", "horror")

    def test_nothing_to_set_is_refused(self):
        self.refused("nothing_to_set", "settings", "set")

    def test_seed_cannot_be_set_through_settings(self):
        code, out = self.camp("settings", "set", "--seed", "fixture-seed-a")
        self.assertEqual(code, 1)
        self.assertEqual(out["error"]["code"], "bad_arguments")

    def test_each_changed_field_is_logged(self):
        self.ok("settings", "set", "--difficulty", "story")
        last = self.log_lines()[-1]
        self.assertEqual(last["type"], "state_change")
        self.assertEqual(last["payload"]["field"], "settings.difficulty")
        self.assertEqual((last["payload"]["before"], last["payload"]["after"]), ("standard", "story"))


class TestStatusCommand(DmTestCase):
    def test_status_of_an_empty_party(self):
        self.init_campaign()
        out = self.ok("status")
        self.assertEqual(out["characters"], {})
        self.assertFalse(out["encounter_active"])
        self.assertIsNone(out["hero_id"])
        self.assertGreater(out["journal_bytes"], 0)
        self.assertEqual(out["repairs"], [])

    def test_status_is_read_only(self):
        self.init_campaign()
        before = self.snapshot()
        self.ok("status")
        self.assertEqual(before, self.snapshot())

    def test_status_repairs_a_deleted_markdown_file_and_says_so(self):
        self.init_campaign()
        (self.campaign_dir / "world.md").unlink()
        out = self.ok("status")
        self.assertEqual(out["repairs"], ["world.md was missing and was recreated as an empty template"])
        self.assertTrue((self.campaign_dir / "world.md").exists())


class TestRollFreeCommand(DmTestCase):
    def setUp(self):
        super().setUp()
        self.init_campaign()

    def test_free_roll_shows_every_die_and_the_total(self):
        out = self.ok("roll", "2d6+3", "--reason", "fire damage", rng=ScriptedRng([4, 6]))
        self.assertEqual(out["dice"][0]["rolls"], [4, 6])
        self.assertEqual(out["total"], 13)

    def test_free_roll_against_a_dc_reports_success_or_failure(self):
        self.assertEqual(self.ok("roll", "1d20+2", "--dc", "15", rng=ScriptedRng([13]))["result"], "success")
        self.assertEqual(self.ok("roll", "1d20+2", "--dc", "15", rng=ScriptedRng([12]))["result"], "failure")

    def test_free_roll_against_an_ac_reports_hit_or_miss(self):
        self.assertEqual(self.ok("roll", "1d20+5", "--ac", "15", rng=ScriptedRng([10]))["result"], "hit")
        self.assertEqual(self.ok("roll", "1d20+5", "--ac", "15", rng=ScriptedRng([9]))["result"], "miss")

    def test_advantage_on_a_single_d20_expression_rolls_twice(self):
        out = self.ok("roll", "1d20+1", "--adv", rng=ScriptedRng([3, 17]))
        self.assertEqual(out["total"], 18)
        self.assertEqual(out["d20"]["rolls"], [3, 17])

    def test_advantage_on_a_damage_expression_is_refused(self):
        self.refused("advantage_invalid_for_expression", "roll", "2d6", "--adv")

    def test_every_roll_is_appended_to_the_log(self):
        self.ok("roll", "1d8", "--reason", "sword", rng=ScriptedRng([5]))
        last = self.log_lines()[-1]
        self.assertEqual(last["type"], "roll")
        self.assertEqual(last["payload"]["total"], 5)
        self.assertEqual(last["payload"]["reason"], "sword")

    def test_roll_never_touches_party_json(self):
        before = self.snapshot()["party.json"]
        self.ok("roll", "1d8")
        self.assertEqual(before, self.snapshot()["party.json"])

    def test_bad_expression_is_refused_and_not_logged(self):
        before = self.snapshot()
        self.refused("bad_expression", "roll", "2d")
        self.assertEqual(before, self.snapshot())

    def test_roll_requires_a_campaign(self):
        code, out = self.run_cli(["roll", "1d6"])
        self.assertEqual(code, 1)
        self.assertEqual(out["error"]["code"], "bad_arguments")
