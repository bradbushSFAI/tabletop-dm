#!/usr/bin/env python3
"""Builds the two release files into dist/.

  tabletop-dm-plugin.zip   plugin.json + skills/        install in Cowork or Claude Code
  tabletop-dm-skill.zip    tabletop-dm/                 add as a bare skill in Cowork

Neither file holds tests, docs, playtests, or caches. Standard library only.
"""
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterator, Tuple

REPO_ROOT = Path(__file__).resolve().parent
SKILL_NAME = "tabletop-dm"
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {".DS_Store"}
SKIP_SUFFIXES = {".pyc"}


def _files(folder: Path) -> Iterator[Path]:
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if SKIP_DIRS & set(path.parts) or path.name in SKIP_FILES or path.suffix in SKIP_SUFFIXES:
            continue
        yield path


def _write_zip(target: Path, entries: Iterator[Tuple[Path, str]]) -> None:
    with zipfile.ZipFile(str(target), "w", zipfile.ZIP_DEFLATED) as zf:
        for source, name in entries:
            zf.write(str(source), name)


def build(out_dir: Path) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = REPO_ROOT / "skills" / SKILL_NAME
    plugin_zip = out_dir / (SKILL_NAME + "-plugin.zip")
    skill_zip = out_dir / (SKILL_NAME + "-skill.zip")

    def plugin_entries() -> Iterator[Tuple[Path, str]]:
        # marketplace.json makes the GitHub repo installable. An uploaded plugin must not carry it.
        manifest = REPO_ROOT / ".claude-plugin" / "plugin.json"
        yield manifest, manifest.relative_to(REPO_ROOT).as_posix()
        for path in _files(REPO_ROOT / "skills"):
            yield path, path.relative_to(REPO_ROOT).as_posix()

    def skill_entries() -> Iterator[Tuple[Path, str]]:
        for path in _files(skill_dir):
            yield path, (Path(SKILL_NAME) / path.relative_to(skill_dir)).as_posix()

    _write_zip(plugin_zip, plugin_entries())
    _write_zip(skill_zip, skill_entries())
    return {"plugin": plugin_zip, "skill": skill_zip}


if __name__ == "__main__":
    for kind, path in build(REPO_ROOT / "dist").items():
        print("%s: %s (%d KB)" % (kind, path, path.stat().st_size // 1024))
    sys.exit(0)
