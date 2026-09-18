from tests.base import DmTestCase, ScriptedRng


class CharacterCase(DmTestCase):
    def setUp(self):
        super().setUp()
        self.init_campaign()

    def make_fighter(self, cid="kira", *extra):
        return self.ok("character", "create", "--id", cid, "--name", cid.title(), "--class", "fighter",
                       "--scores", "16,14,14,10,12,8", *extra)["character"]

    def make_wizard(self, cid="thorn", *extra):
        return self.ok("character", "create", "--id", cid, "--name", cid.title(), "--class", "wizard",
                       "--scores", "8,14,13,16,12,10", *extra)["character"]

    def char(self, cid):
        return self.party()["characters"][cid]


class TestCharacterCreate(CharacterCase):
    def test_first_character_becomes_the_hero(self):
        self.make_fighter()
        self.assertEqual(self.party()["hero_id"], "kira")

    def test_second_character_is_a_companion(self):
        self.make_fighter()
        self.make_wizard()
        self.assertEqual(self.party()["hero_id"], "kira")

    def test_level_one_hp_is_hit_die_maximum_plus_con(self):
        c = self.make_fighter()
        self.assertEqual(c["hp"], {"current": 12, "max": 12, "temp": 0})
        self.assertEqual(c["hit_dice"], {"die": "d10", "max": 1, "remaining": 1})

    def test_new_character_starts_alive_with_clean_counters(self):
        c = self.make_fighter()
        self.assertEqual(c["life_state"], "alive")
        self.assertEqual(c["death_saves"], {"successes": 0, "failures": 0})
        self.assertFalse(c["grit_used_since_long_rest"])
        self.assertEqual((c["xp"], c["level"], c["conditions"]), (0, 1, []))

    def test_starting_gear_gold_and_equipped_items_come_from_the_class(self):
        c = self.make_fighter()
        self.assertIn({"item": "fixture-torch", "quantity": 3}, c["inventory"])
        self.assertEqual(c["gold_cp"], 1000)
        self.assertEqual(c["equipped"]["armor"], "fixture-mail")
        self.assertEqual(c["ac"], 19)  # mail 16 + shield 2 + default defense style 1
        self.assertIn("fixture-sword", c["attacks"])

    def test_default_skills_are_class_defaults_plus_background_defaults(self):
        c = self.make_fighter()
        self.assertEqual(sorted(c["skill_proficiencies"]), ["athletics", "intimidation", "perception", "survival"])

    def test_chosen_skills_must_include_enough_class_skills(self):
        self.refused("illegal_skill_pick", "character", "create", "--id", "x", "--name", "X", "--class", "fighter",
                     "--scores", "16,14,14,10,12,8", "--skills", "arcana,history,stealth,athletics")

    def test_unknown_skill_is_refused(self):
        self.refused("illegal_skill_pick", "character", "create", "--id", "x", "--name", "X", "--class", "fighter",
                     "--scores", "16,14,14,10,12,8", "--skills", "athletics,perception,juggling,stealth")

    def test_rogue_gets_default_expertise(self):
        c = self.ok("character", "create", "--id", "vex", "--name", "Vex", "--class", "rogue", "--quick")["character"]
        self.assertTrue(c["skills"]["stealth"]["expertise"])
        self.assertEqual(c["skills"]["stealth"]["bonus"], 6)

    def test_features_of_level_one_are_on_the_sheet(self):
        self.assertEqual(self.make_fighter()["features"], ["fixture-wind"])

    def test_scores_must_be_six_numbers_from_3_to_18(self):
        for bad in ["16,14,14,10,12", "16,14,14,10,12,19", "16,14,14,10,12,2", "a,b,c,d,e,f"]:
            with self.subTest(scores=bad):
                self.refused("illegal_ability_scores", "character", "create", "--id", "x", "--name", "X",
                             "--class", "fighter", "--scores", bad)

    def test_standard_array_flag_requires_the_standard_array(self):
        self.refused("illegal_ability_scores", "character", "create", "--id", "x", "--name", "X", "--class", "fighter",
                     "--scores", "16,14,14,10,12,8", "--standard-array")
        self.ok("character", "create", "--id", "x", "--name", "X", "--class", "fighter",
                "--scores", "15,13,14,8,12,10", "--standard-array")

    def test_scores_or_quick_is_required(self):
        self.refused("illegal_ability_scores", "character", "create", "--id", "x", "--name", "X", "--class", "fighter")

    def test_quick_builds_a_ready_character_from_class_defaults(self):
        c = self.ok("character", "create", "--id", "q", "--name", "Q", "--class", "fighter", "--quick")["character"]
        self.assertEqual(c["abilities"]["str"], 15)

    def test_unknown_class_is_refused(self):
        self.refused("unknown_class", "character", "create", "--id", "x", "--name", "X", "--class", "bard", "--quick")

    def test_duplicate_id_is_refused(self):
        self.make_fighter()
        self.refused("id_taken", "character", "create", "--id", "kira", "--name", "K", "--class", "fighter", "--quick")

    def test_id_defaults_to_a_slug_of_the_name(self):
        out = self.ok("character", "create", "--name", "Kira Ashwood", "--class", "fighter", "--quick")
        self.assertEqual(out["character"]["id"], "kira-ashwood")

    def test_party_is_full_at_three_active_characters(self):
        for cid in ["a", "b", "c"]:
            self.make_fighter(cid)
        self.refused("party_full", "character", "create", "--id", "d", "--name", "D", "--class", "fighter", "--quick")

    def test_wizard_gets_default_cantrips_spellbook_and_prepared_list(self):
        c = self.make_wizard()
        casting = c["spellcasting"]
        self.assertEqual(casting["cantrips"], ["fixture-spark"])
        self.assertEqual(sorted(casting["known"]), ["fixture-bolt", "fixture-haze", "fixture-ward"])
        self.assertEqual(casting["slots"], {"1": {"max": 2, "used": 0}})
        self.assertLessEqual(len(casting["prepared"]), casting["prepare_limit"])

    def test_default_spellbook_skips_spells_above_the_castable_level(self):
        self.assertNotIn("fixture-beam", self.make_wizard()["spellcasting"]["known"])

    def test_illegal_spell_pick_is_refused(self):
        self.refused("illegal_spell_pick", "character", "create", "--id", "w", "--name", "W", "--class", "wizard",
                     "--quick", "--spells", "fixture-bolt,fixture-ward,fixture-mend")

    def test_level_three_companion_uses_average_hp_and_no_dice(self):
        c = self.ok("character", "create", "--id", "bron", "--name", "Bron", "--class", "fighter",
                    "--scores", "16,14,14,10,12,8", "--level", "3", rng=ScriptedRng([]))["character"]
        self.assertEqual(c["hp"]["max"], 12 + 8 + 8)
        self.assertEqual(c["xp"], 900)
        self.assertEqual(c["features"], ["fixture-wind", "fixture-surge"])

    def test_level_above_five_is_refused(self):
        self.refused("illegal_value", "character", "create", "--id", "x", "--name", "X", "--class", "fighter",
                     "--quick", "--level", "6")

    def test_creation_is_logged(self):
        self.make_fighter()
        self.assertEqual(self.log_lines()[-1]["payload"]["field"], "characters.kira")

    def test_refusal_changes_nothing_on_disk(self):
        before = self.snapshot()
        self.refused("unknown_class", "character", "create", "--id", "x", "--name", "X", "--class", "bard", "--quick")
        self.assertEqual(before, self.snapshot())


class TestSheetCommand(CharacterCase):
    def test_sheet_returns_the_full_character_with_feature_rules_and_gold_in_gp(self):
        self.make_fighter()
        out = self.ok("sheet", "kira")
        self.assertEqual(out["character"]["inventory"][0]["item"], "fixture-mail")
        self.assertEqual(out["character"]["gold_gp"], 10.0)
        self.assertEqual(out["character"]["feature_rules"][0]["rule"], "Placeholder rule.")
        self.assertTrue(out["is_hero"])

    def test_unknown_id_lists_the_known_ids(self):
        self.make_fighter()
        out = self.refused("unknown_id", "sheet", "grog")
        self.assertIn("kira", out["error"]["message"])

    def test_sheet_is_read_only(self):
        self.make_fighter()
        before = self.snapshot()
        self.ok("sheet", "kira")
        self.assertEqual(before, self.snapshot())


class TestEquipUnequip(CharacterCase):
    def test_unequip_armor_and_shield_lowers_ac(self):
        self.make_fighter()
        self.ok("unequip", "--who", "kira", "--slot", "shield")
        out = self.ok("unequip", "--who", "kira", "--slot", "armor")
        self.assertEqual(out["ac"], 12)
        self.assertEqual(self.char("kira")["ac"], 12)

    def test_equip_an_item_that_is_not_in_the_pack_is_refused(self):
        self.make_fighter()
        out = self.refused("item_not_in_inventory", "equip", "--who", "kira", "--slot", "weapon", "--item", "fixture-bow")
        self.assertIn("fixture-bow", out["error"]["message"])

    def test_not_proficient_is_reported_and_not_refused(self):
        self.make_wizard()
        party = self.party()
        party["characters"]["thorn"]["inventory"].append({"item": "fixture-mail", "quantity": 1})
        import json
        (self.campaign_dir / "party.json").write_text(json.dumps(party))
        out = self.ok("equip", "--who", "thorn", "--slot", "armor", "--item", "fixture-mail")
        self.assertEqual(out["warnings"], ["thorn is not proficient with fixture-mail"])
        self.assertEqual(out["ac"], 16)

    def test_item_must_fit_the_slot(self):
        self.make_fighter()
        self.refused("wrong_slot", "equip", "--who", "kira", "--slot", "armor", "--item", "fixture-sword")

    def test_at_most_two_weapons_are_wielded(self):
        self.make_fighter()
        party = self.party()
        party["characters"]["kira"]["inventory"] += [{"item": "fixture-dagger", "quantity": 2}]
        import json
        (self.campaign_dir / "party.json").write_text(json.dumps(party))
        self.ok("unequip", "--who", "kira", "--slot", "shield")
        self.ok("equip", "--who", "kira", "--slot", "weapon", "--item", "fixture-dagger")
        self.refused("hands_full", "equip", "--who", "kira", "--slot", "weapon", "--item", "fixture-dagger")

    def test_unequip_a_named_weapon_removes_its_attack(self):
        self.make_fighter()
        out = self.ok("unequip", "--who", "kira", "--slot", "weapon", "--item", "fixture-sword")
        self.assertNotIn("fixture-sword", out["attacks"])

    def test_unequip_an_empty_slot_is_refused(self):
        self.make_wizard()
        self.refused("nothing_equipped", "unequip", "--who", "thorn", "--slot", "armor")


class TestSpellsPrepare(CharacterCase):
    def test_prepare_replaces_the_prepared_list(self):
        self.make_wizard()
        self.ok("spells", "prepare", "--who", "thorn", "--spells", "fixture-ward,fixture-haze")
        self.assertEqual(self.char("thorn")["spellcasting"]["prepared"], ["fixture-ward", "fixture-haze"])

    def test_too_many_spells_is_refused(self):
        self.make_wizard()  # int 16 (+3) + level 1 = 4 allowed, only 3 known: force limit with a dumb wizard
        self.ok("character", "create", "--id", "dim", "--name", "Dim", "--class", "wizard", "--scores", "10,10,10,8,10,10")
        self.refused("too_many_spells_prepared", "spells", "prepare", "--who", "dim", "--spells", "fixture-bolt,fixture-ward")

    def test_spell_outside_the_spellbook_is_refused(self):
        self.make_wizard()
        self.refused("spell_not_available", "spells", "prepare", "--who", "thorn", "--spells", "fixture-beam")

    def test_cantrips_are_not_prepared(self):
        self.make_wizard()
        self.refused("spell_not_available", "spells", "prepare", "--who", "thorn", "--spells", "fixture-spark")

    def test_non_caster_is_refused(self):
        self.make_fighter()
        self.refused("not_a_caster", "spells", "prepare", "--who", "kira", "--spells", "fixture-bolt")


class TestXpAndLevelUp(CharacterCase):
    def test_xp_below_the_threshold_only_adds_xp(self):
        self.make_fighter()
        out = self.ok("xp", "--who", "kira", "--amount", "299")
        self.assertEqual(out["xp"], 299)
        self.assertNotIn("level_up", out)

    def test_crossing_a_threshold_levels_up_and_rolls_the_hit_die(self):
        self.make_fighter()
        out = self.ok("xp", "--who", "kira", "--amount", "300", rng=ScriptedRng([7]))
        self.assertEqual(out["level_up"]["to"], 2)
        c = self.char("kira")
        self.assertEqual(c["hp"]["max"], 12 + 7 + 2)
        self.assertEqual(c["hp"]["current"], 12 + 7 + 2)
        self.assertEqual(c["hit_dice"], {"die": "d10", "max": 2, "remaining": 2})
        self.assertIn("fixture-surge", c["features"])

    def test_a_large_award_can_cross_several_levels(self):
        self.make_fighter()
        out = self.ok("xp", "--who", "kira", "--amount", "2700", rng=ScriptedRng([5, 5, 5]))
        self.assertEqual((out["level_up"]["from"], out["level_up"]["to"]), (1, 4))
        self.assertEqual(self.char("kira")["pending_asi"], 1)

    def test_level_up_roll_is_logged_as_a_roll(self):
        self.make_fighter()
        self.ok("xp", "--who", "kira", "--amount", "300", rng=ScriptedRng([7]))
        kinds = [line["type"] for line in self.log_lines()[-2:]]
        self.assertEqual(kinds, ["roll", "state_change"])

    def test_wizard_level_up_raises_slots_and_grants_spellbook_picks(self):
        self.make_wizard()
        self.ok("xp", "--who", "thorn", "--amount", "900", rng=ScriptedRng([3, 3]))
        c = self.char("thorn")
        self.assertEqual(c["spellcasting"]["slots"]["2"], {"max": 2, "used": 0})
        self.assertEqual(c["pending_spell_picks"], 2)

    def test_level_five_is_the_cap(self):
        self.make_fighter()
        self.ok("xp", "--who", "kira", "--amount", "6500", rng=ScriptedRng([5, 5, 5, 5]))
        self.assertEqual(self.char("kira")["level"], 5)
        self.refused("level_cap_reached", "xp", "--who", "kira", "--amount", "100")

    def test_amount_must_be_positive(self):
        self.make_fighter()
        self.refused("illegal_value", "xp", "--who", "kira", "--amount", "0")


class TestAsiAndSpellsLearn(CharacterCase):
    def level_four(self):
        self.make_fighter()
        self.ok("xp", "--who", "kira", "--amount", "2700", rng=ScriptedRng([5, 5, 5]))

    def test_asi_needs_a_pending_improvement(self):
        self.make_fighter()
        self.refused("no_pending_asi", "character", "asi", "--who", "kira", "--increase", "str:2")

    def test_asi_plus_two_recomputes_the_sheet(self):
        self.level_four()
        self.ok("character", "asi", "--who", "kira", "--increase", "str:2")
        c = self.char("kira")
        self.assertEqual(c["abilities"]["str"], 18)
        self.assertEqual(c["attacks"]["fixture-sword"]["attack_bonus"], 6)
        self.assertEqual(c["pending_asi"], 0)

    def test_asi_must_total_two_points(self):
        self.level_four()
        self.refused("illegal_value", "character", "asi", "--who", "kira", "--increase", "str:1")
        self.refused("illegal_value", "character", "asi", "--who", "kira", "--increase", "str:2,dex:1")

    def test_asi_cannot_pass_twenty(self):
        self.level_four()
        party = self.party()
        party["characters"]["kira"]["abilities"]["str"] = 19
        import json
        (self.campaign_dir / "party.json").write_text(json.dumps(party))
        self.refused("illegal_value", "character", "asi", "--who", "kira", "--increase", "str:2")

    def test_con_increase_raises_hp_for_every_level(self):
        self.level_four()
        before = self.char("kira")["hp"]["max"]
        self.ok("character", "asi", "--who", "kira", "--increase", "con:2")
        self.assertEqual(self.char("kira")["hp"]["max"], before + 4)

    def test_spells_learn_spends_pending_picks(self):
        self.make_wizard()
        self.ok("xp", "--who", "thorn", "--amount", "900", rng=ScriptedRng([3, 3]))
        self.ok("spells", "learn", "--who", "thorn", "--spells", "fixture-beam")
        c = self.char("thorn")
        self.assertIn("fixture-beam", c["spellcasting"]["known"])
        self.assertEqual(c["pending_spell_picks"], 1)

    def test_spells_learn_without_picks_is_refused(self):
        self.make_wizard()
        self.refused("no_pending_picks", "spells", "learn", "--who", "thorn", "--spells", "fixture-haze")

    def test_spells_learn_refuses_a_spell_level_too_high(self):
        self.make_wizard()
        self.ok("xp", "--who", "thorn", "--amount", "300", rng=ScriptedRng([3]))
        self.refused("spell_not_available", "spells", "learn", "--who", "thorn", "--spells", "fixture-beam")


class TestLookupCommand(DmTestCase):
    def test_lookup_needs_no_campaign(self):
        code, out = self.run_cli(["lookup", "monster", "fixture-goblin"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["record"]["ac"], 15)

    def test_lookup_list_returns_names_only(self):
        code, out = self.run_cli(["lookup", "spell", "--list"])
        self.assertIn("fixture-bolt", out["names"])
        self.assertNotIn("record", out)

    def test_near_miss_suggests_the_right_name(self):
        code, out = self.run_cli(["lookup", "monster", "fixture-goblim"])
        self.assertEqual(out["error"]["code"], "unknown_name")
        self.assertIn("fixture-goblin", out["error"]["message"])

    def test_class_lookup_returns_one_level_row_not_all_of_them(self):
        code, out = self.run_cli(["lookup", "class", "wizard", "--level", "3"])
        self.assertEqual(out["record"]["level_row"]["slots"], {"1": 4, "2": 2})
        self.assertNotIn("levels", out["record"])

    def test_spell_list_can_filter_by_class_and_level(self):
        code, out = self.run_cli(["lookup", "spell", "--list", "--class", "wizard", "--level", "1"])
        self.assertEqual(out["names"], ["fixture-bolt", "fixture-haze", "fixture-ward"])

    def test_unknown_kind_is_a_bad_argument(self):
        code, out = self.run_cli(["lookup", "weather", "rain"])
        self.assertEqual(out["error"]["code"], "bad_arguments")


class TestRollNamedCommand(CharacterCase):
    def test_attack_roll_takes_the_bonus_from_the_sheet(self):
        self.make_fighter()
        out = self.ok("roll", "--who", "kira", "--attack", "fixture-sword", "--ac", "15", rng=ScriptedRng([10]))
        self.assertEqual((out["modifier"], out["total"], out["result"]), (5, 15, "hit"))
        self.assertEqual(out["damage_expr"], "1d8+3")

    def test_natural_twenty_is_a_critical_hit_and_natural_one_misses(self):
        self.make_fighter()
        crit = self.ok("roll", "--who", "kira", "--attack", "fixture-sword", "--ac", "30", rng=ScriptedRng([20]))
        self.assertEqual(crit["result"], "critical_hit")
        miss = self.ok("roll", "--who", "kira", "--attack", "fixture-sword", "--ac", "5", rng=ScriptedRng([1]))
        self.assertEqual(miss["result"], "miss")

    def test_weapon_not_equipped_is_refused(self):
        self.make_fighter()
        self.refused("unknown_weapon", "roll", "--who", "kira", "--attack", "fixture-bow")

    def test_skill_check_uses_the_skill_bonus(self):
        self.make_fighter()
        out = self.ok("roll", "--who", "kira", "--check", "athletics", "--dc", "15", rng=ScriptedRng([10]))
        self.assertEqual((out["modifier"], out["result"]), (5, "success"))

    def test_raw_ability_check_uses_the_ability_modifier(self):
        self.make_fighter()
        self.assertEqual(self.ok("roll", "--who", "kira", "--check", "cha", rng=ScriptedRng([10]))["modifier"], -1)

    def test_unknown_skill_is_refused(self):
        self.make_fighter()
        self.refused("unknown_skill", "roll", "--who", "kira", "--check", "juggling")

    def test_saving_throw_uses_the_save_bonus(self):
        self.make_fighter()
        self.assertEqual(self.ok("roll", "--who", "kira", "--save", "con", rng=ScriptedRng([10]))["modifier"], 4)

    def test_initiative_uses_dexterity(self):
        self.make_fighter()
        self.assertEqual(self.ok("roll", "--who", "kira", "--initiative", rng=ScriptedRng([10]))["total"], 12)

    def test_spell_attack_uses_the_spell_attack_bonus(self):
        self.make_wizard()
        out = self.ok("roll", "--who", "thorn", "--spell-attack", rng=ScriptedRng([10]))
        self.assertEqual(out["modifier"], 5)

    def test_advantage_works_on_named_rolls(self):
        self.make_fighter()
        out = self.ok("roll", "--who", "kira", "--save", "str", "--adv", rng=ScriptedRng([3, 16]))
        self.assertEqual(out["total"], 21)

    def test_named_roll_needs_who(self):
        self.make_fighter()
        self.refused("bad_arguments", "roll", "--attack", "fixture-sword")

    def test_only_one_roll_form_at_a_time(self):
        self.make_fighter()
        self.refused("bad_arguments", "roll", "--who", "kira", "--save", "con", "--check", "athletics")

    def test_named_roll_is_logged_with_who_and_kind(self):
        self.make_fighter()
        self.ok("roll", "--who", "kira", "--save", "con", rng=ScriptedRng([10]))
        payload = self.log_lines()[-1]["payload"]
        self.assertEqual((payload["who"], payload["kind"]), ("kira", "save:con"))
