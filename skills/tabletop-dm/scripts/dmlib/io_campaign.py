"""Every read and write of the campaign folder. Nothing here writes anywhere else."""
import contextlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from . import CURRENT_FORMAT_VERSION
from .errors import DmError

PARTY_FORMAT = "tabletop-dm/party"
ENCOUNTER_FORMAT = "tabletop-dm/encounter"

PARTY_FILE = "party.json"
ENCOUNTER_FILE = "encounter.json"
LOG_FILE = "log.jsonl"
LOCK_FILE = ".dm.lock"

# A command takes well under a second. A lock older than this belongs to a process that died.
STALE_LOCK_SECONDS = 30
# A model can send tool calls in parallel. A waiting command gives up after this long.
LOCK_WAIT_SECONDS = 10
LOCK_POLL_SECONDS = 0.05

MARKDOWN_TEMPLATES = {
    "journal.md": "# Journal\n",
    "world.md": "# World\n\n## People\n\n## Places\n\n## Factions\n\n## Open quests\n",
    "dm-secrets.md": (
        "# DM Secrets\n\n<!-- Player: reading this file spoils the story. -->\n\n"
        "## Seed\n\n## Campaign plan\n\n## Companion motives\n"
    ),
}

# format_version N -> function that returns the version N+1 shape. Migrations only
# add fields with safe defaults. They never delete or reinterpret a number.
MIGRATIONS = {}  # type: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]]


def _visible_entries(folder: Path) -> List[str]:
    """Names in the folder, ignoring hidden dot-files such as .DS_Store."""
    return sorted(p.name for p in folder.iterdir() if not p.name.startswith("."))


def check_write_guard(campaign_dir: Path) -> None:
    """The guard for init: only an empty folder may become a campaign."""
    if not campaign_dir.is_dir():
        raise DmError(
            "write_guard_failed",
            "%s is not a folder. Ask the player to make a new empty subfolder and open it." % campaign_dir,
        )
    entries = _visible_entries(campaign_dir)
    if PARTY_FILE in entries:
        raise DmError(
            "write_guard_failed",
            "this folder already has a party.json. Continue that campaign, or ask the player "
            "to make a new empty subfolder for a new one.",
        )
    if entries:
        raise DmError(
            "write_guard_failed",
            "the folder is not empty (found: %s). Game files must not mix with other files. "
            "Ask the player to make a new empty subfolder and open it." % ", ".join(entries[:5]),
        )


def is_owned_campaign_dir(campaign_dir: Path) -> bool:
    try:
        load_party(campaign_dir)
    except DmError:
        return False
    return True


def campaign_files() -> List[str]:
    return [PARTY_FILE, ENCOUNTER_FILE, LOG_FILE] + sorted(MARKDOWN_TEMPLATES)


def refuse_symlinks(campaign_dir: Path) -> None:
    """A save file that is a symlink would make a write land outside the campaign folder."""
    for name in campaign_files():
        if (campaign_dir / name).is_symlink():
            raise DmError("campaign_file_is_symlink",
                          "%s is a symbolic link. dm.py writes only real files inside the campaign folder. "
                          "Replace the link with the real file." % name)


@contextlib.contextmanager
def campaign_lock(campaign_dir: Path, wait_seconds: float = LOCK_WAIT_SECONDS) -> Iterator[None]:
    """One command at a time per campaign: read, change and write happen under the lock."""
    if not campaign_dir.is_dir():
        yield
        return
    lock = campaign_dir / LOCK_FILE
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(handle)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > STALE_LOCK_SECONDS:
                    lock.unlink()
                    continue
            except OSError:
                continue  # the holder released it between our two calls
            if time.monotonic() >= deadline:
                raise DmError("campaign_busy", "another dm.py command is still running on this campaign. "
                                               "Run commands one at a time, then try again.")
            time.sleep(LOCK_POLL_SECONDS)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write a new, uniquely named temp file in the same folder, flush it to disk, then swap it in.

    mkstemp creates the file exclusively, so a planted temp name or symlink is never opened.
    """
    if path.is_symlink():
        raise DmError("campaign_file_is_symlink", "%s is a symbolic link. dm.py will not write through it." % path.name)
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w") as stream:
            stream.write(json.dumps(data, indent=1, sort_keys=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        raise DmError(
            "campaign_file_damaged",
            "%s is not valid JSON (%s). Restore it from a backup, or rebuild it from log.jsonl." % (path.name, exc),
        )
    if not isinstance(data, dict):
        raise DmError("campaign_file_damaged", "%s does not hold a JSON object." % path.name)
    return data


def migrate_party(
    party: Dict[str, Any],
    migrations: Optional[Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]]] = None,
    target: Optional[int] = None,
) -> Dict[str, Any]:
    steps = MIGRATIONS if migrations is None else migrations
    goal = CURRENT_FORMAT_VERSION if target is None else target
    version = party.get("format_version")
    if not isinstance(version, int):
        raise DmError("not_a_campaign", "party.json has no format_version. It was not made by this skill.")
    if version > goal:
        raise DmError(
            "format_version_too_new",
            "this campaign was made by a newer version of the skill (format %d, this skill knows %d). "
            "Update the skill before continuing." % (version, goal),
        )
    while version < goal:
        if version not in steps:
            raise DmError("campaign_file_damaged", "no migration exists from format %d." % version)
        party = steps[version](party)
        version += 1
        party["format_version"] = version
    return party


def load_party(campaign_dir: Path) -> Dict[str, Any]:
    path = campaign_dir / PARTY_FILE
    if not path.is_file():
        raise DmError("not_a_campaign", "%s has no party.json. Run init first." % campaign_dir)
    party = _read_json(path)
    if party.get("format") != PARTY_FORMAT:
        raise DmError(
            "not_a_campaign",
            "the party.json in %s was not made by this skill. Use a new empty subfolder." % campaign_dir,
        )
    before = party.get("format_version")
    party = migrate_party(party)
    if party["format_version"] != before:
        atomic_write_json(path, party)
    return party


def save_party(campaign_dir: Path, party: Dict[str, Any]) -> None:
    atomic_write_json(campaign_dir / PARTY_FILE, party)


def load_encounter(campaign_dir: Path) -> Optional[Dict[str, Any]]:
    path = campaign_dir / ENCOUNTER_FILE
    if not path.is_file():
        return None
    return _read_json(path)


def save_encounter(campaign_dir: Path, encounter: Dict[str, Any]) -> None:
    atomic_write_json(campaign_dir / ENCOUNTER_FILE, encounter)


def delete_encounter(campaign_dir: Path) -> None:
    path = campaign_dir / ENCOUNTER_FILE
    if path.exists():
        path.unlink()


def append_log(campaign_dir: Path, entries: List[Dict[str, Any]]) -> None:
    """Append entries. seq is the 1-based line number, so no counter is stored."""
    if not entries:
        return
    path = campaign_dir / LOG_FILE
    seq = 0
    if path.is_file():
        with path.open() as handle:
            seq = sum(1 for line in handle if line.strip())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("a") as handle:
        for entry in entries:
            seq += 1
            line = {"seq": seq, "ts": stamp}
            line.update(entry)
            handle.write(json.dumps(line, separators=(",", ":")) + "\n")


def ensure_markdown_templates(campaign_dir: Path) -> List[str]:
    """Recreate a missing prose file as an empty template. Returns repair notes."""
    repairs = []
    for name in sorted(MARKDOWN_TEMPLATES):
        path = campaign_dir / name
        if not path.exists():
            path.write_text(MARKDOWN_TEMPLATES[name])
            repairs.append("%s was missing and was recreated as an empty template" % name)
    return repairs


def roll_entry(command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"command": command, "type": "roll", "payload": payload}


def change_entry(command: str, target: Optional[str], field: str, before: Any, after: Any,
                 details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {"target": target, "field": field, "before": before, "after": after}  # type: Dict[str, Any]
    if details:
        payload["details"] = details
    return {"command": command, "type": "state_change", "payload": payload}
