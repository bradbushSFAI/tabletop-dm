"""Argument parsing and dispatch. Prints exactly one compact JSON line per run."""
import argparse
import json
import random
from pathlib import Path
from typing import Any, Callable, Dict, List

from . import cmd_roll, cmd_setup
from .errors import DmError, error_envelope, success_envelope

Handler = Callable[[argparse.Namespace, Path, random.Random], Dict[str, Any]]

HANDLERS = {
    "version": cmd_setup.version,
    "init": cmd_setup.init,
    "settings set": cmd_setup.settings_set,
    "status": cmd_setup.status,
    "roll": cmd_roll.roll,
}  # type: Dict[str, Handler]


class _Parser(argparse.ArgumentParser):
    """argparse prints usage and exits. The model needs a JSON error instead."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise DmError("bad_arguments", "%s. Usage: %s" % (message, self.format_usage().strip()))

    def exit(self, status: int = 0, message: Any = None) -> None:  # type: ignore[override]
        raise DmError("bad_arguments", (message or "see the command table in SKILL.md").strip())


def _leaf(sub: Any, name: str, key: str, campaign: bool = True) -> argparse.ArgumentParser:
    parser = sub.add_parser(name, add_help=False)
    parser.set_defaults(handler_key=key)
    if campaign:
        parser.add_argument("--campaign", required=True)
    return parser


def _group(sub: Any, name: str) -> Any:
    parser = sub.add_parser(name, add_help=False)
    return parser.add_subparsers(dest=name + "_command", parser_class=_Parser, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="dm.py", add_help=False)
    sub = parser.add_subparsers(dest="command", parser_class=_Parser, required=True)

    _leaf(sub, "init", "init")
    _leaf(sub, "status", "status")

    settings = _group(sub, "settings")
    p = _leaf(settings, "set", "settings set")
    p.add_argument("--difficulty")
    p.add_argument("--content-level", dest="content_level")
    p.add_argument("--tone", action="append")

    p = _leaf(sub, "roll", "roll")
    p.add_argument("expr", nargs="?")
    p.add_argument("--adv", action="store_true")
    p.add_argument("--disadv", action="store_true")
    p.add_argument("--dc", type=int)
    p.add_argument("--ac", type=int)
    p.add_argument("--reason")
    return parser


def dispatch(argv: List[str], skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    """Run one command. Returns the success envelope or raises DmError."""
    if argv == ["--version"]:
        return success_envelope("version", **HANDLERS["version"](argparse.Namespace(), skill_root, rng))
    args = build_parser().parse_args(argv)
    key = args.handler_key
    return success_envelope(key.replace(" ", "_"), **HANDLERS[key](args, skill_root, rng))


def _command_name(argv: List[str]) -> str:
    words = [word for word in argv[:2] if not word.startswith("-")]
    joined = " ".join(words)
    if joined in HANDLERS:
        return joined.replace(" ", "_")
    if words and words[0] in HANDLERS:
        return words[0]
    return "version" if argv == ["--version"] else "unknown"


def run(argv: List[str], skill_root: Path, rng: random.Random) -> int:
    """dispatch, then print one compact JSON line. Returns the exit code."""
    try:
        out = dispatch(argv, skill_root, rng)
        code = 0
    except DmError as err:
        out = error_envelope(_command_name(argv), err)
        code = 1
    except Exception as exc:  # A bug must still reach the model as JSON, not a traceback.
        out = error_envelope(
            _command_name(argv),
            DmError("internal_error", "%s: %s. This is a bug in dm.py. No change was confirmed." % (type(exc).__name__, exc)),
        )
        code = 1
    print(json.dumps(out, separators=(",", ":")))
    return code
