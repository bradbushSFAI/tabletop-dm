import copy

from tests.base import FIXTURE_SKILL_ROOT, unittest

from dmlib import data, derive, rules_tables

DATA = data.load_all(FIXTURE_SKILL_ROOT)


def sheet(**over):
    """A bare level-1 fixture fighter with the inputs derive needs."""
    base = {
        "class": "fighter", "level": 1,
        "abilities": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skill_proficiencies": ["athletics"], "expertise": [], "fighting_style": None,
        "equipped": {"armor": None, "shield": None, "weapons": []},
        "hit_dice": {"die": "d10", "max": 1, "remaining": 1},
        "spellcasting": None,
    }
    base.update(over)
    return derive.recompute_all(copy.deepcopy(base), DATA["classes"], DATA["equipment"])


class TestRulesTables(unittest.TestCase):
    def test_there_are_eighteen_skills_each_tied_to_an_ability(self):
        self.assertEqual(len(rules_tables.SKILLS), 18)
        self.assertTrue(all(a in rules_tables.ABILITIES for a in rules_tables.SKILLS.values()))

    def test_xp_thresholds_are_the_5e_values_for_levels_1_to_5(self):
        self.assertEqual(rules_tables.XP_THRESHOLDS, {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500})

    def test_cr_to_xp_covers_cr_0_to_5(self):
        self.assertEqual(rules_tables.xp_for_cr(0.25), 50)
        self.assertEqual(rules_tables.xp_for_cr(5), 1800)

    def test_there_are_the_srd_conditions(self):
        self.assertIn("poisoned", rules_tables.LEGAL_CONDITIONS)
        self.assertIn("exhaustion", rules_tables.LEGAL_CONDITIONS)


class TestDeriveAbilityAndProficiency(unittest.TestCase):
    def test_ability_modifier_rounds_down(self):
        pairs = {1: -5, 8: -1, 9: -1, 10: 0, 11: 0, 15: 2, 16: 3, 20: 5}
        for score, mod in pairs.items():
            with self.subTest(score=score):
                self.assertEqual(derive.ability_modifier(score), mod)

    def test_proficiency_bonus_comes_from_the_class_level_row(self):
        self.assertEqual(sheet(level=4)["proficiency_bonus"], 2)
        self.assertEqual(sheet(level=5)["proficiency_bonus"], 3)


class TestDeriveSavesAndSkills(unittest.TestCase):
    def test_class_saves_add_proficiency(self):
        saves = sheet()["saves"]
        self.assertEqual(saves["str"], {"proficient": True, "bonus": 5})
        self.assertEqual(saves["dex"], {"proficient": False, "bonus": 2})

    def test_all_eighteen_skills_are_on_the_sheet(self):
        self.assertEqual(len(sheet()["skills"]), 18)

    def test_proficient_skill_adds_proficiency_and_expertise_doubles_it(self):
        skills = sheet(skill_proficiencies=["athletics", "stealth"], expertise=["stealth"])["skills"]
        self.assertEqual(skills["athletics"]["bonus"], 5)
        self.assertEqual(skills["stealth"]["bonus"], 6)
        self.assertEqual(skills["arcana"]["bonus"], 0)

    def test_passive_perception_is_ten_plus_the_skill(self):
        self.assertEqual(sheet(skill_proficiencies=["perception"])["passive_perception"], 13)


class TestDeriveAC(unittest.TestCase):
    def test_no_armor_is_ten_plus_dex(self):
        self.assertEqual(sheet()["ac"], 12)

    def test_heavy_armor_ignores_dex(self):
        self.assertEqual(sheet(equipped={"armor": "fixture-mail", "shield": None, "weapons": []})["ac"], 16)

    def test_medium_armor_caps_dex_at_two(self):
        s = sheet(abilities={"str": 10, "dex": 18, "con": 10, "int": 10, "wis": 10, "cha": 10},
                  equipped={"armor": "fixture-hide", "shield": None, "weapons": []})
        self.assertEqual(s["ac"], 14)

    def test_light_armor_adds_full_dex(self):
        s = sheet(abilities={"str": 10, "dex": 18, "con": 10, "int": 10, "wis": 10, "cha": 10},
                  equipped={"armor": "fixture-leather", "shield": None, "weapons": []})
        self.assertEqual(s["ac"], 15)

    def test_shield_adds_two(self):
        self.assertEqual(sheet(equipped={"armor": "fixture-mail", "shield": "fixture-shield", "weapons": []})["ac"], 18)

    def test_defense_style_adds_one_only_when_armor_is_worn(self):
        self.assertEqual(sheet(fighting_style="defense", equipped={"armor": "fixture-mail", "shield": None, "weapons": []})["ac"], 17)
        self.assertEqual(sheet(fighting_style="defense")["ac"], 12)


class TestDeriveAttacks(unittest.TestCase):
    def equip(self, weapons, **over):
        eq = {"armor": None, "shield": None, "weapons": weapons}
        eq.update(over.pop("equipped_extra", {}))
        return sheet(equipped=eq, **over)["attacks"]

    def test_melee_weapon_uses_strength_and_proficiency(self):
        atk = self.equip(["fixture-sword"])["fixture-sword"]
        self.assertEqual(atk["attack_bonus"], 5)
        self.assertEqual(atk["damage_expr"], "1d8+3")
        self.assertEqual(atk["ability"], "str")

    def test_ranged_weapon_uses_dexterity(self):
        atk = self.equip(["fixture-bow"])["fixture-bow"]
        self.assertEqual(atk["ability"], "dex")
        self.assertEqual(atk["attack_bonus"], 4)
        self.assertEqual(atk["damage_expr"], "1d6+2")

    def test_finesse_weapon_uses_the_higher_of_str_and_dex(self):
        dexy = {"str": 8, "dex": 16, "con": 10, "int": 10, "wis": 10, "cha": 10}
        atk = self.equip(["fixture-dagger"], abilities=dexy)["fixture-dagger"]
        self.assertEqual(atk["ability"], "dex")
        self.assertEqual(atk["damage_expr"], "1d4+3")

    def test_not_proficient_gets_no_proficiency_bonus(self):
        atk = self.equip(["fixture-sword"], **{"class": "wizard"})["fixture-sword"]
        self.assertFalse(atk["proficient"])
        self.assertEqual(atk["attack_bonus"], 3)

    def test_negative_and_zero_modifiers_format_cleanly(self):
        weak = {"str": 8, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        self.assertEqual(self.equip(["fixture-sword"], abilities=weak)["fixture-sword"]["damage_expr"], "1d8-1")
        flat = dict(weak, str=10)
        self.assertEqual(self.equip(["fixture-sword"], abilities=flat)["fixture-sword"]["damage_expr"], "1d8")

    def test_archery_style_adds_two_to_ranged_attacks_only(self):
        atks = self.equip(["fixture-bow", "fixture-dagger"], fighting_style="archery")
        self.assertEqual(atks["fixture-bow"]["attack_bonus"], 6)
        self.assertEqual(atks["fixture-dagger"]["attack_bonus"], 5)

    def test_dueling_style_adds_two_damage_to_a_lone_one_handed_melee_weapon(self):
        self.assertEqual(self.equip(["fixture-sword"], fighting_style="dueling")["fixture-sword"]["damage_expr"], "1d8+5")
        two = self.equip(["fixture-sword", "fixture-dagger"], fighting_style="dueling")
        self.assertEqual(two["fixture-sword"]["damage_expr"], "1d8+3")

    def test_versatile_weapon_reports_two_handed_damage_when_no_shield(self):
        self.assertEqual(self.equip(["fixture-sword"])["fixture-sword"]["versatile_damage_expr"], "1d10+3")
        shielded = sheet(equipped={"armor": None, "shield": "fixture-shield", "weapons": ["fixture-sword"]})
        self.assertNotIn("versatile_damage_expr", shielded["attacks"]["fixture-sword"])

    def test_unarmed_strike_is_always_available(self):
        self.assertEqual(self.equip([])["unarmed"]["damage_expr"], "4")


class TestDeriveSpellcasting(unittest.TestCase):
    def wizard(self, level, used=None):
        casting = {"cantrips": ["fixture-spark"], "known": ["fixture-bolt"], "prepared": ["fixture-bolt"],
                   "slots": used or {}}
        smart = {"str": 8, "dex": 14, "con": 13, "int": 16, "wis": 12, "cha": 10}
        return sheet(**{"class": "wizard", "level": level, "abilities": smart, "spellcasting": casting})["spellcasting"]

    def test_non_casters_have_null_spellcasting(self):
        self.assertIsNone(sheet()["spellcasting"])

    def test_save_dc_and_attack_bonus(self):
        casting = self.wizard(1)
        self.assertEqual(casting["save_dc"], 13)
        self.assertEqual(casting["attack_bonus"], 5)
        self.assertEqual(casting["ability"], "int")

    def test_slots_come_from_the_class_level_row(self):
        self.assertEqual(self.wizard(3)["slots"], {"1": {"max": 4, "used": 0}, "2": {"max": 2, "used": 0}})

    def test_used_slots_survive_a_recompute_and_are_clamped(self):
        slots = self.wizard(1, used={"1": {"max": 2, "used": 9}})["slots"]
        self.assertEqual(slots, {"1": {"max": 2, "used": 2}})

    def test_prepare_limit_is_ability_modifier_plus_level_minimum_one(self):
        self.assertEqual(self.wizard(3)["prepare_limit"], 6)

    def test_max_spell_level_follows_the_slots(self):
        self.assertEqual(self.wizard(5)["max_spell_level"], 3)
