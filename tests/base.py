"""Shared test helpers. Adds the skill's scripts folder to sys.path once."""
import contextlib
import io
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_SKILL_ROOT = REPO_ROOT / "skills" / "tabletop-dm"
SCRIPTS_DIR = REAL_SKILL_ROOT / "scripts"
FIXTURE_SKILL_ROOT = Path(__file__).resolve().parent / "fixtures" / "skill_root"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class ScriptedRng(random.Random):
    """A random source that returns a fixed queue of die results.

    Every dice call in dmlib goes through rng.randint, so a test can state
    the exact dice it wants. Running out of values is a test bug.
    """

    def __init__(self, values: List[int]) -> None:
        super().__init__(0)
        self._values = list(values)

    def randint(self, a: int, b: int) -> int:
        if not self._values:
            raise AssertionError("ScriptedRng ran out of values")
        value = self._values.pop(0)
        if not a <= value <= b:
            raise AssertionError("scripted value %d outside %d..%d" % (value, a, b))
        return value


class DmTestCase(unittest.TestCase):
    SKILL_ROOT = FIXTURE_SKILL_ROOT

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.campaign_dir = Path(self._tmp.name) / "campaign"
        self.campaign_dir.mkdir()
        self.rng = random.Random(20260918)

    def run_cli(self, argv: List[str], rng: Any = None) -> Tuple[int, Dict[str, Any]]:
        from dmlib import cli

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.run(argv, self.SKILL_ROOT, rng if rng is not None else self.rng)
        return code, json.loads(buf.getvalue())

    def camp(self, *argv: str, rng: Any = None) -> Tuple[int, Dict[str, Any]]:
        """Run a command with --campaign appended."""
        return self.run_cli(list(argv) + ["--campaign", str(self.campaign_dir)], rng=rng)

    def ok(self, *argv: str, rng: Any = None) -> Dict[str, Any]:
        code, out = self.camp(*argv, rng=rng)
        self.assertEqual(code, 0, out)
        self.assertTrue(out["ok"], out)
        return out

    def refused(self, error_code: str, *argv: str, rng: Any = None) -> Dict[str, Any]:
        code, out = self.camp(*argv, rng=rng)
        self.assertEqual(code, 1, out)
        self.assertFalse(out["ok"], out)
        self.assertEqual(out["error"]["code"], error_code, out)
        return out

    def init_campaign(self) -> None:
        self.ok("init")

    def party(self) -> Dict[str, Any]:
        return json.loads((self.campaign_dir / "party.json").read_text())

    def log_lines(self) -> List[Dict[str, Any]]:
        text = (self.campaign_dir / "log.jsonl").read_text()
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def snapshot(self) -> Dict[str, str]:
        """Every file's text, to prove a refusal changed nothing on disk."""
        return {p.name: p.read_text() for p in sorted(self.campaign_dir.iterdir()) if p.is_file()}
