import json

from tests.base import DmTestCase

from dmlib import CURRENT_FORMAT_VERSION, io_campaign
from dmlib.errors import DmError


class TestWriteGuard(DmTestCase):
    def test_empty_folder_is_allowed(self):
        io_campaign.check_write_guard(self.campaign_dir)

    def test_folder_with_only_hidden_dot_files_counts_as_empty(self):
        (self.campaign_dir / ".DS_Store").write_text("x")
        io_campaign.check_write_guard(self.campaign_dir)

    def test_folder_with_an_unrelated_file_is_refused(self):
        (self.campaign_dir / "taxes-2026.pdf").write_text("real document")
        with self.assertRaises(DmError) as ctx:
            io_campaign.check_write_guard(self.campaign_dir)
        self.assertEqual(ctx.exception.code, "write_guard_failed")
        self.assertIn("new empty subfolder", ctx.exception.message)

    def test_folder_with_an_unrelated_subfolder_is_refused(self):
        (self.campaign_dir / "Photos").mkdir()
        with self.assertRaises(DmError):
            io_campaign.check_write_guard(self.campaign_dir)

    def test_missing_folder_is_refused_and_not_created(self):
        missing = self.campaign_dir / "nope"
        with self.assertRaises(DmError) as ctx:
            io_campaign.check_write_guard(missing)
        self.assertEqual(ctx.exception.code, "write_guard_failed")
        self.assertFalse(missing.exists())

    def test_foreign_party_json_is_not_an_owned_campaign(self):
        (self.campaign_dir / "party.json").write_text(json.dumps({"guests": ["ann"]}))
        self.assertFalse(io_campaign.is_owned_campaign_dir(self.campaign_dir))
        with self.assertRaises(DmError) as ctx:
            io_campaign.load_party(self.campaign_dir)
        self.assertEqual(ctx.exception.code, "not_a_campaign")

    def test_corrupt_party_json_is_reported_not_a_traceback(self):
        (self.campaign_dir / "party.json").write_text("{not json")
        with self.assertRaises(DmError) as ctx:
            io_campaign.load_party(self.campaign_dir)
        self.assertEqual(ctx.exception.code, "campaign_file_damaged")


class TestIoCampaign(DmTestCase):
    def test_atomic_write_leaves_no_temp_file_behind(self):
        io_campaign.atomic_write_json(self.campaign_dir / "x.json", {"a": 1})
        self.assertEqual([p.name for p in self.campaign_dir.iterdir()], ["x.json"])
        self.assertEqual(json.loads((self.campaign_dir / "x.json").read_text()), {"a": 1})

    def test_append_log_numbers_lines_from_one_and_continues(self):
        io_campaign.append_log(self.campaign_dir, [{"command": "a", "type": "roll", "payload": {}}])
        io_campaign.append_log(
            self.campaign_dir,
            [{"command": "b", "type": "roll", "payload": {}}, {"command": "c", "type": "state_change", "payload": {}}],
        )
        lines = self.log_lines()
        self.assertEqual([line["seq"] for line in lines], [1, 2, 3])
        self.assertTrue(all("ts" in line for line in lines))

    def test_encounter_is_none_when_no_fight_is_active(self):
        self.assertIsNone(io_campaign.load_encounter(self.campaign_dir))


class TestFormatVersionMigration(DmTestCase):
    def test_current_version_loads_unchanged(self):
        self.init_campaign()
        self.assertEqual(io_campaign.load_party(self.campaign_dir)["format_version"], CURRENT_FORMAT_VERSION)

    def test_newer_campaign_is_refused_and_not_rewritten(self):
        self.init_campaign()
        party = self.party()
        party["format_version"] = CURRENT_FORMAT_VERSION + 1
        (self.campaign_dir / "party.json").write_text(json.dumps(party))
        before = self.snapshot()
        self.refused("format_version_too_new", "status")
        self.assertEqual(before, self.snapshot())

    def test_older_campaign_runs_the_migration_chain(self):
        party = {"format": io_campaign.PARTY_FORMAT, "format_version": 0}
        calls = []

        def fake_v0_to_v1(old):
            calls.append(0)
            new = dict(old)
            new["added_by_migration"] = True
            return new

        out = io_campaign.migrate_party(party, migrations={0: fake_v0_to_v1}, target=1)
        self.assertEqual(calls, [0])
        self.assertEqual(out["format_version"], 1)
        self.assertTrue(out["added_by_migration"])
