from tests.base import ScriptedRng, unittest

from dmlib import dice
from dmlib.errors import DmError


class TestDiceExpr(unittest.TestCase):
    def test_single_die_with_modifier_totals_roll_plus_modifier(self):
        out = dice.roll_expression("1d20+5", ScriptedRng([14]))
        self.assertEqual(out["total"], 19)
        self.assertEqual(out["modifier"], 5)
        self.assertEqual(out["dice"][0]["rolls"], [14])

    def test_multiple_dice_are_all_reported(self):
        out = dice.roll_expression("2d6+3", ScriptedRng([2, 5]))
        self.assertEqual(out["dice"][0]["rolls"], [2, 5])
        self.assertEqual(out["total"], 10)

    def test_keep_highest_drops_the_lowest(self):
        out = dice.roll_expression("4d6kh3", ScriptedRng([1, 6, 4, 3]))
        self.assertEqual(out["dice"][0]["kept"], [6, 4, 3])
        self.assertEqual(out["total"], 13)

    def test_keep_lowest_drops_the_highest(self):
        out = dice.roll_expression("2d20kl1", ScriptedRng([17, 4]))
        self.assertEqual(out["total"], 4)

    def test_negative_modifier_and_second_dice_term(self):
        out = dice.roll_expression("1d8+1d6-1", ScriptedRng([8, 6]))
        self.assertEqual(out["total"], 13)
        self.assertEqual(out["modifier"], -1)

    def test_trailing_multiplier_applies_to_the_whole_sum(self):
        out = dice.roll_expression("5d4*10", ScriptedRng([1, 2, 3, 4, 4]))
        self.assertEqual(out["total"], 140)

    def test_constant_only_expression_is_legal(self):
        self.assertEqual(dice.roll_expression("7", ScriptedRng([]))["total"], 7)

    def test_spaces_and_upper_case_are_accepted(self):
        self.assertEqual(dice.roll_expression(" 1D6 + 2 ", ScriptedRng([3]))["total"], 5)

    def test_bad_expressions_are_refused(self):
        for bad in ["", "2d", "d", "1d6++2", "abc", "1d6kh2", "0d6", "1d1", "101d6", "1d6*"]:
            with self.subTest(expr=bad):
                with self.assertRaises(DmError) as ctx:
                    dice.roll_expression(bad, ScriptedRng([1] * 200))
                self.assertEqual(ctx.exception.code, "bad_expression")


class TestDiceD20Advantage(unittest.TestCase):
    def test_plain_d20_rolls_once(self):
        out = dice.roll_d20(ScriptedRng([11]))
        self.assertEqual(out, {"rolls": [11], "kept": 11, "mode": "normal"})

    def test_advantage_keeps_the_higher_of_two(self):
        out = dice.roll_d20(ScriptedRng([4, 18]), advantage=True)
        self.assertEqual(out["kept"], 18)
        self.assertEqual(out["rolls"], [4, 18])

    def test_disadvantage_keeps_the_lower_of_two(self):
        self.assertEqual(dice.roll_d20(ScriptedRng([4, 18]), disadvantage=True)["kept"], 4)

    def test_advantage_and_disadvantage_cancel_to_one_roll(self):
        out = dice.roll_d20(ScriptedRng([9]), advantage=True, disadvantage=True)
        self.assertEqual(out["rolls"], [9])
        self.assertEqual(out["mode"], "normal")

    def test_hit_die_rolls_the_named_die(self):
        self.assertEqual(dice.roll_hit_die("d10", ScriptedRng([7])), 7)


class TestErrors(unittest.TestCase):
    def test_error_envelope_has_the_one_error_shape(self):
        from dmlib.errors import error_envelope

        env = error_envelope("gold", DmError("insufficient_gold", "kira has 15 gp"))
        self.assertEqual(
            env,
            {"ok": False, "command": "gold", "error": {"code": "insufficient_gold", "message": "kira has 15 gp"}},
        )

    def test_success_envelope_puts_ok_and_command_first(self):
        from dmlib.errors import success_envelope

        env = success_envelope("gold", gold_gp=15.0)
        self.assertEqual(list(env.keys())[:2], ["ok", "command"])
        self.assertEqual(env["gold_gp"], 15.0)
