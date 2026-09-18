"""The dice roller. The random source is always passed in, never made here."""
import random
import re
from typing import Any, Dict, List

from .errors import DmError

# Limits keep a typo such as "1000000d6" from hanging the session.
MAX_DICE_PER_TERM = 100
MAX_EXPRESSION_LENGTH = 100
MAX_TERMS = 10
MIN_SIDES = 2
MAX_SIDES = 1000

_TERM = re.compile(r"^(?:(\d+)d(\d+)(?:(kh|kl)(\d+))?|(\d+))$")


def _bad(expr: str, why: str) -> DmError:
    return DmError("bad_expression", "'%s' is not a legal dice expression: %s" % (expr, why))


def roll_expression(expr: str, rng: random.Random) -> Dict[str, Any]:
    """Roll an expression such as 1d20+5, 2d6+3, 4d6kh3, 1d8+1d6-1, 5d4*10."""
    if len(expr) > MAX_EXPRESSION_LENGTH:
        raise DmError("bad_expression", "a dice expression is at most %d characters. This one has %d."
                      % (MAX_EXPRESSION_LENGTH, len(expr)))
    text = expr.replace(" ", "").lower()
    if not text:
        raise _bad(expr, "it is empty")
    multiplier = 1
    if "*" in text:
        text, _, mult = text.partition("*")
        if not mult.isdigit():
            raise _bad(expr, "a whole number must follow '*'")
        multiplier = int(mult)
    # Split into signed terms: "1d8+1d6-1" -> [("+","1d8"),("+","1d6"),("-","1")]
    pieces = re.findall(r"([+-]?)([^+-]*)", text)
    terms = [(sign or "+", body) for sign, body in pieces if sign or body]
    if not terms:
        raise _bad(expr, "it has no terms")
    if len(terms) > MAX_TERMS:
        raise _bad(expr, "at most %d terms" % MAX_TERMS)
    dice_out = []  # type: List[Dict[str, Any]]
    modifier = 0
    total = 0
    parsed = []
    for sign, body in terms:
        match = _TERM.match(body)
        if not match:
            raise _bad(expr, "cannot read '%s'" % (sign + body))
        parsed.append((sign, body, match))
    # Validate every term before rolling any die, so a refusal uses no randomness.
    for sign, body, match in parsed:
        if match.group(5) is not None:
            continue
        count, sides = int(match.group(1)), int(match.group(2))
        if not 1 <= count <= MAX_DICE_PER_TERM:
            raise _bad(expr, "dice count must be 1 to %d" % MAX_DICE_PER_TERM)
        if not MIN_SIDES <= sides <= MAX_SIDES:
            raise _bad(expr, "die size must be %d to %d" % (MIN_SIDES, MAX_SIDES))
        if match.group(3) and not 1 <= int(match.group(4)) <= count:
            raise _bad(expr, "cannot keep %s of %d dice" % (match.group(4), count))
    for sign, body, match in parsed:
        factor = -1 if sign == "-" else 1
        if match.group(5) is not None:
            modifier += factor * int(match.group(5))
            continue
        count, sides = int(match.group(1)), int(match.group(2))
        rolls = [rng.randint(1, sides) for _ in range(count)]
        kept = list(rolls)
        if match.group(3):
            keep = int(match.group(4))
            ordered = sorted(rolls, reverse=(match.group(3) == "kh"))
            kept = ordered[:keep]
        total += factor * sum(kept)
        dice_out.append({"term": sign.replace("+", "") + body, "rolls": rolls, "kept": kept})
    total = (total + modifier) * multiplier
    out = {"expr": expr.strip(), "dice": dice_out, "modifier": modifier, "total": total}  # type: Dict[str, Any]
    if multiplier != 1:
        out["multiplier"] = multiplier
    return out


def roll_d20(rng: random.Random, advantage: bool = False, disadvantage: bool = False) -> Dict[str, Any]:
    """One d20, or two with the higher or lower kept. Both flags cancel (5e)."""
    if advantage == disadvantage:
        value = rng.randint(1, 20)
        return {"rolls": [value], "kept": value, "mode": "normal"}
    rolls = [rng.randint(1, 20), rng.randint(1, 20)]
    kept = max(rolls) if advantage else min(rolls)
    return {"rolls": rolls, "kept": kept, "mode": "advantage" if advantage else "disadvantage"}


def roll_hit_die(die: str, rng: random.Random) -> int:
    """Roll one hit die named like 'd10'."""
    return rng.randint(1, int(die.lstrip("d")))
