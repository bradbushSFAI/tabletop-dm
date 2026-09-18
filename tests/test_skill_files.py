"""Structure tests for SKILL.md and the reference files (limits from the Agent Skills docs)."""
import re

from tests.base import REAL_SKILL_ROOT, unittest

from dmlib import cli

SKILL_MD = REAL_SKILL_ROOT / "SKILL.md"
REFERENCES = ["combat.md", "checks.md", "dm-style.md", "session-flow.md"]


def frontmatter():
    text = SKILL_MD.read_text()
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, "SKILL.md must start with YAML frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, match.group(2)


class TestSkillMdLength(unittest.TestCase):
    def test_name_follows_the_skill_naming_rules(self):
        name = frontmatter()[0]["name"]
        self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
        self.assertNotIn("claude", name)
        self.assertNotIn("anthropic", name)
        self.assertEqual(name, SKILL_MD.parent.name)

    def test_description_is_third_person_and_within_the_limit(self):
        description = frontmatter()[0]["description"]
        self.assertTrue(0 < len(description) <= 1024)
        self.assertNotIn("<", description)
        self.assertNotRegex(description, r"\b(I can|I will|You can)\b")

    def test_description_names_the_trigger_situations(self):
        description = frontmatter()[0]["description"].lower()
        for phrase in ["d&d", "campaign", "dungeon master", "continue"]:
            self.assertIn(phrase, description)

    def test_body_is_under_500_lines(self):
        self.assertLess(len(frontmatter()[1].splitlines()), 500)

    def test_every_cli_command_is_documented(self):
        body = frontmatter()[1]
        for key in cli.HANDLERS:
            if key == "version":
                self.assertIn("--version", body)
                continue
            with self.subTest(command=key):
                self.assertIn(key, body)

    def test_the_six_firm_rules_are_present(self):
        body = frontmatter()[1].lower()
        for phrase in ["--version", "never edit", "never change a roll", "never act", "every scene change", "dm-secrets.md"]:
            with self.subTest(rule=phrase):
                self.assertIn(phrase, body)

    def test_paths_use_forward_slashes_only(self):
        """A backslash between two name characters is a Windows path. (A table's \\| escape is fine.)"""
        self.assertNotRegex(SKILL_MD.read_text(), r"[A-Za-z0-9_]\\[A-Za-z0-9_]")


class TestReferenceFilesStructure(unittest.TestCase):
    def test_every_reference_file_exists_and_is_linked_from_skill_md(self):
        body = frontmatter()[1]
        for name in REFERENCES:
            with self.subTest(file=name):
                self.assertTrue((REAL_SKILL_ROOT / "reference" / name).is_file())
                self.assertIn("reference/" + name, body)

    def test_a_long_reference_file_starts_with_a_table_of_contents(self):
        for name in REFERENCES:
            lines = (REAL_SKILL_ROOT / "reference" / name).read_text().splitlines()
            if len(lines) > 100:
                with self.subTest(file=name):
                    self.assertIn("## Contents", lines[:12])

    def test_reference_files_do_not_link_to_other_reference_files(self):
        """One level deep from SKILL.md: a nested link gets a partial read."""
        for name in REFERENCES:
            text = (REAL_SKILL_ROOT / "reference" / name).read_text()
            with self.subTest(file=name):
                self.assertNotRegex(text, r"\]\((?!https?:)[^)]*\.md\)")

    def test_no_em_dashes_in_the_skill_prose(self):
        for path in [SKILL_MD] + [REAL_SKILL_ROOT / "reference" / n for n in REFERENCES]:
            with self.subTest(file=path.name):
                self.assertNotIn("—", path.read_text())
