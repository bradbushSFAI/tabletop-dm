import ast
import json
import subprocess
import sys
import tempfile

from tests.base import DmTestCase, SCRIPTS_DIR, unittest


class TestCliDispatch(DmTestCase):
    def test_unknown_command_is_a_json_error_not_a_usage_dump(self):
        code, out = self.run_cli(["dance"])
        self.assertEqual(code, 1)
        self.assertEqual(out["error"]["code"], "bad_arguments")

    def test_no_arguments_is_a_json_error(self):
        code, out = self.run_cli([])
        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])

    def test_output_is_one_compact_json_line(self):
        import contextlib
        import io

        from dmlib import cli

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.run(["--version"], self.SKILL_ROOT, self.rng)
        text = buf.getvalue()
        self.assertEqual(text.count("\n"), 1)
        self.assertNotIn(", ", text.split('"python_version"')[0])

    def test_an_unexpected_crash_is_reported_as_json_not_a_traceback(self):
        from dmlib import cli

        def boom(args, skill_root, rng):
            raise RuntimeError("kaboom")

        original = cli.HANDLERS["status"]
        cli.HANDLERS["status"] = boom
        self.addCleanup(cli.HANDLERS.__setitem__, "status", original)
        code, out = self.camp("status")
        self.assertEqual(code, 1)
        self.assertEqual(out["error"]["code"], "internal_error")
        self.assertIn("kaboom", out["error"]["message"])

    def test_real_script_runs_by_absolute_path_from_another_folder(self):
        """Proves the import mechanism: dm.py finds dmlib from any working directory."""
        with tempfile.TemporaryDirectory() as elsewhere:
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "dm.py"), "--version"],
                cwd=elsewhere, capture_output=True, text=True, timeout=30,
            )
        out = json.loads(proc.stdout)
        self.assertEqual(out["command"], "version")


class TestPython39Syntax(unittest.TestCase):
    def test_every_source_file_parses_as_python_3_9(self):
        files = sorted(SCRIPTS_DIR.rglob("*.py"))
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=path.name):
                ast.parse(path.read_text(), filename=str(path), feature_version=(3, 9))

    def test_no_source_file_imports_outside_the_standard_library_or_the_network(self):
        banned = {"requests", "urllib", "http", "socket", "ssl", "ftplib", "smtplib", "subprocess"}
        for path in sorted(SCRIPTS_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                for name in names:
                    with self.subTest(path=path.name, module=name):
                        self.assertNotIn(name, banned)
