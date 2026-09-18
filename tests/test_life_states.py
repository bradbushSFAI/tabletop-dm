"""PRD section 11, row by row. Pure functions: a character dict in, a changed dict out."""
from tests.base import unittest

from dmlib import life_states as ls


def ch(state="alive", hp=20, hp_max=20, successes=0, failures=0, grit_used=False):
    return {"id": "kira", "hp": {"current": hp, "max": hp_max, "temp": 0}, "life_state": state,
            "death_saves": {"successes": successes, "failures": failures},
            "grit_used_since_long_rest": grit_used, "conditions": []}


class TestLifeStatesDamage(unittest.TestCase):
    def test_damage_above_zero_stays_alive(self):
        c = ls.apply_damage(ch(), 5, False, True)
        self.assertEqual((c["hp"]["current"], c["life_state"]), (15, "alive"))

    def test_damage_to_zero_makes_a_character_dying_with_clean_counters(self):
        for is_hero in (True, False):
            c = ls.apply_damage(ch(hp=5, successes=1), 9, False, is_hero)
            self.assertEqual((c["hp"]["current"], c["life_state"]), (0, "dying"))
            self.assertEqual(c["death_saves"], {"successes": 0, "failures": 0})
            self.assertIn("unconscious", c["conditions"])

    def test_temporary_hp_absorbs_damage_first(self):
        c = ch()
        c["hp"]["temp"] = 5
        c = ls.apply_damage(c, 8, False, True)
        self.assertEqual((c["hp"]["temp"], c["hp"]["current"]), (0, 17))

    def test_massive_damage_from_alive_makes_the_hero_fallen(self):
        c = ls.apply_damage(ch(hp=5, hp_max=20), 25, False, True)
        self.assertEqual(c["life_state"], "fallen")

    def test_massive_damage_is_overkill_of_at_least_max_hp_and_no_less(self):
        self.assertEqual(ls.apply_damage(ch(hp=5, hp_max=20), 24, False, True)["life_state"], "dying")

    def test_massive_damage_from_alive_kills_a_companion(self):
        self.assertEqual(ls.apply_damage(ch(hp=5, hp_max=20), 25, False, False)["life_state"], "dead")

    def test_damage_while_dying_adds_one_failure(self):
        c = ls.apply_damage(ch("dying", hp=0), 3, False, True)
        self.assertEqual((c["life_state"], c["death_saves"]["failures"]), ("dying", 1))

    def test_critical_damage_while_dying_adds_two_failures(self):
        self.assertEqual(ls.apply_damage(ch("dying", hp=0), 3, True, True)["death_saves"]["failures"], 2)

    def test_third_failure_from_damage_makes_the_hero_fallen(self):
        self.assertEqual(ls.apply_damage(ch("dying", hp=0, failures=2), 3, False, True)["life_state"], "fallen")

    def test_third_failure_from_damage_kills_a_companion(self):
        self.assertEqual(ls.apply_damage(ch("dying", hp=0, failures=2), 3, False, False)["life_state"], "dead")

    def test_massive_damage_while_dying(self):
        self.assertEqual(ls.apply_damage(ch("dying", hp=0, hp_max=20), 20, False, True)["life_state"], "fallen")
        self.assertEqual(ls.apply_damage(ch("dying", hp=0, hp_max=20), 20, False, False)["life_state"], "dead")

    def test_damage_to_a_stable_character_makes_it_dying_again(self):
        c = ls.apply_damage(ch("stable", hp=0), 2, False, True)
        self.assertEqual((c["life_state"], c["death_saves"]), ("dying", {"successes": 0, "failures": 1}))

    def test_massive_damage_while_stable(self):
        self.assertEqual(ls.apply_damage(ch("stable", hp=0, hp_max=20), 20, False, True)["life_state"], "fallen")

    def test_damage_to_fallen_dead_or_departed_is_refused(self):
        from dmlib.errors import DmError

        for state in ("fallen", "dead", "departed"):
            with self.subTest(state=state), self.assertRaises(DmError) as ctx:
                ls.apply_damage(ch(state, hp=0), 3, False, True)
            self.assertEqual(ctx.exception.code, "not_eligible_for_damage")

    def test_the_input_dict_is_not_mutated(self):
        original = ch(hp=5)
        ls.apply_damage(original, 9, False, True)
        self.assertEqual(original["life_state"], "alive")


class TestLifeStatesHeal(unittest.TestCase):
    def test_heal_is_capped_at_max_hp(self):
        self.assertEqual(ls.apply_heal(ch(hp=18), 10)["hp"]["current"], 20)

    def test_any_heal_brings_a_dying_character_back(self):
        c = ls.apply_heal(ch("dying", hp=0, successes=1, failures=2), 1)
        self.assertEqual((c["life_state"], c["hp"]["current"]), ("alive", 1))
        self.assertEqual(c["death_saves"], {"successes": 0, "failures": 0})
        self.assertNotIn("unconscious", c["conditions"])

    def test_heal_brings_a_stable_character_back(self):
        self.assertEqual(ls.apply_heal(ch("stable", hp=0), 4)["life_state"], "alive")

    def test_heal_on_fallen_dead_or_departed_is_refused(self):
        from dmlib.errors import DmError

        for state in ("fallen", "dead", "departed"):
            with self.subTest(state=state), self.assertRaises(DmError) as ctx:
                ls.apply_heal(ch(state, hp=0), 5)
            self.assertEqual(ctx.exception.code, "not_eligible_for_heal")


class TestLifeStatesDeathSave(unittest.TestCase):
    def test_ten_or_more_is_a_success(self):
        c, result = ls.apply_death_save(ch("dying", hp=0), 10, True)
        self.assertEqual((result, c["death_saves"]["successes"]), ("success", 1))

    def test_nine_or_less_is_a_failure(self):
        c, result = ls.apply_death_save(ch("dying", hp=0), 9, True)
        self.assertEqual((result, c["death_saves"]["failures"]), ("failure", 1))

    def test_third_success_makes_the_character_stable(self):
        c, _ = ls.apply_death_save(ch("dying", hp=0, successes=2), 15, True)
        self.assertEqual((c["life_state"], c["death_saves"]), ("stable", {"successes": 0, "failures": 0}))

    def test_natural_one_is_two_failures(self):
        c, result = ls.apply_death_save(ch("dying", hp=0), 1, True)
        self.assertEqual((result, c["death_saves"]["failures"]), ("critical_failure", 2))

    def test_natural_twenty_gives_one_hp_and_alive(self):
        c, result = ls.apply_death_save(ch("dying", hp=0, failures=2), 20, True)
        self.assertEqual((result, c["life_state"], c["hp"]["current"]), ("critical_success", "alive", 1))

    def test_third_failure_makes_the_hero_fallen(self):
        self.assertEqual(ls.apply_death_save(ch("dying", hp=0, failures=2), 4, True)[0]["life_state"], "fallen")

    def test_third_failure_kills_a_companion(self):
        self.assertEqual(ls.apply_death_save(ch("dying", hp=0, failures=2), 4, False)[0]["life_state"], "dead")

    def test_natural_one_at_two_failures_does_not_overflow(self):
        c, _ = ls.apply_death_save(ch("dying", hp=0, failures=2), 1, True)
        self.assertEqual((c["life_state"], c["death_saves"]["failures"]), ("fallen", 3))


class TestLifeStatesGrit(unittest.TestCase):
    def fallen(self, **kw):
        return ch("fallen", hp=0, failures=3, **kw)

    def test_success_is_a_light_cost_in_every_difficulty(self):
        for difficulty in ("story", "standard", "iron"):
            c, outcome = ls.apply_grit(self.fallen(), 12, 10, difficulty)
            self.assertEqual((outcome, c["life_state"], c["hp"]["current"]), ("light_cost", "stable", 0), difficulty)

    def test_meeting_the_dc_is_a_success(self):
        self.assertEqual(ls.apply_grit(self.fallen(), 10, 10, "iron")[1], "light_cost")

    def test_failure_outcome_depends_on_difficulty(self):
        want = {"story": ("light_cost", "stable"), "standard": ("heavy_cost", "stable"), "iron": ("dead", "dead")}
        for difficulty, (outcome, state) in want.items():
            c, got = ls.apply_grit(self.fallen(), 9, 10, difficulty)
            self.assertEqual((got, c["life_state"]), (outcome, state), difficulty)

    def test_grit_already_used_is_an_automatic_failure_with_no_roll(self):
        want = {"story": "light_cost", "standard": "heavy_cost", "iron": "dead"}
        for difficulty, outcome in want.items():
            self.assertEqual(ls.apply_grit(self.fallen(grit_used=True), None, 10, difficulty)[1], outcome)

    def test_any_roll_uses_the_grit_save_up(self):
        self.assertTrue(ls.apply_grit(self.fallen(), 15, 10, "standard")[0]["grit_used_since_long_rest"])
        self.assertTrue(ls.apply_grit(self.fallen(), 2, 10, "standard")[0]["grit_used_since_long_rest"])

    def test_surviving_clears_the_death_save_counters(self):
        self.assertEqual(ls.apply_grit(self.fallen(), 15, 10, "standard")[0]["death_saves"], {"successes": 0, "failures": 0})

    def test_a_roll_is_required_when_grit_is_available(self):
        with self.assertRaises(ValueError):
            ls.apply_grit(self.fallen(), None, 10, "standard")


class TestLifeStatesRest(unittest.TestCase):
    def test_rest_that_restores_hp_wakes_a_stable_character(self):
        self.assertEqual(ls.apply_hp_gain_from_rest(ch("stable", hp=0), 3)["life_state"], "alive")

    def test_rest_that_restores_nothing_leaves_a_stable_character_stable(self):
        self.assertEqual(ls.apply_hp_gain_from_rest(ch("stable", hp=0), 0)["life_state"], "stable")
