"""roll: the free form (any expression) and the named forms (from a sheet)."""
import argparse
import random
import re
from pathlib import Path
from typing import Any, Dict, Optional

from . import dice, io_campaign
from .errors import DmError

# "1d20", "1d20+5", "1d20+2-1": the only shape advantage can apply to.
_SINGLE_D20 = re.compile(r"^1d20((?:[+-]\d+)*)$")


def resolve(total: int, natural: Optional[int], dc: Optional[int], ac: Optional[int]) -> Optional[str]:
    """Success or failure against a DC. Hit or miss against an AC (5e: natural 20 and 1)."""
    if ac is not None:
        if natural == 20:
            return "critical_hit"
        if natural == 1:
            return "miss"
        return "hit" if total >= ac else "miss"
    if dc is not None:
        return "success" if total >= dc else "failure"
    return None


def roll_with_d20_rules(expr: str, rng: random.Random, adv: bool, disadv: bool) -> Dict[str, Any]:
    """Roll an expression. A lone d20 also reports its natural value and honours advantage."""
    text = expr.replace(" ", "").lower()
    match = _SINGLE_D20.match(text)
    if not match:
        if adv or disadv:
            raise DmError(
                "advantage_invalid_for_expression",
                "advantage and disadvantage only apply to a single d20 roll, not to '%s'." % expr,
            )
        return dice.roll_expression(expr, rng)
    modifier = dice.roll_expression(match.group(1) or "0", rng)["total"] if match.group(1) else 0
    d20 = dice.roll_d20(rng, advantage=adv, disadvantage=disadv)
    return {
        "expr": expr.strip(),
        "dice": [{"term": "1d20", "rolls": d20["rolls"], "kept": [d20["kept"]]}],
        "modifier": modifier,
        "total": d20["kept"] + modifier,
        "d20": d20,
        "natural": d20["kept"],
    }


def roll(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    io_campaign.load_party(campaign_dir)
    if not args.expr:
        raise DmError("bad_arguments", "give a dice expression, for example: roll 2d6+3")
    out = roll_with_d20_rules(args.expr, rng, args.adv, args.disadv)
    return finish(campaign_dir, out, args, who=None, kind="free")


def finish(campaign_dir: Path, out: Dict[str, Any], args: argparse.Namespace,
           who: Optional[str], kind: str) -> Dict[str, Any]:
    """Add the target and result, log the roll, and return the output."""
    if args.dc is not None:
        out["target"] = {"dc": args.dc}
    elif args.ac is not None:
        out["target"] = {"ac": args.ac}
    result = resolve(out["total"], out.get("natural"), args.dc, args.ac)
    if result is not None:
        out["result"] = result
    if args.reason:
        out["reason"] = args.reason
    payload = dict(out)
    payload["who"] = who
    payload["kind"] = kind
    io_campaign.append_log(campaign_dir, [io_campaign.roll_entry("roll", payload)])
    return out
