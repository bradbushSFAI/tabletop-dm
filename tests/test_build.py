"""The two release zips: what is in them, and what must never be."""
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.base import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
import build  # noqa: E402

FORBIDDEN = ("tests/", "playtests/", "docs/", "GRILL.md", "PRD.md", "__pycache__", ".pyc", ".DS_Store", ".git")


class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = build.build(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def names(self, key):
        with zipfile.ZipFile(str(self.paths[key])) as zf:
            return zf.namelist()

    def test_both_zips_are_made(self):
        self.assertEqual(sorted(self.paths), ["plugin", "skill"])
        self.assertEqual(self.paths["plugin"].name, "tabletop-dm-plugin.zip")
        self.assertEqual(self.paths["skill"].name, "tabletop-dm-skill.zip")

    def test_plugin_zip_holds_the_manifest_and_the_skill(self):
        names = self.names("plugin")
        for needed in [".claude-plugin/plugin.json", "skills/tabletop-dm/SKILL.md", "skills/tabletop-dm/scripts/dm.py",
                       "skills/tabletop-dm/scripts/dmlib/cli.py", "skills/tabletop-dm/data/monsters.json",
                       "skills/tabletop-dm/reference/combat.md", "skills/tabletop-dm/LICENSE-SRD.md"]:
            self.assertIn(needed, names)

    def test_skill_zip_has_the_skill_folder_at_its_root(self):
        names = self.names("skill")
        self.assertIn("tabletop-dm/SKILL.md", names)
        self.assertTrue(all(n.startswith("tabletop-dm/") for n in names))

    def test_neither_zip_ships_tests_docs_or_caches(self):
        for key in ("plugin", "skill"):
            for name in self.names(key):
                for bad in FORBIDDEN:
                    with self.subTest(zip=key, name=name, bad=bad):
                        self.assertNotIn(bad, name)

    def test_manifest_is_valid_and_matches_the_skill_version(self):
        manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertRegex(manifest["name"], r"^[a-z0-9-]{1,64}$")
        self.assertNotIn("claude", manifest["name"])
        init = (REPO_ROOT / "skills" / "tabletop-dm" / "scripts" / "dmlib" / "__init__.py").read_text()
        self.assertEqual(manifest["version"], re.search(r'__version__ = "([^"]+)"', init).group(1))

    def test_both_zips_carry_the_mit_licence(self):
        self.assertIn("skills/tabletop-dm/LICENSE.txt", self.names("plugin"))
        self.assertIn("tabletop-dm/LICENSE.txt", self.names("skill"))
        root = (REPO_ROOT / "LICENSE").read_text()
        self.assertTrue(root.startswith("MIT License"))
        self.assertEqual((REPO_ROOT / "skills" / "tabletop-dm" / "LICENSE.txt").read_text(), root)
        manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["license"], "MIT")

    def test_the_repo_is_a_marketplace_that_lists_this_plugin(self):
        market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text())
        manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(market["name"], "tabletop-dm")
        self.assertIn("name", market["owner"])
        self.assertEqual([p["name"] for p in market["plugins"]], [manifest["name"]])
        self.assertEqual(market["plugins"][0]["source"], "./")

    def test_the_plugin_zip_is_a_plugin_not_a_marketplace(self):
        self.assertNotIn(".claude-plugin/marketplace.json", self.names("plugin"))

    def test_the_zipped_script_runs_after_unpacking(self):
        import subprocess

        with tempfile.TemporaryDirectory() as out:
            with zipfile.ZipFile(str(self.paths["skill"])) as zf:
                zf.extractall(out)
            proc = subprocess.run([sys.executable, "-B", str(Path(out) / "tabletop-dm" / "scripts" / "dm.py"), "--version"],
                                  capture_output=True, text=True, timeout=30)
        self.assertTrue(json.loads(proc.stdout)["ok"], proc.stdout)
