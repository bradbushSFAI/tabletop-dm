#!/usr/bin/env python3
"""dm.py: the state keeper for the tabletop-dm skill.

Owns every number in the game: dice, hit points, spell slots, gold, inventory.
Standard library only. Run it by its full path from any folder.
"""
import random
import sys
from pathlib import Path


def main(argv=None):
    scripts_dir = Path(__file__).resolve().parent
    # Python already puts the script's folder on sys.path. This is insurance
    # for a host that starts the script in an unusual way.
    sys.path.insert(0, str(scripts_dir))
    from dmlib.cli import run

    skill_root = scripts_dir.parent
    return run(sys.argv[1:] if argv is None else argv, skill_root, random.SystemRandom())


if __name__ == "__main__":
    sys.exit(main())
