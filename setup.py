#!/usr/bin/env python3
"""
setup.py — create or update a second-brain vault, and optionally connect the
OneNote → Obsidian converter to it.

    python setup.py --vault "C:\\Users\\you\\Documents\\Second Brain"
    python setup.py --vault "..." --converter "C:\\Users\\you\\Documents\\OneNote2Obsidian"

- vault/ files (Home.md, wiki skeleton, raw/, Templates, evals) are copied only if
  they don't exist yet, so your notes and wiki are never overwritten. Works on an
  existing Obsidian vault too.
- system/ files (CLAUDE.md, AGENTS.md, .claude/, .brain/ tools) are the kit's own
  and are replaced on every run, so re-running setup is how you update. Your
  filing records (.brain/state.json) and wiki/conventions.md are kept.
- --converter points the converter at this vault and sets its after-sync command,
  so every OneNote sync is filed into the wiki automatically.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def copy_tree(src: Path, dst: Path, overwrite: bool) -> tuple[int, int]:
    written = kept = 0
    for f in sorted(src.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        target = dst / f.relative_to(src)
        if target.exists() and not overwrite:
            kept += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        written += 1
    return written, kept


def connect_converter(converter: Path, vault: Path) -> None:
    settings = converter / "settings.ps1"
    if not (converter / "scripts" / "common.ps1").exists():
        sys.exit(f"{converter} doesn't look like the OneNote converter folder (no scripts\\common.ps1).")
    lines = settings.read_text(encoding="utf-8-sig").splitlines() if settings.exists() else \
        ["# Written by Setup.bat - re-run it to change. Read by scripts\\common.ps1."]
    lines = [l for l in lines if not l.lstrip().lower().startswith(("$vaultpath", "$aftersync"))]
    q = lambda s: s.replace("'", "''")
    after = f'"{vault / ".brain" / "after-sync.bat"}"'
    lines += [f"$VaultPath = '{q(str(vault))}'", f"$AfterSync = '{q(after)}'"]
    # UTF-8 with BOM: Windows PowerShell 5.1 reads a BOM-less file as ANSI.
    settings.write_text("\ufeff" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"Converter connected: it now syncs into {vault} and files new pages after each sync.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--vault", required=True, help="vault folder (created if missing)")
    ap.add_argument("--converter", help="OneNote converter folder to connect")
    args = ap.parse_args()
    vault = Path(args.vault).expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    w1, k1 = copy_tree(ROOT / "vault", vault, overwrite=False)
    w2, _ = copy_tree(ROOT / "system", vault, overwrite=True)
    print(f"Vault: {vault}")
    print(f"  {w1} starter file(s) added, {k1} already there and kept; {w2} system file(s) installed.")
    if args.converter:
        connect_converter(Path(args.converter).expanduser().resolve(), vault)
    print("\nNext:")
    print(f"  1. Open {vault} in Obsidian (Open folder as vault).")
    print(f"  2. Open Claude Code in that folder and run /ingest, or: python .brain/sb.py auto")
    if not args.converter:
        print("  3. To file OneNote syncs automatically, re-run with --converter <converter folder>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
