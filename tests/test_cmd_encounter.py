import json

from tests.base import ScriptedRng
from tests.test_cmd_play import PlayCase

CUSTOM = json.dumps({"name": "Swamp Brute", "count": 1, "ac": 14, "hp": 27,
                     "abilities": {"str": 17, "dex": 10, "con": 15, "int": 6, "wis": 10, "cha": 6},
                     "attacks": [{"name": "slam", "attack_bonus": 5, "damage_expr": "2d6+3", "damage_type": "bludgeoning"}],
                     "tactic": "Grapples the nearest foe.", "challenge_rating": 2})


class TestEncounterStart(PlayCase):
    def start(self, *monsters, rng=None):
        args = []
        for m in monsters:
            args += ["--monster", m]
        return self.ok("encounter", "start", *args, rng=rng)

    def test_start_creates_encounter_json_with_numbered_monsters(self):
        out = self.start("fixture-goblin:2", rng=ScriptedRng([10, 10, 10, 3, 4, 5, 6]))
        self.assertTrue((self.campaign_dir / "encounter.json").exists())
        self.assertEqual(sorted(out["monsters"]), ["fixture-goblin-1", "fixture-goblin-2"])

    def test_monster_hp_is_rolled_from_its_hit_dice(self):
        # rolls: kira init, thorn init, goblin init, then goblin hp 2d6
        out = self.start("fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        self.assertEqual(out["monsters"]["fixture-goblin-1"]["hp"], {"current": 7, "max": 7})

    def test_average_hp_flag_uses_the_printed_average_and_no_hp_dice(self):
        out = self.ok("encounter", "start", "--monster", "fixture-brute:1", "--average-hp", rng=ScriptedRng([10, 10, 10]))
        self.assertEqual(out["monsters"]["fixture-brute-1"]["hp"]["max"], 59)

    def test_initiative_is_sorted_high_to_low_with_dex_as_the_tie_break(self):
        # kira dex+2, thorn dex+2, goblin dex+2: rolls 5, 15, 15 -> thorn 17, goblin 17, kira 7
        out = self.start("fixture-goblin:1", rng=ScriptedRng([5, 15, 15, 3, 4]))
        self.assertEqual([c["id"] for c in out["initiative_order"]][-1], "kira")
        self.assertEqual(out["initiative_order"][0]["initiative"], 17)
        self.assertEqual(out["turn"]["id"], out["initiative_order"][0]["id"])

    def test_every_initiative_roll_is_logged(self):
        lines = len(self.log_lines())
        self.start("fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        new = self.log_lines()[lines:]
        self.assertEqual([l["type"] for l in new].count("roll"), 4)  # 3 initiative + 1 hp
        self.assertEqual(new[-1]["type"], "state_change")

    def test_a_second_start_is_refused(self):
        self.start("fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        before = self.snapshot()
        self.refused("encounter_active", "encounter", "start", "--monster", "fixture-wolf:1")
        self.assertEqual(before, self.snapshot())

    def test_unknown_monster_suggests_a_near_match(self):
        out = self.refused("unknown_name", "encounter", "start", "--monster", "fixture-goblim:1")
        self.assertIn("fixture-goblin", out["error"]["message"])

    def test_a_fight_needs_at_least_one_monster(self):
        self.refused("bad_arguments", "encounter", "start")

    def test_custom_monster_takes_xp_from_its_challenge_rating(self):
        out = self.ok("encounter", "start", "--custom", CUSTOM, rng=ScriptedRng([10, 10, 10]))
        brute = out["monsters"]["swamp-brute-1"]
        self.assertEqual((brute["xp_value"], brute["custom"], brute["hp"]["max"], brute["ac"]), (450, True, 27, 14))

    def test_custom_monster_without_cr_or_xp_is_refused(self):
        bad = json.loads(CUSTOM)
        del bad["challenge_rating"]
        self.refused("illegal_custom_monster", "encounter", "start", "--custom", json.dumps(bad))

    def test_custom_monster_that_is_not_json_is_refused(self):
        self.refused("illegal_custom_monster", "encounter", "start", "--custom", "{oops")

    def test_dead_and_departed_characters_do_not_roll_initiative(self):
        self.ok("character", "retire", "--who", "thorn", "--status", "departed")
        out = self.start("fixture-goblin:1", rng=ScriptedRng([10, 10, 3, 4]))
        self.assertNotIn("thorn", [c["id"] for c in out["initiative_order"]])

    def test_status_shows_the_active_fight(self):
        self.start("fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        out = self.ok("status")
        self.assertTrue(out["encounter_active"])
        self.assertEqual(out["encounter"]["monsters"], {"fixture-goblin-1": "7/7"})


class TestEncounterAdd(PlayCase):
    def test_reinforcements_continue_the_numbering_and_join_the_order(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:2", rng=ScriptedRng([10, 10, 10, 1, 1, 1, 1]))
        out = self.ok("encounter", "add", "--monster", "fixture-goblin:1", rng=ScriptedRng([20, 1, 1]))
        self.assertEqual(out["added"], ["fixture-goblin-3"])
        self.assertEqual(out["initiative_order"][0]["id"], "fixture-goblin-3")

    def test_the_current_turn_does_not_change_when_someone_joins_above_it(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 1, 1]))
        now = self.ok("status")["encounter"]["turn"]
        self.ok("encounter", "add", "--monster", "fixture-wolf:1", rng=ScriptedRng([20, 1, 1]))
        self.assertEqual(self.ok("status")["encounter"]["turn"], now)

    def test_add_without_a_fight_is_refused(self):
        self.refused("no_active_encounter", "encounter", "add", "--monster", "fixture-goblin:1")


class TestEncounterNext(PlayCase):
    def begin(self):
        # kira 20+2, thorn 10+2, goblin 1+2
        return self.ok("encounter", "start", "--monster", "fixture-goblin:1", rng=ScriptedRng([20, 10, 1, 3, 4]))

    def test_next_walks_the_order_and_wraps_into_round_two(self):
        self.begin()
        self.assertEqual(self.ok("encounter", "next")["turn"]["id"], "thorn")
        self.assertEqual(self.ok("encounter", "next")["turn"]["id"], "fixture-goblin-1")
        out = self.ok("encounter", "next")
        self.assertEqual((out["turn"]["id"], out["round"]), ("kira", 2))

    def test_defeated_monsters_are_skipped(self):
        self.begin()
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.ok("encounter", "next")
        self.assertEqual(self.ok("encounter", "next")["turn"]["id"], "kira")

    def test_a_dying_character_still_gets_a_turn_for_the_death_save(self):
        self.begin()
        self.drop("thorn")
        out = self.ok("encounter", "next")
        self.assertEqual((out["turn"]["id"], out["turn"]["note"]), ("thorn", "dying: run deathsave"))

    def test_stable_and_dead_characters_are_skipped(self):
        self.begin()
        self.ok("damage", "--who", "thorn", "--amount", "14")
        self.assertEqual(self.ok("encounter", "next")["turn"]["id"], "fixture-goblin-1")

    def test_next_without_a_fight_is_refused(self):
        self.refused("no_active_encounter", "encounter", "next")


class TestEncounterEnd(PlayCase):
    def fight(self, monsters="fixture-goblin:2", rolls=None):
        self.ok("encounter", "start", "--monster", monsters, "--average-hp", rng=ScriptedRng(rolls or [10, 10, 10, 10]))

    def test_end_splits_the_xp_of_defeated_monsters_and_deletes_the_file(self):
        self.fight()
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.ok("damage", "--who", "fixture-goblin-2", "--amount", "99")
        out = self.ok("encounter", "end")
        self.assertEqual((out["xp_awarded"], out["xp_per_member"]), (100, 50))
        self.assertEqual(self.char("kira")["xp"], 50)
        self.assertFalse((self.campaign_dir / "encounter.json").exists())

    def test_only_defeated_monsters_give_xp(self):
        self.fight()
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.assertEqual(self.ok("encounter", "end")["xp_awarded"], 50)

    def test_no_xp_flag_awards_nothing(self):
        self.fight()
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.assertEqual(self.ok("encounter", "end", "--no-xp")["xp_awarded"], 0)
        self.assertEqual(self.char("kira")["xp"], 0)

    def test_the_dead_get_no_share_but_the_dying_and_stable_do(self):
        self.fight()
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.ok("damage", "--who", "fixture-goblin-2", "--amount", "99")
        self.ok("damage", "--who", "thorn", "--amount", "14")
        out = self.ok("encounter", "end")
        self.assertEqual(out["xp_per_member"], 100)
        self.assertEqual(self.char("thorn")["xp"], 0)

    def test_xp_from_a_fight_can_level_a_character_up(self):
        self.fight("fixture-brute:2", rolls=[10, 10, 10, 10])
        self.ok("damage", "--who", "fixture-brute-1", "--amount", "99")
        self.ok("damage", "--who", "fixture-brute-2", "--amount", "99")
        out = self.ok("encounter", "end", rng=ScriptedRng([5, 3]))
        self.assertEqual(out["level_ups"]["kira"]["to"], 2)
        self.assertEqual(self.char("thorn")["level"], 2)

    def test_end_is_refused_while_the_hero_is_fallen(self):
        self.fight()
        self.ok("damage", "--who", "kira", "--amount", "24")
        before = self.snapshot()
        self.refused("hero_not_resolved", "encounter", "end")
        self.assertEqual(before, self.snapshot())

    def test_a_level_five_character_still_gets_a_clean_end(self):
        self.ok("xp", "--who", "kira", "--amount", "6500", rng=ScriptedRng([5, 5, 5, 5]))
        self.fight()
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.ok("encounter", "end")

    def test_end_without_a_fight_is_refused(self):
        self.refused("no_active_encounter", "encounter", "end")
