"""Regressions for the Codex adversarial review of 2026-09-18."""
import json
import os
import threading

from tests.base import ScriptedRng
from tests.test_cmd_play import PlayCase
from tests.base import DmTestCase

from dmlib import io_campaign
from dmlib.errors import DmError


class TestTempFileAndSymlinks(DmTestCase):
    def test_init_does_not_write_through_a_hidden_temp_symlink(self):
        victim = self.campaign_dir.parent / "victim.txt"
        victim.write_text("precious")
        os.symlink(str(victim), str(self.campaign_dir / ".party.json.tmp"))
        self.camp("init")
        self.assertEqual(victim.read_text(), "precious")
        self.assertFalse((self.campaign_dir / "party.json").is_symlink())

    def test_atomic_write_never_reuses_a_fixed_temp_name(self):
        planted = self.campaign_dir / ".x.json.tmp"
        planted.write_text("do not touch")
        io_campaign.atomic_write_json(self.campaign_dir / "x.json", {"a": 1})
        self.assertEqual(planted.read_text(), "do not touch")

    def test_a_symlinked_campaign_file_is_refused(self):
        self.init_campaign()
        victim = self.campaign_dir.parent / "victim.jsonl"
        victim.write_text("")
        (self.campaign_dir / "log.jsonl").unlink()
        os.symlink(str(victim), str(self.campaign_dir / "log.jsonl"))
        self.refused("campaign_file_is_symlink", "roll", "1d6")
        self.assertEqual(victim.read_text(), "")

    def test_status_does_not_repair_through_a_dangling_symlink(self):
        self.init_campaign()
        outside = self.campaign_dir.parent / "outside.md"
        (self.campaign_dir / "world.md").unlink()
        os.symlink(str(outside), str(self.campaign_dir / "world.md"))
        self.refused("campaign_file_is_symlink", "status")
        self.assertFalse(outside.exists())

    def test_status_refusal_repairs_nothing(self):
        self.init_campaign()
        (self.campaign_dir / "journal.md").unlink()
        (self.campaign_dir / "encounter.json").write_text("{broken")
        before = self.snapshot()
        self.refused("campaign_file_damaged", "status")
        self.assertEqual(before, self.snapshot())


class TestCampaignLock(DmTestCase):
    def test_a_held_lock_makes_a_second_command_wait_then_refuse(self):
        self.init_campaign()
        with io_campaign.campaign_lock(self.campaign_dir):
            with self.assertRaises(DmError) as ctx:
                with io_campaign.campaign_lock(self.campaign_dir, wait_seconds=0.2):
                    pass
        self.assertEqual(ctx.exception.code, "campaign_busy")

    def test_the_lock_is_released_after_a_command_and_after_a_refusal(self):
        self.init_campaign()
        self.ok("roll", "1d6")
        self.refused("bad_expression", "roll", "2d")
        self.ok("roll", "1d6")
        self.assertFalse((self.campaign_dir / io_campaign.LOCK_FILE).exists())

    def test_a_stale_lock_is_broken(self):
        self.init_campaign()
        lock = self.campaign_dir / io_campaign.LOCK_FILE
        lock.write_text("dead process")
        old = lock.stat().st_mtime - io_campaign.STALE_LOCK_SECONDS - 5
        os.utime(str(lock), (old, old))
        self.ok("roll", "1d6")

    def test_parallel_processes_lose_no_update(self):
        """Real processes, because a model can send tool calls in parallel."""
        import subprocess
        import sys

        from tests.base import SCRIPTS_DIR

        def dm(*argv):
            proc = subprocess.run([sys.executable, "-B", str(SCRIPTS_DIR / "dm.py")] + list(argv) +
                                  ["--campaign", str(self.campaign_dir)], capture_output=True, text=True, timeout=60)
            return json.loads(proc.stdout)

        self.assertTrue(dm("init")["ok"])
        self.assertTrue(dm("character", "create", "--name", "Kira", "--class", "fighter", "--quick")["ok"])
        results = []

        def add_gold():
            for _ in range(4):
                results.append(dm("gold", "--who", "kira", "--add", "1"))

        threads = [threading.Thread(target=add_gold) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(r["ok"] for r in results), results)
        self.assertEqual(self.party()["characters"]["kira"]["gold_cp"], 1000 + 16 * 100)
        seqs = [line["seq"] for line in self.log_lines()]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))


class TestBoundsAndInvariants(PlayCase):
    def test_a_custom_monster_cannot_carry_negative_or_boolean_numbers(self):
        for bad in ({"xp_value": -100}, {"xp_value": True}, {"hp": True}, {"ac": 0}, {"count": 0}, {"count": 999}):
            spec = {"name": "Bad", "ac": 10, "hp": 5, "xp_value": 10}
            spec.update(bad)
            with self.subTest(bad=bad):
                self.refused("illegal_custom_monster", "encounter", "start", "--custom", json.dumps(spec))

    def test_a_custom_monster_with_a_bad_ability_is_refused_not_crashed(self):
        spec = {"name": "Bad", "ac": 10, "hp": 5, "xp_value": 10, "abilities": {"dex": "fast"}}
        self.refused("illegal_custom_monster", "encounter", "start", "--custom", json.dumps(spec))

    def test_a_level_up_while_dying_raises_max_hp_but_does_not_wake_the_character(self):
        self.drop("kira")
        self.ok("xp", "--who", "kira", "--amount", "300", rng=ScriptedRng([7]))
        kira = self.char("kira")
        self.assertEqual((kira["hp"]["current"], kira["hp"]["max"], kira["life_state"]), (0, 21, "dying"))

    def test_a_con_increase_while_stable_does_not_give_current_hp(self):
        self.ok("xp", "--who", "kira", "--amount", "2700", rng=ScriptedRng([5, 5, 5]))
        self.drop("kira")
        self.patch("kira", life_state="stable")
        self.ok("character", "asi", "--who", "kira", "--increase", "con:2")
        self.assertEqual(self.char("kira")["hp"]["current"], 0)

    def test_huge_amounts_are_refused_before_anything_is_written(self):
        before = self.snapshot()
        self.refused("illegal_value", "gold", "--who", "kira", "--add", "1" + "0" * 310)
        self.refused("illegal_value", "damage", "--who", "kira", "--amount", str(10 ** 12))
        self.refused("illegal_value", "xp", "--who", "kira", "--amount", str(10 ** 12))
        self.refused("illegal_value", "item", "add", "--who", "kira", "--item", "fixture-torch", "--qty", str(10 ** 12))
        self.refused("illegal_value", "track", "--name", "day", "--set", str(10 ** 12))
        self.assertEqual(before, self.snapshot())

    def test_gold_cannot_pass_the_cap_by_addition(self):
        self.ok("gold", "--who", "kira", "--add", "9000000")
        self.refused("illegal_value", "gold", "--who", "kira", "--add", "9000000")

    def test_a_character_named_twice_in_a_short_rest_is_refused_before_any_roll(self):
        self.ok("damage", "--who", "kira", "--amount", "5")
        before = self.snapshot()
        self.refused("bad_arguments", "rest", "short", "--dice", "kira:1,kira:0", rng=ScriptedRng([]))
        self.assertEqual(before, self.snapshot())

    def test_character_creation_logs_the_full_sheet_so_the_log_can_rebuild_a_save(self):
        line = [l for l in self.log_lines() if l["command"] == "character_create"][0]
        self.assertEqual(line["payload"]["details"]["sheet"]["abilities"]["str"], 16)


class TestEncounterEndIsIdempotent(PlayCase):
    def test_a_crash_after_the_xp_is_paid_does_not_pay_it_again_on_retry(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", "--average-hp", rng=ScriptedRng([20, 10, 1]))
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        saved = (self.campaign_dir / "encounter.json").read_text()
        self.assertEqual(self.ok("encounter", "end")["xp_awarded"], 50)
        # Simulate the crash window: the party was paid, but encounter.json was never deleted.
        (self.campaign_dir / "encounter.json").write_text(saved)
        out = self.ok("encounter", "end")
        self.assertEqual((out["xp_awarded"], out["already_paid"]), (0, True))
        self.assertEqual(self.char("kira")["xp"], 25)
        self.assertFalse((self.campaign_dir / "encounter.json").exists())

    def test_every_encounter_has_its_own_id(self):
        ids = []
        for _ in range(2):
            self.ok("encounter", "start", "--monster", "fixture-goblin:1", "--average-hp", rng=ScriptedRng([20, 10, 1]))
            ids.append(json.loads((self.campaign_dir / "encounter.json").read_text())["id"])
            self.ok("encounter", "end", "--no-xp")
        self.assertNotEqual(ids[0], ids[1])
