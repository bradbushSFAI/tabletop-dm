"""lookup: one compact record from the rules data. Needs no campaign."""
import argparse
import random
from pathlib import Path
from typing import Any, Dict

from . import data
from .errors import DmError


def lookup(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    records = data.load_all(skill_root)[data.SINGULAR[args.kind]]
    if args.list:
        names = sorted(records)
        if args.kind == "spell":
            if args.char_class:
                names = [n for n in names if args.char_class.lower() in records[n]["classes"]]
            if args.level is not None:
                names = [n for n in names if records[n]["level"] == args.level]
        if args.kind == "monster" and args.cr is not None:
            names = [n for n in names if records[n]["challenge_rating"] == args.cr]
        return {"kind": args.kind, "names": names}
    if not args.name:
        raise DmError("bad_arguments", "give a name, or use --list.")
    record = dict(data.get_record(records, args.kind, args.name))
    if args.kind == "class":
        # One level row, never all five: a lookup stays about 100 tokens.
        levels = record.pop("levels")
        if args.level is not None:
            if str(args.level) not in levels:
                raise DmError("illegal_value", "%s has levels %s." % (record["id"], ", ".join(sorted(levels))))
            record["level_row"] = levels[str(args.level)]
        else:
            record["levels_available"] = sorted(levels)
    return {"kind": args.kind, "record": record}
