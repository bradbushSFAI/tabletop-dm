"""Integrity tests for the REAL rules data that ships in the skill."""
import json
import re

from tests.base import REAL_SKILL_ROOT, unittest

from dmlib import data, dice
from dmlib.rules_tables import ABILITIES, CR_TO_XP, SKILLS
from tests.base import ScriptedRng

DICE = re.compile(r"^\d+d\d+([+-]\d+)?$")

# SRD 5.1 names Wizards product identity that the CC-BY licence does NOT cover,
# plus published setting names. Owlbear, drow and tarrasque ARE in the SRD.
BANNED = ["beholder", "gauth", "carrion crawler", "displacer beast", "githyanki", "githzerai", "kuo-toa",
          "mind flayer", "illithid", "slaad", "umber hulk", "yuan-ti", "tanar'ri", "baatezu",
          "forgotten realms", "faerun", "greyhawk", "eberron", "ravenloft", "dragonlance",
          "dungeons & dragons", "dungeons and dragons", "tasha", "mordenkainen", "bigby", "melf", "tenser",
          "leomund", "otiluke", "evard", "drawmij", "nystul", "rary", "otto"]


def load():
    return data.load_all(REAL_SKILL_ROOT)


class TestClassesDataCompleteness(unittest.TestCase):
    def setUp(self):
        self.records = load()
        self.classes = self.records["classes"]

    def test_the_four_classes_are_present(self):
        self.assertEqual(sorted(self.classes), ["cleric", "fighter", "rogue", "wizard"])

    def test_every_class_has_levels_one_to_five_with_every_field(self):
        for cid, c in self.classes.items():
            self.assertEqual(sorted(c["levels"]), ["1", "2", "3", "4", "5"], cid)
            for lvl, row in c["levels"].items():
                with self.subTest(cls=cid, level=lvl):
                    self.assertEqual(row["proficiency_bonus"], 3 if lvl == "5" else 2)
                    for feature in row["features"]:
                        self.assertEqual(sorted(feature), ["id", "name", "rule"])
                        self.assertGreater(len(feature["rule"]), 15)

    def test_level_four_grants_an_ability_score_improvement(self):
        for cid, c in self.classes.items():
            ids = [f["id"] for f in c["levels"]["4"]["features"]]
            self.assertIn("ability-score-improvement", ids, cid)

    def test_full_caster_slots_match_the_srd_table(self):
        want = {"1": {"1": 2}, "2": {"1": 3}, "3": {"1": 4, "2": 2}, "4": {"1": 4, "2": 3}, "5": {"1": 4, "2": 3, "3": 2}}
        for cid in ["wizard", "cleric"]:
            for lvl, slots in want.items():
                self.assertEqual(self.classes[cid]["levels"][lvl]["slots"], slots, "%s %s" % (cid, lvl))
        for cid in ["fighter", "rogue"]:
            self.assertTrue(all(row["slots"] is None for row in self.classes[cid]["levels"].values()))

    def test_hit_dice_and_saves_match_the_srd(self):
        want = {"fighter": ("d10", ["con", "str"]), "rogue": ("d8", ["dex", "int"]),
                "wizard": ("d6", ["int", "wis"]), "cleric": ("d8", ["cha", "wis"])}
        for cid, (die, saves) in want.items():
            self.assertEqual(self.classes[cid]["hit_die"], die)
            self.assertEqual(sorted(self.classes[cid]["saving_throw_proficiencies"]), saves)

    def test_skill_lists_are_legal_and_defaults_fit(self):
        for cid, c in self.classes.items():
            with self.subTest(cls=cid):
                options = c["skill_choices"]["options"]
                self.assertTrue(all(s in SKILLS for s in options))
                self.assertEqual(len(c["default_skills"]), c["skill_choices"]["count"])
                self.assertTrue(all(s in options for s in c["default_skills"]))
                self.assertEqual(len(c["default_background_skills"]), 2)
                self.assertFalse(set(c["default_background_skills"]) & set(c["default_skills"]))
                self.assertEqual(sorted(c["quick_scores"].values()), [8, 10, 12, 13, 14, 15])
                self.assertEqual(sorted(c["quick_scores"]), sorted(ABILITIES))

    def test_every_equipment_and_spell_reference_resolves(self):
        eq, spells = self.records["equipment"], self.records["spells"]
        for cid, c in self.classes.items():
            with self.subTest(cls=cid):
                owned = [line["item"] for line in c["starting_equipment"]]
                self.assertTrue(all(item in eq for item in owned))
                worn = c["starting_equipped"]
                for item in [worn["armor"], worn["shield"]] + worn["weapons"]:
                    if item:
                        self.assertIn(item, owned)
                rules = c["spellcasting"]
                if rules:
                    for sid in rules["default_cantrips"]:
                        self.assertEqual(spells[sid]["level"], 0)
                        self.assertIn(cid, spells[sid]["classes"])
                    for sid in rules["default_spells"]:
                        self.assertEqual(spells[sid]["level"], 1)
                        self.assertIn(cid, spells[sid]["classes"])

    def test_a_quick_character_of_every_class_can_be_built_at_every_level(self):
        """The strongest check: the real data works through the real create command."""
        import tempfile
        from pathlib import Path

        from dmlib import cli
        import contextlib
        import io

        for cid in self.classes:
            for level in range(1, 6):
                with self.subTest(cls=cid, level=level), tempfile.TemporaryDirectory() as tmp:
                    camp = Path(tmp) / "c"
                    camp.mkdir()
                    for argv in (["init"], ["character", "create", "--name", "T", "--class", cid, "--quick",
                                            "--level", str(level)]):
                        buf = io.StringIO()
                        with contextlib.redirect_stdout(buf):
                            code = cli.run(argv + ["--campaign", str(camp)], REAL_SKILL_ROOT, ScriptedRng([]))
                        out = json.loads(buf.getvalue())
                        self.assertEqual(code, 0, out)
                    ch = out["character"]
                    self.assertGreater(ch["ac"], 9)
                    self.assertGreater(len(ch["attacks"]), 1)
                    if ch["spellcasting"]:
                        self.assertEqual(len(ch["spellcasting"]["cantrips"]), ch["spellcasting"]["cantrips_known_limit"])
                        self.assertTrue(ch["spellcasting"]["prepared"])


class TestSpellsDataLegality(unittest.TestCase):
    def test_every_spell_is_legal(self):
        spells = load()["spells"]
        self.assertTrue(40 <= len(spells) <= 46, len(spells))
        for sid, s in spells.items():
            with self.subTest(spell=sid):
                self.assertIn(s["level"], (0, 1, 2, 3))
                self.assertTrue(s["classes"] and set(s["classes"]) <= {"wizard", "cleric"})
                self.assertTrue(s["attack_or_save"] is None or s["attack_or_save"] == "spell_attack"
                                or re.match(r"^save:(str|dex|con|int|wis|cha)$", s["attack_or_save"]))
                if s["damage_expr"] is not None:
                    self.assertRegex(s["damage_expr"], DICE)
                    self.assertTrue(s["damage_type"])
                self.assertIsInstance(s["concentration"], bool)
                self.assertIsInstance(s["ritual"], bool)
                self.assertLess(len(s["description"].split()), 30)

    def test_each_caster_has_spells_at_every_level_it_can_cast(self):
        spells = load()["spells"]
        for cid in ["wizard", "cleric"]:
            for level in (0, 1, 2, 3):
                count = len([s for s in spells.values() if cid in s["classes"] and s["level"] == level])
                self.assertGreaterEqual(count, 3, "%s level %d" % (cid, level))

    def test_known_srd_numbers(self):
        spells = load()["spells"]
        self.assertEqual(spells["fireball"]["damage_expr"], "8d6")
        self.assertEqual(spells["fireball"]["attack_or_save"], "save:dex")
        self.assertEqual(spells["magic-missile"]["damage_expr"], "1d4+1")
        self.assertEqual(spells["cure-wounds"]["damage_expr"], "1d8")
        self.assertEqual(spells["fire-bolt"]["damage_expr"], "1d10")
        self.assertEqual(spells["guiding-bolt"]["damage_expr"], "4d6")


class TestMonstersDataCompleteness(unittest.TestCase):
    def test_every_monster_is_complete_and_legal(self):
        monsters = load()["monsters"]
        self.assertTrue(40 <= len(monsters) <= 46, len(monsters))
        for mid, m in monsters.items():
            with self.subTest(monster=mid):
                self.assertIn(m["challenge_rating"], CR_TO_XP)
                self.assertLessEqual(m["challenge_rating"], 5)
                self.assertEqual(m["xp_value"], CR_TO_XP[m["challenge_rating"]])
                self.assertTrue(5 <= m["ac"] <= 22)
                self.assertRegex(m["hp_expr"], DICE)
                self.assertEqual(sorted(m["abilities"]), sorted(ABILITIES))
                self.assertTrue(m["attacks"])
                for attack in m["attacks"]:
                    self.assertTrue(attack["attack_bonus"] is None or isinstance(attack["attack_bonus"], int))
                    if attack["attack_bonus"] is None:
                        self.assertTrue(attack.get("save"))
                    if attack.get("damage_expr"):
                        self.assertRegex(attack["damage_expr"], DICE)
                self.assertTrue(m["tactic"])
                self.assertIsInstance(m["traits"], list)

    def test_hp_average_agrees_with_the_hit_dice(self):
        for mid, m in load()["monsters"].items():
            with self.subTest(monster=mid):
                count, rest = m["hp_expr"].split("d")
                match = re.match(r"^(\d+)([+-]\d+)?$", rest)
                sides, bonus = int(match.group(1)), int(match.group(2) or 0)
                expected = int(int(count) * (sides + 1) / 2.0 + bonus)
                self.assertEqual(m["hp_average"], expected)

    def test_every_challenge_rating_band_has_monsters(self):
        ratings = [m["challenge_rating"] for m in load()["monsters"].values()]
        for cr in (0, 0.125, 0.25, 0.5, 1, 2, 3, 4, 5):
            self.assertGreaterEqual(ratings.count(cr), 2, "CR %s" % cr)

    def test_known_srd_numbers(self):
        m = load()["monsters"]
        self.assertEqual((m["goblin"]["ac"], m["goblin"]["hp_expr"], m["goblin"]["challenge_rating"]), (15, "2d6", 0.25))
        self.assertEqual((m["ogre"]["ac"], m["ogre"]["hp_expr"], m["ogre"]["challenge_rating"]), (11, "7d10+21", 2))
        self.assertEqual((m["troll"]["ac"], m["troll"]["hp_expr"], m["troll"]["challenge_rating"]), (15, "8d10+40", 5))
        self.assertEqual((m["skeleton"]["ac"], m["skeleton"]["hp_expr"]), (13, "2d8+4"))


class TestEquipmentDataLegality(unittest.TestCase):
    def test_every_item_is_legal(self):
        for iid, item in load()["equipment"].items():
            with self.subTest(item=iid):
                self.assertIn(item["category"], ("weapon", "armor", "gear"))
                self.assertIsInstance(item["cost_cp"], int)
                self.assertGreaterEqual(item["cost_cp"], 0)
                if item["category"] == "weapon":
                    self.assertRegex(item["damage_expr"], r"^(\d+d\d+|\d+)$")
                    self.assertIn(item["weapon_class"], ("simple-melee", "simple-ranged", "martial-melee", "martial-ranged"))
                    ranged = item["weapon_class"].endswith("ranged")
                    self.assertEqual("ranged" in item["properties"], ranged)
                    self.assertEqual("versatile" in item["properties"], "versatile_damage_expr" in item)
                if item["category"] == "armor":
                    self.assertIn(item["armor_type"], ("light", "medium", "heavy", "shield"))
                    if item["armor_type"] == "shield":
                        self.assertEqual(item["ac_bonus"], 2)
                    else:
                        want_cap = {"light": None, "medium": 2, "heavy": 0}[item["armor_type"]]
                        self.assertEqual(item["dex_bonus_max"], want_cap)

    def test_known_srd_numbers(self):
        eq = load()["equipment"]
        self.assertEqual((eq["longsword"]["damage_expr"], eq["longsword"]["versatile_damage_expr"], eq["longsword"]["cost_cp"]),
                         ("1d8", "1d10", 1500))
        self.assertEqual((eq["chain-mail"]["armor_class_base"], eq["chain-mail"]["cost_cp"]), (16, 7500))
        self.assertEqual(eq["leather-armor"]["armor_class_base"], 11)
        self.assertIn("finesse", eq["rapier"]["properties"])
        self.assertEqual(eq["torch"]["cost_cp"], 1)

    def test_weapon_damage_strings_roll(self):
        for iid, item in load()["equipment"].items():
            if item["category"] == "weapon":
                dice.roll_expression(item["damage_expr"], ScriptedRng([1] * 10))


class TestNoProductIdentityNames(unittest.TestCase):
    def test_no_banned_term_appears_in_any_data_file(self):
        hits = []
        for path in sorted((REAL_SKILL_ROOT / "data").glob("*.json")):
            text = path.read_text().lower()
            for term in BANNED:
                if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text):
                    hits.append("%s: %s" % (path.name, term))
        self.assertEqual(hits, [])

    def test_the_srd_attribution_ships_with_the_skill(self):
        text = (REAL_SKILL_ROOT / "LICENSE-SRD.md").read_text()
        self.assertIn("System Reference Document 5.1", text)
        self.assertIn("Creative Commons Attribution 4.0", text)


class TestRealWeaponsDerive(unittest.TestCase):
    def test_a_net_deals_no_damage_even_with_a_high_modifier(self):
        """derive adds the ability modifier to weapon damage. A net has none to add to."""
        import copy

        from dmlib import derive

        records = load()
        sheet = {"class": "fighter", "level": 1,
                 "abilities": {"str": 16, "dex": 16, "con": 10, "int": 10, "wis": 10, "cha": 10},
                 "skill_proficiencies": [], "expertise": [], "fighting_style": "dueling",
                 "equipped": {"armor": None, "shield": None, "weapons": ["net"]},
                 "hit_dice": {"die": "d10", "max": 1, "remaining": 1}, "spellcasting": None}
        out = derive.recompute_all(copy.deepcopy(sheet), records["classes"], records["equipment"])
        self.assertEqual(out["attacks"]["net"]["damage_expr"], "0")

    def test_every_real_weapon_gives_a_rollable_damage_string_on_a_sheet(self):
        import copy

        from dmlib import derive

        records = load()
        for wid, item in records["equipment"].items():
            if item["category"] != "weapon":
                continue
            sheet = {"class": "fighter", "level": 1,
                     "abilities": {"str": 7, "dex": 7, "con": 10, "int": 10, "wis": 10, "cha": 10},
                     "skill_proficiencies": [], "expertise": [], "fighting_style": None,
                     "equipped": {"armor": None, "shield": None, "weapons": [wid]},
                     "hit_dice": {"die": "d10", "max": 1, "remaining": 1}, "spellcasting": None}
            out = derive.recompute_all(copy.deepcopy(sheet), records["classes"], records["equipment"])
            with self.subTest(weapon=wid):
                dice.roll_expression(out["attacks"][wid]["damage_expr"], ScriptedRng([1] * 10))
