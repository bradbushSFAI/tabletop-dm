"""Defects found by the real-door playtest (2026-09-18)."""
import json

from tests.base import REAL_SKILL_ROOT, ScriptedRng
from tests.test_cmd_play import PlayCase


class RealDataCase(PlayCase):
    """These need the real class data (the Cleric), so they run against the real skill root."""
    SKILL_ROOT = REAL_SKILL_ROOT

    def setUp(self):
        super(PlayCase, self).setUp()      # CharacterCase.setUp: a temp folder and init, with no fixture characters
        self.ok("character", "create", "--name", "Ilsa", "--class", "cleric", "--quick")
        self.ok("character", "create", "--name", "Bram", "--class", "fighter", "--quick")


class TestDomainSpellsAreAlwaysPrepared(RealDataCase):
    def test_domain_spells_are_on_the_sheet_and_do_not_use_the_prepare_limit(self):
        casting = self.char("ilsa")["spellcasting"]
        self.assertEqual(casting["always_prepared"], ["bless", "cure-wounds"])
        self.assertEqual(len(casting["prepared"]), casting["prepare_limit"])
        self.assertFalse(set(casting["prepared"]) & set(casting["always_prepared"]))

    def test_an_always_prepared_spell_can_be_cast(self):
        self.assertEqual(self.ok("cast", "--who", "ilsa", "--spell", "bless")["slot_used"], 1)

    def test_preparing_the_full_list_works_and_domain_spells_in_it_cost_nothing(self):
        limit = self.char("ilsa")["spellcasting"]["prepare_limit"]
        picks = ["healing-word", "guiding-bolt", "shield-of-faith"][:limit]
        out = self.ok("spells", "prepare", "--who", "ilsa", "--spells", ",".join(picks + ["bless", "cure-wounds"]))
        self.assertEqual(out["prepared"], picks)
        self.assertEqual(out["always_prepared"], ["bless", "cure-wounds"])

    def test_higher_level_domain_spells_arrive_with_the_level(self):
        self.ok("xp", "--who", "ilsa", "--amount", "900", rng=ScriptedRng([4, 4]))
        self.assertIn("spiritual-weapon", self.char("ilsa")["spellcasting"]["always_prepared"])


class TestSeedPickGivesSomethingSafeToShow(RealDataCase):
    def test_pick_returns_the_roll_and_the_door_number_in_teaser_order(self):
        out = self.ok("seed", "pick", rng=ScriptedRng([3]))
        lines = [ln for ln in (REAL_SKILL_ROOT / "seeds" / "teasers.md").read_text().splitlines() if ln.strip()]
        self.assertEqual((out["roll"], out["doors"], out["door"]), (3, 5, 3))
        self.assertEqual(out["seed"], lines[2].split(":")[0])
        self.assertIn("door 3", out["show_the_player"])

    def test_choose_accepts_a_door_number(self):
        lines = [ln for ln in (REAL_SKILL_ROOT / "seeds" / "teasers.md").read_text().splitlines() if ln.strip()]
        self.assertEqual(self.ok("seed", "choose", "2")["seed"], lines[1].split(":")[0])


class TestBonusDiceAndPartyXp(RealDataCase):
    def test_a_bonus_die_is_rolled_and_added_by_the_script(self):
        out = self.ok("roll", "--who", "ilsa", "--check", "insight", "--bonus", "1d4", "--dc", "15", rng=ScriptedRng([10, 3]))
        base = self.char("ilsa")["skills"]["insight"]["bonus"]
        self.assertEqual((out["bonus"]["total"], out["total"]), (3, 10 + base + 3))

    def test_a_bonus_die_works_on_a_free_d20_roll_too(self):
        self.assertEqual(self.ok("roll", "1d20+2", "--bonus", "1d4", rng=ScriptedRng([10, 4]))["total"], 16)

    def test_a_bad_bonus_expression_is_refused(self):
        self.refused("bad_expression", "roll", "--who", "ilsa", "--check", "insight", "--bonus", "lots")

    def test_party_xp_is_split_by_the_script(self):
        out = self.ok("xp", "--party", "--amount", "101")
        self.assertEqual(out["xp_per_member"], 50)
        self.assertEqual((self.char("ilsa")["xp"], self.char("bram")["xp"]), (50, 50))

    def test_party_and_who_together_is_refused(self):
        self.refused("bad_arguments", "xp", "--party", "--who", "ilsa", "--amount", "10")
        self.refused("bad_arguments", "xp", "--amount", "10")


class TestHeavyArmourAndStealth(RealDataCase):
    def test_the_sheet_says_when_armour_gives_stealth_disadvantage(self):
        self.assertTrue(self.char("bram")["stealth_disadvantage"])       # chain mail
        self.ok("unequip", "--who", "bram", "--slot", "armor")
        self.assertFalse(self.char("bram")["stealth_disadvantage"])

    def test_a_stealth_check_in_heavy_armour_rolls_with_disadvantage(self):
        out = self.ok("roll", "--who", "bram", "--check", "stealth", rng=ScriptedRng([17, 4]))
        self.assertEqual((out["d20"]["mode"], out["natural"]), ("disadvantage", 4))
        self.assertIn("armour", out["note"])

    def test_advantage_cancels_it(self):
        out = self.ok("roll", "--who", "bram", "--check", "stealth", "--adv", rng=ScriptedRng([17]))
        self.assertEqual(out["d20"]["mode"], "normal")


class TestCountersCanBeHiddenFromThePlayer(RealDataCase):
    def test_a_secret_counter_is_not_in_status_under_its_name(self):
        self.ok("track", "--name", "the baron strikes", "--set", "5", "--secret")
        status = self.ok("status")
        self.assertNotIn("the-baron-strikes", json.dumps(status))
        self.assertEqual(status["secret_counters"], 1)

    def test_the_dm_can_still_read_and_spend_it(self):
        self.ok("track", "--name", "the baron strikes", "--set", "5", "--secret")
        self.assertEqual(self.ok("track", "--name", "the baron strikes", "--add", "-1")["value"], 4)
        self.assertEqual(self.ok("track", "--list")["secret"], {"the-baron-strikes": 4})

    def test_the_name_is_not_stored_in_clear_text_in_party_json(self):
        self.ok("track", "--name", "the baron strikes", "--set", "5", "--secret")
        self.assertNotIn("baron", (self.campaign_dir / "party.json").read_text())
        self.assertNotIn("baron", (self.campaign_dir / "log.jsonl").read_text())
