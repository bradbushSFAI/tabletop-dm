"""Structure tests for the world, the metaplot and the seeds.

SPOILER WALL: these tests read the secret files, so no assertion here may print file content.
Every check is a plain True/False with a message that names the file and the rule only.
"""
import re

from tests.base import REAL_SKILL_ROOT, unittest
from tests.test_data_real import BANNED

WORLD = REAL_SKILL_ROOT / "world"
SEEDS = REAL_SKILL_ROOT / "seeds"
SEED_NAMES = ["brannocks-cut", "greywater", "hushwood", "sallows", "tollhills"]
SEED_SECTIONS = ["Tone", "Start place", "The opening scene", "What is really going on here", "The local villain",
                 "Other people", "Companion candidates", "If the hero does nothing", "Fights", "Local secrets",
                 "The way in to the larger mystery", "Ways it can end"]
METAPLOT_SECTIONS = ["The truth", "Who is behind it", "How it started", "The clock", "The five revelations",
                     "The nine rumours", "Which door reaches what", "How to run it", "The moral question"]


def story_files():
    return [WORLD / "bible.md", WORLD / "metaplot.md", SEEDS / "teasers.md"] + [SEEDS / (n + ".md") for n in SEED_NAMES]


class TestWorldFiles(unittest.TestCase):
    def test_every_story_file_exists(self):
        for path in story_files():
            self.assertTrue(path.is_file(), "%s is missing" % path.name)

    def test_the_seed_folder_holds_exactly_the_five_doors_and_the_teasers(self):
        names = sorted(p.stem for p in SEEDS.glob("*.md"))
        self.assertEqual(names, sorted(SEED_NAMES + ["teasers"]))

    def test_teasers_has_one_line_per_seed_in_the_documented_format(self):
        lines = [ln for ln in (SEEDS / "teasers.md").read_text().splitlines() if ln.strip()]
        self.assertEqual(len(lines), len(SEED_NAMES), "teasers.md must have one line per seed")
        found = []
        for line in lines:
            match = re.match(r"^([a-z0-9-]+): (.+)$", line)
            self.assertTrue(bool(match), "a teaser line is not in the 'name: sentence' format")
            found.append(match.group(1))
            words = len(match.group(2).split())
            self.assertTrue(10 <= words <= 40, "a teaser must be one sentence of about 15 to 30 words")
        self.assertEqual(sorted(found), sorted(SEED_NAMES))

    def test_every_seed_has_every_section_in_order(self):
        for name in SEED_NAMES:
            text = (SEEDS / (name + ".md")).read_text()
            positions = [text.find("## " + section) for section in SEED_SECTIONS]
            self.assertTrue(all(p >= 0 for p in positions), "%s.md is missing a required section" % name)
            self.assertTrue(positions == sorted(positions), "%s.md has its sections out of order" % name)

    def test_every_seed_is_a_page_or_two(self):
        for name in SEED_NAMES:
            words = len((SEEDS / (name + ".md")).read_text().split())
            # Read once per campaign, so length is cheap. The cap only stops a seed becoming a script.
            self.assertTrue(450 <= words <= 1900, "%s.md should be 450 to 1900 words" % name)

    def test_metaplot_has_every_section_and_five_revelations(self):
        text = (WORLD / "metaplot.md").read_text()
        for section in METAPLOT_SECTIONS:
            self.assertTrue(("## " + section) in text, "metaplot.md is missing the section '%s'" % section)
        for code in ("R1", "R2", "R3", "R4", "R5"):
            self.assertTrue(code in text, "metaplot.md does not define %s" % code)

    def test_every_seed_points_at_the_metaplot_but_not_all_of_it(self):
        for name in SEED_NAMES:
            text = (SEEDS / (name + ".md")).read_text()
            way_in = text[text.find("## The way in to the larger mystery"):text.find("## Ways it can end")]
            reached = set(re.findall(r"\bR[1-5]\b", way_in))
            self.assertTrue(len(reached) >= 2, "%s.md must name the revelations it can reach" % name)

    def test_every_revelation_is_reachable_from_at_least_two_doors(self):
        table = (WORLD / "metaplot.md").read_text()
        table = table[table.find("## Which door reaches what"):table.find("## How to run it")]
        for code in ("R1", "R2", "R3", "R4", "R5"):
            rows = [ln for ln in table.splitlines() if ln.startswith("|") and any(n in ln for n in SEED_NAMES)]
            reach = 0
            for row in rows:
                cells = [c.strip() for c in row.strip("|").split("|")]
                if len(cells) >= 2 and code in cells[1]:
                    reach += 1
            self.assertTrue(reach >= 2, "%s must be reachable from at least two doors" % code)

    def test_no_em_dashes_and_no_product_identity(self):
        for path in story_files():
            text = path.read_text()
            self.assertTrue("—" not in text, "%s contains an em-dash" % path.name)
            lowered = text.lower()
            for term in BANNED:
                hit = re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", lowered)
                self.assertTrue(hit is None, "%s contains a banned product-identity term (index %d of the ban list)"
                                % (path.name, BANNED.index(term)))

    def test_companion_candidates_use_only_the_four_classes(self):
        for name in SEED_NAMES:
            text = (SEEDS / (name + ".md")).read_text()
            part = text[text.find("## Companion candidates"):text.find("## If the hero does nothing")].lower()
            self.assertTrue(any(c in part for c in ("fighter", "rogue", "wizard", "cleric")),
                            "%s.md names no class for its companions" % name)
            for other in ("barbarian", "bard", "druid", "monk", "paladin", "ranger", "sorcerer", "warlock"):
                self.assertTrue(re.search(r"\b%s\b" % other, part) is None,
                                "%s.md gives a companion a class this build does not have" % name)

    def test_fights_name_monsters_that_exist_in_the_data(self):
        from dmlib import data

        monsters = data.load_all(REAL_SKILL_ROOT)["monsters"]
        names = sorted(monsters, key=len, reverse=True)
        for seed in SEED_NAMES:
            text = (SEEDS / (seed + ".md")).read_text()
            part = text[text.find("## Fights"):text.find("## Local secrets")].lower().replace(" ", "-")
            found = [m for m in names if m in part]
            self.assertTrue(len(found) >= 2, "%s.md must name at least two monsters from the rules data in Fights" % seed)

    def test_the_installed_skill_reports_five_seeds(self):
        from dmlib import data

        self.assertEqual(data.list_seed_names(REAL_SKILL_ROOT), SEED_NAMES)
