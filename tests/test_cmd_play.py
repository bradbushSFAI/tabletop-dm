import json

from tests.base import ScriptedRng
from tests.test_cmd_character import CharacterCase


class PlayCase(CharacterCase):
    def setUp(self):
        super().setUp()
        self.make_fighter()          # kira, hero, 12 HP, con +2, d10
        self.make_wizard()           # thorn, companion, 7 HP

    def patch(self, cid, **fields):
        party = self.party()
        for key, value in fields.items():
            party["characters"][cid][key] = value
        (self.campaign_dir / "party.json").write_text(json.dumps(party))

    def drop(self, cid):
        """Take a character to 0 HP with the normal command."""
        hp = self.char(cid)["hp"]["current"]
        return self.ok("damage", "--who", cid, "--amount", str(hp))


class TestDamageHealCommand(PlayCase):
    def test_damage_reduces_hp_and_reports_the_state(self):
        out = self.ok("damage", "--who", "kira", "--amount", "5")
        self.assertEqual((out["hp"], out["life_state"]), ("7/12", "alive"))
        self.assertEqual(self.char("kira")["hp"]["current"], 7)

    def test_damage_to_zero_makes_the_character_dying(self):
        self.assertEqual(self.drop("kira")["life_state"], "dying")

    def test_massive_damage_to_the_hero_gives_fallen_and_a_note(self):
        out = self.ok("damage", "--who", "kira", "--amount", "24")
        self.assertEqual((out["life_state"], out["note"]), ("fallen", "massive damage"))
        self.assertIn("grit", out["next"])

    def test_massive_damage_to_a_companion_gives_dead(self):
        self.assertEqual(self.ok("damage", "--who", "thorn", "--amount", "14")["life_state"], "dead")

    def test_crit_flag_adds_two_failures_to_a_dying_character(self):
        self.drop("kira")
        out = self.ok("damage", "--who", "kira", "--amount", "1", "--crit")
        self.assertEqual(out["death_saves"]["failures"], 2)

    def test_heal_wakes_a_dying_character(self):
        self.drop("kira")
        out = self.ok("heal", "--who", "kira", "--amount", "3")
        self.assertEqual((out["hp"], out["life_state"]), ("3/12", "alive"))

    def test_heal_on_a_fallen_hero_is_refused(self):
        self.ok("damage", "--who", "kira", "--amount", "24")
        before = self.snapshot()
        self.refused("not_eligible_for_heal", "heal", "--who", "kira", "--amount", "5")
        self.assertEqual(before, self.snapshot())

    def test_amount_must_be_positive(self):
        self.refused("illegal_value", "damage", "--who", "kira", "--amount", "0")
        self.refused("illegal_value", "heal", "--who", "kira", "--amount", "-3")

    def test_unknown_target_is_refused(self):
        self.refused("unknown_id", "damage", "--who", "grog", "--amount", "3")

    def test_temp_hp_can_be_granted_and_does_not_stack(self):
        self.ok("heal", "--who", "kira", "--amount", "5", "--temp")
        self.ok("heal", "--who", "kira", "--amount", "3", "--temp")
        self.assertEqual(self.char("kira")["hp"]["temp"], 5)

    def test_damage_is_logged_with_before_and_after(self):
        self.ok("damage", "--who", "kira", "--amount", "5")
        payload = self.log_lines()[-1]["payload"]
        self.assertEqual((payload["field"], payload["before"], payload["after"]), ("hp.current", 12, 7))

    def test_monster_damage_and_defeat(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        out = self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.assertEqual((out["hp"], out["defeated"]), ("0/7", True))

    def test_monster_heal_is_capped_and_revives_a_defeated_monster(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        out = self.ok("heal", "--who", "fixture-goblin-1", "--amount", "50")
        self.assertEqual((out["hp"], out["defeated"]), ("7/7", False))


class TestCastCommand(PlayCase):
    def test_cast_spends_a_slot_of_the_spell_level(self):
        out = self.ok("cast", "--who", "thorn", "--spell", "fixture-bolt")
        self.assertEqual(out["slot_used"], 1)
        self.assertEqual(self.char("thorn")["spellcasting"]["slots"]["1"], {"max": 2, "used": 1})
        self.assertEqual(out["spell"]["damage_expr"], "3d4+3")
        self.assertEqual(out["save_dc"], 13)

    def test_no_slot_left_is_refused(self):
        self.ok("cast", "--who", "thorn", "--spell", "fixture-bolt")
        self.ok("cast", "--who", "thorn", "--spell", "fixture-bolt")
        before = self.snapshot()
        self.refused("no_slot_available", "cast", "--who", "thorn", "--spell", "fixture-bolt")
        self.assertEqual(before, self.snapshot())

    def test_cantrip_spends_nothing_but_is_logged(self):
        lines = len(self.log_lines())
        out = self.ok("cast", "--who", "thorn", "--spell", "fixture-spark")
        self.assertEqual(out["slot_used"], 0)
        self.assertEqual(self.char("thorn")["spellcasting"]["slots"]["1"]["used"], 0)
        self.assertEqual(len(self.log_lines()), lines + 1)

    def test_unknown_cantrip_is_refused(self):
        self.refused("spell_not_prepared", "cast", "--who", "thorn", "--spell", "fixture-glow")

    def test_unprepared_spell_is_refused(self):
        self.ok("spells", "prepare", "--who", "thorn", "--spells", "fixture-ward")
        self.refused("spell_not_prepared", "cast", "--who", "thorn", "--spell", "fixture-bolt")

    def test_upcast_spends_the_higher_slot(self):
        self.ok("xp", "--who", "thorn", "--amount", "900", rng=ScriptedRng([3, 3]))
        out = self.ok("cast", "--who", "thorn", "--spell", "fixture-bolt", "--slot", "2")
        self.assertEqual(out["slot_used"], 2)
        self.assertEqual(self.char("thorn")["spellcasting"]["slots"]["2"]["used"], 1)

    def test_slot_below_the_spell_level_is_refused(self):
        self.ok("xp", "--who", "thorn", "--amount", "900", rng=ScriptedRng([3, 3]))
        self.ok("spells", "learn", "--who", "thorn", "--spells", "fixture-beam")
        self.ok("spells", "prepare", "--who", "thorn", "--spells", "fixture-beam")
        self.refused("slot_too_low", "cast", "--who", "thorn", "--spell", "fixture-beam", "--slot", "1")

    def test_non_caster_is_refused(self):
        self.refused("not_a_caster", "cast", "--who", "kira", "--spell", "fixture-bolt")

    def test_unconscious_caster_is_refused(self):
        self.drop("thorn")
        self.refused("cannot_act", "cast", "--who", "thorn", "--spell", "fixture-bolt")


class TestRestShortCommand(PlayCase):
    def test_short_rest_spends_hit_dice_and_heals_die_plus_con(self):
        self.ok("damage", "--who", "kira", "--amount", "10")
        out = self.ok("rest", "short", "--dice", "kira:1", rng=ScriptedRng([4]))
        self.assertEqual(out["results"]["kira"], {"dice_spent": 1, "rolls": [4], "con_modifier": 2, "hp_rolled": 6,
                                                  "hp_gained": 6, "hp": "8/12", "life_state": "alive"})
        self.assertEqual(self.char("kira")["hit_dice"]["remaining"], 0)

    def test_healing_is_capped_at_max_hp(self):
        self.ok("damage", "--who", "kira", "--amount", "2")
        out = self.ok("rest", "short", "--dice", "kira:1", rng=ScriptedRng([10]))
        self.assertEqual(out["results"]["kira"]["hp"], "12/12")

    def test_more_dice_than_remaining_is_refused(self):
        before = self.snapshot()
        self.refused("insufficient_hit_dice", "rest", "short", "--dice", "kira:2")
        self.assertEqual(before, self.snapshot())

    def test_rest_during_a_fight_is_refused(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        self.refused("encounter_active", "rest", "short", "--dice", "kira:1")
        self.refused("encounter_active", "rest", "long")

    def test_stable_character_who_spends_no_dice_stays_stable(self):
        self.drop("kira")
        self.patch("kira", life_state="stable")
        out = self.ok("rest", "short", "--dice", "kira:0")
        self.assertEqual(out["results"]["kira"]["life_state"], "stable")

    def test_stable_character_who_gains_hp_wakes(self):
        self.drop("kira")
        self.patch("kira", life_state="stable")
        out = self.ok("rest", "short", "--dice", "kira:1", rng=ScriptedRng([3]))
        self.assertEqual(out["results"]["kira"]["life_state"], "alive")

    def test_short_rest_with_no_dice_flag_is_legal(self):
        self.ok("rest", "short")

    def test_each_hit_die_is_logged_as_a_roll(self):
        self.ok("damage", "--who", "kira", "--amount", "10")
        self.ok("rest", "short", "--dice", "kira:1", rng=ScriptedRng([4]))
        self.assertEqual([line["type"] for line in self.log_lines()[-2:]], ["roll", "state_change"])

    def test_bad_dice_argument_is_refused(self):
        self.refused("bad_arguments", "rest", "short", "--dice", "kira=1")


class TestRestLongCommand(PlayCase):
    def test_long_rest_restores_hp_slots_and_half_the_hit_dice(self):
        self.ok("xp", "--who", "thorn", "--amount", "2700", rng=ScriptedRng([3, 3, 3]))
        self.ok("cast", "--who", "thorn", "--spell", "fixture-bolt")
        self.ok("damage", "--who", "thorn", "--amount", "5")
        self.patch("thorn", hit_dice={"die": "d6", "max": 4, "remaining": 0})
        out = self.ok("rest", "long")
        thorn = self.char("thorn")
        self.assertEqual(thorn["hp"]["current"], thorn["hp"]["max"])
        self.assertEqual(thorn["spellcasting"]["slots"]["1"]["used"], 0)
        self.assertEqual(thorn["hit_dice"]["remaining"], 2)
        self.assertIn("thorn", out["results"])

    def test_long_rest_restores_at_least_one_hit_die(self):
        self.patch("kira", hit_dice={"die": "d10", "max": 1, "remaining": 0})
        self.ok("rest", "long")
        self.assertEqual(self.char("kira")["hit_dice"]["remaining"], 1)

    def test_long_rest_resets_the_grit_save_and_wakes_a_stable_hero(self):
        self.drop("kira")
        self.patch("kira", life_state="stable", grit_used_since_long_rest=True)
        self.ok("rest", "long")
        kira = self.char("kira")
        self.assertEqual((kira["life_state"], kira["grit_used_since_long_rest"]), ("alive", False))

    def test_long_rest_skips_the_dead(self):
        self.ok("damage", "--who", "thorn", "--amount", "14")
        out = self.ok("rest", "long")
        self.assertNotIn("thorn", out["results"])

    def test_long_rest_with_a_fallen_hero_is_refused(self):
        self.ok("damage", "--who", "kira", "--amount", "24")
        self.refused("hero_not_resolved", "rest", "long")


class TestItemCommands(PlayCase):
    def test_add_a_data_item_stacks_quantity(self):
        self.ok("item", "add", "--who", "kira", "--item", "fixture-torch", "--qty", "2")
        self.assertIn({"item": "fixture-torch", "quantity": 5}, self.char("kira")["inventory"])

    def test_add_loot_the_dm_invented(self):
        self.ok("item", "add", "--who", "kira", "--name", "Moonstone Key", "--note", "opens the old gate")
        line = [l for l in self.char("kira")["inventory"] if l["item"] == "moonstone-key"][0]
        self.assertEqual((line["custom"], line["name"], line["note"]), (True, "Moonstone Key", "opens the old gate"))

    def test_unknown_item_id_is_refused_and_points_to_name(self):
        out = self.refused("unknown_name", "item", "add", "--who", "kira", "--item", "laser-gun")
        self.assertIn("--name", out["error"]["message"])

    def test_remove_lowers_quantity_and_prunes_at_zero(self):
        self.ok("item", "remove", "--who", "kira", "--item", "fixture-torch", "--qty", "3")
        self.assertFalse([l for l in self.char("kira")["inventory"] if l["item"] == "fixture-torch"])

    def test_remove_more_than_carried_is_refused(self):
        before = self.snapshot()
        self.refused("item_not_in_inventory", "item", "remove", "--who", "kira", "--item", "fixture-torch", "--qty", "4")
        self.assertEqual(before, self.snapshot())

    def test_removing_the_last_copy_of_an_equipped_item_unequips_it(self):
        out = self.ok("item", "remove", "--who", "kira", "--item", "fixture-shield")
        self.assertIsNone(self.char("kira")["equipped"]["shield"])
        self.assertEqual(out["ac"], 17)

    def test_give_moves_an_item_between_characters(self):
        self.ok("item", "remove", "--who", "kira", "--item", "fixture-torch", "--qty", "1", "--give-to", "thorn")
        self.assertIn({"item": "fixture-torch", "quantity": 1}, self.char("thorn")["inventory"])
        self.assertIn({"item": "fixture-torch", "quantity": 2}, self.char("kira")["inventory"])

    def test_quantity_must_be_positive(self):
        self.refused("illegal_value", "item", "add", "--who", "kira", "--item", "fixture-torch", "--qty", "0")


class TestGoldCommand(PlayCase):
    def test_add_and_spend_in_gp(self):
        self.assertEqual(self.ok("gold", "--who", "kira", "--add", "5.5")["gold_gp"], 15.5)
        self.assertEqual(self.ok("gold", "--who", "kira", "--spend", "0.01")["gold_gp"], 15.49)
        self.assertEqual(self.char("kira")["gold_cp"], 1549)

    def test_spending_more_than_carried_is_refused(self):
        before = self.snapshot()
        out = self.refused("insufficient_gold", "gold", "--who", "kira", "--spend", "10.01")
        self.assertIn("10", out["error"]["message"])
        self.assertEqual(before, self.snapshot())

    def test_add_and_spend_together_is_refused(self):
        self.refused("bad_arguments", "gold", "--who", "kira", "--add", "1", "--spend", "1")

    def test_neither_flag_is_refused(self):
        self.refused("bad_arguments", "gold", "--who", "kira")

    def test_amount_must_be_positive_with_at_most_two_decimals(self):
        self.refused("illegal_value", "gold", "--who", "kira", "--add", "-1")
        self.refused("illegal_value", "gold", "--who", "kira", "--add", "1.005")

    def test_give_moves_gold_to_another_character(self):
        self.ok("gold", "--who", "kira", "--spend", "4", "--give-to", "thorn")
        self.assertEqual((self.char("kira")["gold_cp"], self.char("thorn")["gold_cp"]), (600, 1400))


class TestConditionCommands(PlayCase):
    def test_add_and_remove(self):
        self.assertEqual(self.ok("condition", "add", "--who", "kira", "--condition", "poisoned")["conditions"], ["poisoned"])
        self.assertEqual(self.ok("condition", "remove", "--who", "kira", "--condition", "poisoned")["conditions"], [])

    def test_unknown_condition_lists_the_legal_ones(self):
        out = self.refused("unknown_condition", "condition", "add", "--who", "kira", "--condition", "sleepy")
        self.assertIn("poisoned", out["error"]["message"])

    def test_adding_twice_does_not_duplicate(self):
        self.ok("condition", "add", "--who", "kira", "--condition", "prone")
        self.assertEqual(self.ok("condition", "add", "--who", "kira", "--condition", "prone")["conditions"], ["prone"])

    def test_removing_an_absent_condition_is_refused(self):
        self.refused("condition_not_present", "condition", "remove", "--who", "kira", "--condition", "prone")

    def test_a_monster_can_carry_a_condition(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        out = self.ok("condition", "add", "--who", "fixture-goblin-1", "--condition", "restrained")
        self.assertEqual(out["conditions"], ["restrained"])


class TestDeathsaveCommand(PlayCase):
    def test_a_success_is_counted_and_shown(self):
        self.drop("kira")
        out = self.ok("deathsave", "--who", "kira", rng=ScriptedRng([14]))
        self.assertEqual((out["roll"], out["result"], out["successes"], out["life_state"]), (14, "success", 1, "dying"))

    def test_three_failures_make_the_hero_fallen_and_point_to_grit(self):
        self.drop("kira")
        for _ in range(2):
            self.ok("deathsave", "--who", "kira", rng=ScriptedRng([5]))
        out = self.ok("deathsave", "--who", "kira", rng=ScriptedRng([5]))
        self.assertEqual(out["life_state"], "fallen")
        self.assertIn("grit", out["next"])

    def test_three_failures_kill_a_companion(self):
        self.drop("thorn")
        for _ in range(2):
            self.ok("deathsave", "--who", "thorn", rng=ScriptedRng([5]))
        self.assertEqual(self.ok("deathsave", "--who", "thorn", rng=ScriptedRng([5]))["life_state"], "dead")

    def test_natural_twenty_wakes_the_character_at_one_hp(self):
        self.drop("kira")
        out = self.ok("deathsave", "--who", "kira", rng=ScriptedRng([20]))
        self.assertEqual((out["life_state"], out["hp"]), ("alive", "1/12"))

    def test_not_dying_is_refused(self):
        self.refused("not_dying", "deathsave", "--who", "kira")

    def test_the_roll_and_the_change_are_both_logged(self):
        self.drop("kira")
        self.ok("deathsave", "--who", "kira", rng=ScriptedRng([14]))
        self.assertEqual([line["type"] for line in self.log_lines()[-2:]], ["roll", "state_change"])


class TestGritCommand(PlayCase):
    def fall(self):
        self.ok("damage", "--who", "kira", "--amount", "24")

    def test_success_is_a_light_cost_and_the_hero_is_stable(self):
        self.fall()
        out = self.ok("grit", "--dc", "10", rng=ScriptedRng([8]))   # 8 + con save 4 = 12
        self.assertEqual((out["outcome"], out["life_state"], out["total"], out["who"]), ("light_cost", "stable", 12, "kira"))
        self.assertTrue(self.char("kira")["grit_used_since_long_rest"])

    def test_failure_on_standard_is_a_heavy_cost(self):
        self.fall()
        out = self.ok("grit", "--dc", "15", rng=ScriptedRng([5]))
        self.assertEqual((out["outcome"], out["life_state"]), ("heavy_cost", "stable"))

    def test_failure_on_iron_is_death(self):
        self.ok("settings", "set", "--difficulty", "iron")
        self.fall()
        out = self.ok("grit", "--dc", "15", rng=ScriptedRng([5]))
        self.assertEqual((out["outcome"], out["life_state"]), ("dead", "dead"))

    def test_failure_on_story_is_still_a_light_cost(self):
        self.ok("settings", "set", "--difficulty", "story")
        self.fall()
        self.assertEqual(self.ok("grit", "--dc", "15", rng=ScriptedRng([5]))["outcome"], "light_cost")

    def test_already_used_means_no_roll_and_an_automatic_failure(self):
        self.patch("kira", grit_used_since_long_rest=True)
        self.fall()
        lines = len(self.log_lines())
        out = self.ok("grit", "--dc", "10", rng=ScriptedRng([]))
        self.assertIsNone(out["roll"])
        self.assertEqual(out["outcome"], "heavy_cost")
        self.assertEqual([l["type"] for l in self.log_lines()[lines:]], ["state_change"])

    def test_not_fallen_is_refused(self):
        self.refused("not_fallen", "grit", "--dc", "10")

    def test_dc_is_required_and_must_be_sane(self):
        self.fall()
        self.refused("bad_arguments", "grit")
        self.refused("illegal_value", "grit", "--dc", "0")

    def test_a_rolled_grit_save_logs_the_roll_then_the_change(self):
        self.fall()
        self.ok("grit", "--dc", "10", rng=ScriptedRng([8]))
        self.assertEqual([line["type"] for line in self.log_lines()[-2:]], ["roll", "state_change"])


class TestCharacterRetire(PlayCase):
    def test_a_companion_can_depart_or_die(self):
        self.assertEqual(self.ok("character", "retire", "--who", "thorn", "--status", "departed")["life_state"], "departed")

    def test_the_sheet_stays_in_the_file(self):
        self.ok("character", "retire", "--who", "thorn", "--status", "dead")
        self.assertIn("thorn", self.party()["characters"])

    def test_hero_death_needs_the_player_accepted_flag_in_every_difficulty(self):
        for difficulty in ("story", "standard", "iron"):
            self.ok("settings", "set", "--difficulty", difficulty) if difficulty != "standard" else None
            self.refused("hero_death_needs_confirmation", "character", "retire", "--who", "kira", "--status", "dead")
        self.ok("character", "retire", "--who", "kira", "--status", "dead", "--player-accepted")
        self.assertEqual(self.char("kira")["life_state"], "dead")

    def test_retiring_twice_is_refused(self):
        self.ok("character", "retire", "--who", "thorn", "--status", "dead")
        self.refused("not_active", "character", "retire", "--who", "thorn", "--status", "departed")

    def test_a_retired_companion_frees_a_party_slot(self):
        self.make_fighter("bron")
        self.ok("character", "retire", "--who", "thorn", "--status", "departed")
        self.make_fighter("dax")


class TestCharacterPromote(PlayCase):
    def test_promote_is_refused_while_the_hero_is_active(self):
        self.refused("promotion_not_allowed", "character", "promote", "thorn")

    def test_a_companion_becomes_the_hero_after_the_hero_dies(self):
        self.ok("character", "retire", "--who", "kira", "--status", "dead", "--player-accepted")
        self.assertEqual(self.ok("character", "promote", "thorn")["hero_id"], "thorn")
        self.assertEqual(self.party()["hero_id"], "thorn")
        self.assertEqual(self.char("kira")["life_state"], "dead")

    def test_a_dead_companion_cannot_be_promoted(self):
        self.ok("character", "retire", "--who", "kira", "--status", "dead", "--player-accepted")
        self.ok("character", "retire", "--who", "thorn", "--status", "dead")
        self.refused("not_active", "character", "promote", "thorn")

    def test_the_new_hero_gets_the_grit_save(self):
        self.ok("character", "retire", "--who", "kira", "--status", "dead", "--player-accepted")
        self.ok("character", "promote", "thorn")
        self.ok("damage", "--who", "thorn", "--amount", "14")
        self.assertEqual(self.char("thorn")["life_state"], "fallen")


class TestSeedCommands(PlayCase):
    def test_choose_records_the_seed(self):
        self.assertEqual(self.ok("seed", "choose", "fixture-seed-b")["seed"], "fixture-seed-b")
        self.assertEqual(self.party()["settings"]["seed"], "fixture-seed-b")

    def test_choose_returns_the_path_of_the_seed_file_for_the_dm_to_copy(self):
        out = self.ok("seed", "choose", "fixture-seed-a")
        self.assertTrue(out["seed_file"].endswith("seeds/fixture-seed-a.md"))

    def test_pick_is_a_logged_random_choice(self):
        out = self.ok("seed", "pick", rng=ScriptedRng([2]))
        self.assertEqual(out["seed"], "fixture-seed-b")
        self.assertEqual([line["type"] for line in self.log_lines()[-2:]], ["roll", "state_change"])

    def test_unknown_seed_is_refused(self):
        self.refused("seed_unknown", "seed", "choose", "fixture-seed-z")

    def test_teasers_is_not_a_seed(self):
        self.refused("seed_unknown", "seed", "choose", "teasers")

    def test_a_second_choice_is_refused(self):
        self.ok("seed", "choose", "fixture-seed-a")
        self.refused("seed_already_set", "seed", "pick")

    def test_list_shows_the_names_only(self):
        self.assertEqual(self.ok("seed", "list")["seeds"], ["fixture-seed-a", "fixture-seed-b"])


class TestStabilizeCommand(PlayCase):
    def test_stabilize_stops_the_death_saves(self):
        self.drop("kira")
        self.ok("deathsave", "--who", "kira", rng=ScriptedRng([5]))
        out = self.ok("stabilize", "--who", "kira")
        self.assertEqual(out["life_state"], "stable")
        self.assertEqual(self.char("kira")["death_saves"], {"successes": 0, "failures": 0})

    def test_stabilize_needs_a_dying_character(self):
        self.refused("not_dying", "stabilize", "--who", "kira")


class TestPlaytestFindings(PlayCase):
    """Defects found by the first DM playtest (2026-09-18)."""

    def test_character_set_saves_the_hooks_after_a_quick_start(self):
        self.ok("character", "set", "--who", "kira", "--background", "Dock rat", "--bond", "Owes Osk", "--flaw", "Greedy")
        kira = self.char("kira")
        self.assertEqual((kira["background"], kira["bond"], kira["flaw"]), ("Dock rat", "Owes Osk", "Greedy"))

    def test_character_set_needs_at_least_one_field(self):
        self.refused("nothing_to_set", "character", "set", "--who", "kira")

    def test_short_rest_shows_the_modifier_and_the_sum_so_the_dm_does_no_arithmetic(self):
        self.ok("damage", "--who", "kira", "--amount", "10")
        out = self.ok("rest", "short", "--dice", "kira:1", rng=ScriptedRng([4]))["results"]["kira"]
        self.assertEqual((out["rolls"], out["con_modifier"], out["hp_rolled"], out["hp_gained"]), ([4], 2, 6, 6))

    def test_encounter_next_reports_monster_hp_so_the_dm_holds_nothing_in_memory(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", rng=ScriptedRng([10, 10, 10, 3, 4]))
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "3")
        self.assertEqual(self.ok("encounter", "next")["monsters"], {"fixture-goblin-1": "4/7"})

    def test_a_monster_that_flees_leaves_the_order_and_gives_no_xp(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:2", "--average-hp", rng=ScriptedRng([20, 10, 1]))
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        out = self.ok("encounter", "flee", "--who", "fixture-goblin-2")
        self.assertTrue(out["fled"])
        self.assertEqual(self.ok("encounter", "next")["turn"]["id"], "thorn")
        self.assertEqual(self.ok("encounter", "next")["turn"]["id"], "kira")
        self.assertEqual(self.ok("encounter", "end")["xp_awarded"], 50)

    def test_flee_is_for_monsters_in_the_fight(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", "--average-hp", rng=ScriptedRng([20, 10, 1]))
        self.refused("unknown_id", "encounter", "flee", "--who", "kira")

    def test_item_add_returns_the_one_line_and_not_the_whole_pack(self):
        out = self.ok("item", "add", "--who", "kira", "--item", "fixture-torch")
        self.assertEqual(out["item"], {"item": "fixture-torch", "quantity": 4})
        self.assertNotIn("inventory", out)

    def test_track_keeps_a_named_counter_and_status_shows_it(self):
        self.ok("track", "--name", "day", "--set", "1")
        self.assertEqual(self.ok("track", "--name", "day", "--add", "2")["value"], 3)
        self.assertEqual(self.ok("status")["trackers"], {"day": 3})

    def test_track_refuses_to_spend_a_use_that_is_not_there(self):
        self.ok("track", "--name", "kira second wind", "--set", "1")
        self.ok("track", "--name", "kira second wind", "--add", "-1")
        before = self.snapshot()
        out = self.refused("tracker_empty", "track", "--name", "kira second wind", "--add", "-1")
        self.assertIn("kira-second-wind", out["error"]["message"])
        self.assertEqual(before, self.snapshot())

    def test_track_needs_set_or_add_and_can_be_cleared(self):
        self.refused("bad_arguments", "track", "--name", "day")
        self.ok("track", "--name", "day", "--set", "4")
        self.ok("track", "--name", "day", "--clear")
        self.assertEqual(self.ok("status")["trackers"], {})


class TestDeathRunFindings(PlayCase):
    """Defects found by the death-run playtest (2026-09-18)."""

    def test_encounter_start_shows_the_natural_initiative_die_of_everyone(self):
        out = self.ok("encounter", "start", "--monster", "fixture-goblin:1", "--average-hp", rng=ScriptedRng([20, 10, 1]))
        naturals = {c["id"]: c["natural"] for c in out["initiative_order"]}
        self.assertEqual(naturals, {"kira": 20, "thorn": 10, "fixture-goblin-1": 1})

    def test_the_stabilising_death_save_reports_the_third_success(self):
        self.drop("kira")
        for _ in range(2):
            self.ok("deathsave", "--who", "kira", rng=ScriptedRng([15]))
        out = self.ok("deathsave", "--who", "kira", rng=ScriptedRng([15]))
        self.assertEqual((out["life_state"], out["successes"]), ("stable", 3))

    def test_the_fatal_death_save_reports_the_third_failure(self):
        self.drop("thorn")
        for _ in range(2):
            self.ok("deathsave", "--who", "thorn", rng=ScriptedRng([5]))
        out = self.ok("deathsave", "--who", "thorn", rng=ScriptedRng([5]))
        self.assertEqual((out["life_state"], out["failures"]), ("dead", 3))

    def test_status_shows_whether_the_hero_still_has_the_grit_save(self):
        self.assertTrue(self.ok("status")["characters"]["kira"]["grit_available"])
        self.assertNotIn("grit_available", self.ok("status")["characters"]["thorn"])
        self.patch("kira", grit_used_since_long_rest=True)
        self.assertFalse(self.ok("status")["characters"]["kira"]["grit_available"])

    def test_a_party_with_nobody_standing_earns_no_xp(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:2", "--average-hp", rng=ScriptedRng([20, 10, 1]))
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.drop("kira")
        self.drop("thorn")
        out = self.ok("encounter", "end")
        self.assertEqual((out["xp_awarded"], out["party_defeated"]), (0, True))
        self.assertEqual(self.char("kira")["xp"], 0)

    def test_a_party_with_one_member_standing_still_earns_xp(self):
        self.ok("encounter", "start", "--monster", "fixture-goblin:1", "--average-hp", rng=ScriptedRng([20, 10, 1]))
        self.ok("damage", "--who", "fixture-goblin-1", "--amount", "99")
        self.drop("thorn")
        out = self.ok("encounter", "end")
        self.assertEqual((out["xp_awarded"], out["party_defeated"]), (50, False))
