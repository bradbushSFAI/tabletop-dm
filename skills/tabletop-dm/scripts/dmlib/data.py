"""Loads the rules data that ships in the skill folder. Read-only."""
import difflib
import json
from pathlib import Path
from typing import Any, Dict, List

from .errors import DmError

KINDS = ("classes", "spells", "monsters", "equipment")
# lookup takes the singular word.
SINGULAR = {"class": "classes", "spell": "spells", "monster": "monsters", "equipment": "equipment"}


def load_all(skill_root: Path) -> Dict[str, Dict[str, Any]]:
    """Return {"classes": {...}, "spells": {...}, ...} or refuse with every problem found."""
    problems = []  # type: List[str]
    out = {}  # type: Dict[str, Dict[str, Any]]
    for kind in KINDS:
        path = skill_root / "data" / (kind + ".json")
        if not path.is_file():
            problems.append("data/%s.json is missing" % kind)
            continue
        try:
            doc = json.loads(path.read_text())
        except ValueError as exc:
            problems.append("data/%s.json is not valid JSON (%s)" % (kind, exc))
            continue
        if not isinstance(doc, dict) or doc.get("format") != "tabletop-dm/" + kind:
            problems.append("data/%s.json has no 'tabletop-dm/%s' format marker" % (kind, kind))
            continue
        records = doc.get(kind)
        if not isinstance(records, dict) or not records:
            problems.append("data/%s.json has no '%s' records" % (kind, kind))
            continue
        for key, record in records.items():
            if not isinstance(record, dict) or record.get("id") != key:
                problems.append("data/%s.json: entry '%s' must be an object whose id is '%s'" % (kind, key, key))
        out[kind] = records
    if problems:
        raise DmError("data_invalid", "the skill's data files have problems: " + "; ".join(problems))
    return out


def get_record(records: Dict[str, Any], kind_word: str, name: str) -> Dict[str, Any]:
    """One record by id, or a refusal that lists near matches."""
    key = name.strip().lower().replace(" ", "-")
    if key in records:
        return records[key]
    near = difflib.get_close_matches(key, list(records), n=3, cutoff=0.5)
    hint = " Did you mean: %s?" % ", ".join(near) if near else ""
    raise DmError("unknown_name", "no %s '%s'.%s" % (kind_word, name, hint))


def list_seed_names(skill_root: Path) -> List[str]:
    folder = skill_root / "seeds"
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.md") if p.stem != "teasers")
