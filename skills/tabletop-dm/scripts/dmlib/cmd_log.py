"""beat and recent: the fast save point, and the way back in after a break.

journal.md is the story, written by the DM at scene changes. That leaves a gap: play that happened
after the last journal line is lost if the session ends without a Stop. A beat is one quick append
to log.jsonl, and recent shows a returning DM everything the log holds, with a flag on whatever is
newer than the journal.
"""
import argparse
import calendar
import random
import time
from pathlib import Path
from typing import Any, Dict, List

from . import io_campaign, party_ops
from .errors import DmError

DEFAULT_RECENT = 25
MAX_RECENT = 200
MAX_VALUE_TEXT = 60
PLAY_TYPES = ("roll", "beat")


def beat(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    io_campaign.load_party(campaign_dir)
    text = party_ops.clean_text(args.text, "--text", party_ops.MAX_HOOK)
    if not text:
        raise DmError("illegal_text", "--text is empty. Say in one line what just changed.")
    io_campaign.append_log(campaign_dir, [{"command": "beat", "type": "beat", "payload": {"text": text}}])
    return {"saved": text}


def _epoch(stamp: str) -> float:
    return float(calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")))


def _short(value: Any) -> str:
    if isinstance(value, dict):
        return "{...}"
    if isinstance(value, list):
        return "[%d items]" % len(value)
    text = str(value)
    return text if len(text) <= MAX_VALUE_TEXT else text[:MAX_VALUE_TEXT] + "..."


def _describe(entry: Dict[str, Any]) -> Dict[str, str]:
    payload = entry.get("payload", {})
    if entry.get("type") == "beat":
        return {"kind": "beat", "text": payload.get("text", "")}
    if entry.get("type") == "roll":
        parts = [str(payload.get("who") or "").strip(), str(payload.get("kind") or ""),
                 "%s = %s" % (payload.get("expr", "?"), payload.get("total", "?"))]
        if payload.get("result"):
            parts.append(str(payload["result"]))
        if payload.get("reason"):
            parts.append("(%s)" % payload["reason"])
        return {"kind": "roll", "text": " ".join(p for p in parts if p)}
    field = str(payload.get("field", ""))
    if field.startswith("secret_trackers."):
        # The name of a secret counter is a spoiler. Show that one moved, and its value, never its name.
        return {"kind": "change", "text": "a secret counter: %s -> %s" % (_short(payload.get("before")), _short(payload.get("after")))}
    target = payload.get("target") or ""
    return {"kind": "change", "text": "%s %s %s: %s -> %s" % (entry.get("command", ""), target, field,
                                                               _short(payload.get("before")), _short(payload.get("after")))}


def _read_log(campaign_dir: Path) -> List[Dict[str, Any]]:
    import json

    path = campaign_dir / io_campaign.LOG_FILE
    if not path.is_file():
        return []
    rows = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue  # one torn line must not hide the rest of the log
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _journal_time(campaign_dir: Path) -> float:
    journal = campaign_dir / "journal.md"
    return journal.stat().st_mtime if journal.is_file() else 0.0


def _after_journal(entry: Dict[str, Any], journal_time: float) -> bool:
    try:
        return entry.get("type") in PLAY_TYPES and _epoch(entry["ts"]) > journal_time
    except (KeyError, ValueError):
        return False


def unjournaled_count(campaign_dir: Path) -> int:
    """How many rolls and beats are newer than journal.md: play the story file does not cover."""
    journal_time = _journal_time(campaign_dir)
    return len([e for e in _read_log(campaign_dir) if _after_journal(e, journal_time)])


def recent(args: argparse.Namespace, skill_root: Path, rng: random.Random) -> Dict[str, Any]:
    campaign_dir = Path(args.campaign)
    io_campaign.load_party(campaign_dir)
    if not 1 <= args.n <= MAX_RECENT:
        raise DmError("illegal_value", "--n must be 1 to %d." % MAX_RECENT)
    rows = _read_log(campaign_dir)
    journal_time = _journal_time(campaign_dir)
    events = []
    for entry in rows[-args.n:]:
        event = {"seq": entry.get("seq"), "ts": entry.get("ts")}  # type: Dict[str, Any]
        event.update(_describe(entry))
        event["after_journal"] = _after_journal(entry, journal_time)
        events.append(event)
    unjournaled = len([e for e in rows if _after_journal(e, journal_time)])
    out = {"events": events, "log_lines": len(rows), "unjournaled": unjournaled,
           "journal_written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(journal_time))}  # type: Dict[str, Any]
    if unjournaled:
        out["warning"] = ("%d rolls or beats happened after the journal was last written. The journal does not cover "
                          "them. Tell the player what your notes end on, read these events, and ask what happened "
                          "in that gap before you narrate anything." % unjournaled)
    return out
