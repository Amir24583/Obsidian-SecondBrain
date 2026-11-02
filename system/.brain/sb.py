#!/usr/bin/env python3
"""
sb.py — bookkeeping for the second brain, so the AI does the thinking and this
script does the counting.

The vault follows Andrej Karpathy's "LLM Wiki" pattern:
  raw/ and "OneNote Journals/"   sources, never edited by the AI
  wiki/                          pages the AI writes and maintains
  CLAUDE.md                      the rules the AI follows

This script tracks which sources have been filed into the wiki, keyed by a
stable ID (OneNote's page ID from the converter's manifest, or "raw:<path>"),
and checks that the wiki is consistent. It never calls an AI itself except in
`auto` and `eval`, which run the Claude Code CLI.

Commands:
  pending   [--limit N]   list sources that are new, changed, moved or deleted
                          since they were last filed; writes .brain/pending.json
  apply     [REPORT]      record what an ingest run did, from .brain/ingest-report.json
  status                  counts: filed, skipped, pending
  lint      [--strict]    check links, frontmatter, sources and the index;
                          reconcile every source against the filing records
  auto      [--batch N] [--rounds N] [--dry-run]
                          file everything pending by running Claude Code headless
  eval      [--model M]   ask the wiki every question in evals/questions.md and
                          check the answer cites the expected source
  agreement               compare your own sorting (evals/my-sorting.csv) with the AI's

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parent
VAULT = Path(os.environ.get("SECOND_BRAIN_VAULT") or BRAIN.parent).resolve()
RAW = VAULT / "raw"
ONENOTE = VAULT / "OneNote Journals"
ON_MANIFEST = ONENOTE / ".onenote-manifest.json"
WIKI = VAULT / "wiki"
STATE_FILE = BRAIN / "state.json"
PENDING_FILE = BRAIN / "pending.json"
REPORT_FILE = BRAIN / "ingest-report.json"
EVALS = VAULT / "evals"

# wiki pages that are bookkeeping rather than knowledge: no frontmatter rules
SPECIAL = {"index.md", "log.md", "overview.md", "conventions.md", "README.md"}
PAGE_TYPES = {"source", "entity", "concept", "topic", "question"}
RELATED = re.compile(r"<!-- related:auto:start -->.*?<!-- related:auto:end -->\n?", re.DOTALL)
WIKILINK = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


# --- small helpers -------------------------------------------------------------

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def rel(p: Path) -> str:
    return p.relative_to(VAULT).as_posix()


def frontmatter(text: str) -> dict[str, str]:
    """Flat `key: value` frontmatter. Lists stay as their raw text."""
    m = FRONTMATTER.match(text.replace("\r\n", "\n"))
    out: dict[str, str] = {}
    if not m:
        return out
    key = None
    for line in m.group(1).split("\n"):
        if re.match(r"^[A-Za-z_][\w-]*:", line):
            key, _, val = line.partition(":")
            key = key.strip()
            out[key] = val.strip()
        elif key and line.startswith((" ", "-")):
            out[key] += "\n" + line          # block list item
    return out


def fm_list(value: str) -> list[str]:
    """Items of a frontmatter list, inline `[a, b]` or block `- a`."""
    value = value.strip()
    if value.startswith("["):
        inner = value.strip("[]")
        items = re.findall(r'"[^"]*"|\'[^\']*\'|[^,]+', inner)
    else:
        items = [l.strip()[1:] for l in value.split("\n") if l.strip().startswith("-")]
    return [i.strip().strip('"\'').strip() for i in items if i.strip().strip('"\'').strip()]


# --- sources ------------------------------------------------------------------

def onenote_sources() -> dict[str, dict]:
    """OneNote pages from the converter's manifest (or a folder scan without one)."""
    out: dict[str, dict] = {}
    manifest = read_json(ON_MANIFEST, None)
    if manifest and isinstance(manifest.get("pages"), list):
        for p in manifest["pages"]:
            key = p["id"] if p.get("id_source") == "onenote" else f"onenote:{p['path']}"
            out[key] = {"key": key, "kind": "onenote", "path": f"OneNote Journals/{p['path']}",
                        "title": p.get("title"), "sha256": p["sha256"]}
        return out
    if not ONENOTE.exists():
        return out
    for f in sorted(ONENOTE.rglob("*.md")):
        parts = f.relative_to(ONENOTE).parts
        if f.name.endswith(" MOC.md") or f.name == "README.md" or any(x.startswith(".") for x in parts):
            continue
        body = RELATED.sub("", f.read_text(encoding="utf-8", errors="replace")).replace("\r\n", "\n").rstrip() + "\n"
        key = f"onenote:{'/'.join(parts)}"
        out[key] = {"key": key, "kind": "onenote", "path": rel(f), "title": f.stem,
                    "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}
    return out


def raw_sources() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not RAW.exists():
        return out
    for f in sorted(RAW.rglob("*")):
        parts = f.relative_to(RAW).parts
        if not f.is_file() or f.name in ("README.md", ".gitkeep") or any(x.startswith(".") for x in parts):
            continue
        if parts[0] == "assets":           # images etc. that sources embed; not sources themselves
            continue
        key = f"raw:{'/'.join(parts)}"
        out[key] = {"key": key, "kind": "raw", "path": rel(f), "title": f.stem,
                    "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    return out


def all_sources() -> dict[str, dict]:
    return {**onenote_sources(), **raw_sources()}


def load_state() -> dict:
    state = read_json(STATE_FILE, {})
    state.setdefault("version", 1)
    state.setdefault("items", {})
    return state


def rekey(state: dict, sources: dict[str, dict]) -> bool:
    """A page tracked by path gets its OneNote ID once the converter can read IDs:
    carry its filing record over to the new key instead of re-filing it."""
    items = state["items"]
    by_path = {it.get("path"): k for k, it in items.items() if k not in sources}
    changed = False
    for key, src in sources.items():
        old_key = by_path.get(src["path"])
        if key not in items and old_key:
            items[key] = items.pop(old_key)
            changed = True
    return changed


def compute_pending(state: dict) -> list[dict]:
    if rekey(state, all_sources()):
        write_json(STATE_FILE, state)
    items = state["items"]
    out = []
    for key, src in all_sources().items():
        old = items.get(key)
        if old is None:
            out.append({**src, "change": "new"})
        elif old.get("sha256") != src["sha256"]:
            out.append({**src, "change": "changed", "previous_pages": old.get("pages", [])})
        elif old.get("path") != src["path"]:
            out.append({**src, "change": "moved", "previous_path": old.get("path"),
                        "previous_pages": old.get("pages", [])})
    current = set(all_sources())
    for key, old in items.items():
        if key not in current and old.get("status") in ("ingested", "skipped"):
            out.append({"key": key, "kind": old.get("kind"), "path": old.get("path"),
                        "title": old.get("title"), "change": "deleted",
                        "previous_pages": old.get("pages", [])})
    order = {"deleted": 0, "moved": 1, "changed": 2, "new": 3}
    out.sort(key=lambda p: (order[p["change"]], p.get("path") or ""))
    return out


# --- commands -----------------------------------------------------------------

def cmd_pending(args) -> int:
    pending = compute_pending(load_state())
    batch = pending[: args.limit] if args.limit else pending
    write_json(PENDING_FILE, {"generated_at": now(), "total": len(pending), "batch": batch})
    if args.json:
        print(json.dumps({"total": len(pending), "batch": batch}, indent=1, ensure_ascii=False))
        return 0
    print(f"{len(pending)} pending ({len(batch)} in this batch, written to .brain/pending.json)")
    for p in batch:
        print(f"  [{p['change']:>7}] {p['path']}   key={p['key']}")
    return 0


def cmd_apply(args) -> int:
    report_path = Path(args.report) if args.report else REPORT_FILE
    report = read_json(report_path, None)
    if not report or not isinstance(report.get("items"), list):
        print(f"No report at {report_path}. The ingest run writes it when it finishes.")
        return 1
    state = load_state()
    sources = all_sources()
    applied, problems = 0, []
    for r in report["items"]:
        key, status = r.get("key"), r.get("status")
        if status not in ("ingested", "skipped", "retracted"):
            problems.append(f"{key}: unknown status {status!r}")
            continue
        if status == "retracted":
            state["items"].pop(key, None)
            applied += 1
            continue
        src = sources.get(key)
        if src is None:
            problems.append(f"{key}: not a current source (wrong key?)")
            continue
        pages = [p for p in r.get("pages", []) if p]
        missing = [p for p in pages if not (VAULT / p).exists()]
        if missing:
            problems.append(f"{key}: report lists pages that don't exist: {', '.join(missing)}")
            continue
        if status == "ingested" and not pages:
            problems.append(f"{key}: marked ingested but lists no wiki pages")
            continue
        if status == "skipped" and not r.get("reason"):
            problems.append(f"{key}: skipped without a reason")
            continue
        state["items"][key] = {
            "status": status, "kind": src["kind"], "path": src["path"], "title": src.get("title"),
            "sha256": src["sha256"], "pages": pages, "topics": r.get("topics", []),
            "reason": r.get("reason"), "at": now(),
        }
        applied += 1
    write_json(STATE_FILE, state)
    report_path.rename(report_path.with_name(f"ingest-report.{dt.datetime.now():%Y%m%d-%H%M%S}.applied.json"))
    print(f"Recorded {applied} item(s).")
    for p in problems:
        print(f"  not recorded: {p}")
    return 1 if problems else 0


def cmd_status(args) -> int:
    state = load_state()
    counts: dict[str, int] = {}
    for it in state["items"].values():
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    pending = compute_pending(state)
    by_change: dict[str, int] = {}
    for p in pending:
        by_change[p["change"]] = by_change.get(p["change"], 0) + 1
    wiki_pages = len([p for p in WIKI.rglob("*.md")]) if WIKI.exists() else 0
    print(f"Sources filed: {counts.get('ingested', 0)}, skipped: {counts.get('skipped', 0)}, "
          f"pending: {len(pending)} {by_change if by_change else ''}")
    print(f"Wiki pages: {wiki_pages}")
    return 0


def vault_targets() -> tuple[set[str], set[str]]:
    """Everything a [[link]] can point at: vault paths without .md, and bare names."""
    paths, names = set(), set()
    for f in VAULT.rglob("*"):
        if not f.is_file() or any(x.startswith(".") for x in f.relative_to(VAULT).parts):
            continue
        r = rel(f)
        for form in {r, r[:-3] if r.endswith(".md") else r}:
            # Obsidian also resolves partial paths like [[sources/x]]: add every suffix.
            parts = form.lower().split("/")
            for i in range(len(parts)):
                paths.add("/".join(parts[i:]))
        names.add(f.name.lower())
        names.add(f.stem.lower() if f.suffix == ".md" else f.name.lower())
    return paths, names


def resolves(target: str, paths: set[str], names: set[str]) -> bool:
    t = target.strip().lower()
    return t in paths or t in names or t.removesuffix(".md") in paths


def cmd_lint(args) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    if not WIKI.exists():
        print("No wiki/ folder.")
        return 1
    paths, names = vault_targets()
    index = WIKI / "index.md"
    index_links: set[str] = set()
    for t in (WIKILINK.findall(index.read_text(encoding="utf-8")) if index.exists() else []):
        t = t.strip().lower().removesuffix(".md")
        index_links |= {t, t.rsplit("/", 1)[-1]}
    if not index.exists():
        errors.append("wiki/index.md is missing")
    if not (WIKI / "log.md").exists():
        errors.append("wiki/log.md is missing")

    for f in sorted(WIKI.rglob("*.md")):
        r = rel(f)
        text = f.read_text(encoding="utf-8", errors="replace")
        for target in WIKILINK.findall(text):
            if not resolves(target, paths, names):
                errors.append(f"{r}: broken link [[{target}]]")
        if (f.name in SPECIAL and f.parent == WIKI) or f.name == "README.md":
            continue
        fm = frontmatter(text)
        ptype = fm.get("type", "").strip()
        if ptype not in PAGE_TYPES:
            errors.append(f"{r}: frontmatter 'type' must be one of {sorted(PAGE_TYPES)}")
            continue
        if ptype == "source":
            raw = fm_list(fm.get("raw", "")) or ([fm["raw"]] if fm.get("raw") else [])
            targets = [m for v in raw for m in (WIKILINK.findall(v) or [v])]
            if not targets:
                errors.append(f"{r}: source page has no 'raw' link to what it summarises")
            for t in targets:
                if not resolves(t, paths, names):
                    errors.append(f"{r}: raw source not found: {t}")
        else:
            srcs = fm_list(fm.get("sources", ""))
            if not srcs:
                errors.append(f"{r}: no 'sources' (every claim must trace back to a source page)")
            for s in srcs:
                for t in (WIKILINK.findall(s) or [s]):
                    if not resolves(t, paths, names):
                        errors.append(f"{r}: source not found: {t}")
        stem, path_noext = f.stem.lower(), r[:-3].lower()
        if not ({stem, path_noext, path_noext.removeprefix("wiki/")} & index_links):
            warnings.append(f"{r}: not listed in wiki/index.md")

    # reconcile: every source accounted for, every filing record points at real pages
    state = load_state()
    pending = compute_pending(state)
    for p in pending:
        (errors if args.strict else warnings).append(f"unfiled source ({p['change']}): {p['path']}")
    for key, it in state["items"].items():
        for page in it.get("pages", []):
            if not (VAULT / page).exists():
                errors.append(f"filing record {key} points at a missing page: {page}")

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error:   {e}")
    sources = all_sources()
    filed = sum(1 for k in sources if k in state["items"])
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s). "
          f"Reconciliation: {len(sources)} sources = {filed} filed or skipped + "
          f"{len(sources) - filed} not yet.")
    return 1 if errors else 0


def claude_cmd() -> str | None:
    return os.environ.get("CLAUDE_BIN") or shutil.which("claude")


INGEST_PROMPT = (
    "Run the ingest workflow from CLAUDE.md (details in .claude/commands/ingest.md) on the "
    "items in .brain/pending.json, batch only. When finished, write .brain/ingest-report.json "
    "as described there. Don't run sb.py yourself: this automatic run records the report "
    "and lints afterwards. Do not edit anything under raw/ or 'OneNote Journals/'."
)
ALLOWED = "Read,Write,Edit,Glob,Grep"


def cmd_auto(args) -> int:
    claude = claude_cmd()
    rounds = 0
    while rounds < args.rounds:
        state = load_state()
        pending = compute_pending(state)
        if not pending:
            print("Nothing pending. The wiki is up to date.")
            if rounds:
                print("\nChecking the wiki after this run:")
                cmd_lint(argparse.Namespace(strict=False))
            return 0
        batch = pending[: args.batch]
        write_json(PENDING_FILE, {"generated_at": now(), "total": len(pending), "batch": batch})
        print(f"Round {rounds + 1}: {len(pending)} pending, filing {len(batch)}.")
        if args.dry_run:
            for p in batch:
                print(f"  [{p['change']:>7}] {p['path']}")
            return 0
        if not claude:
            print("Claude Code CLI not found (install it, or set CLAUDE_BIN). Run /ingest in Claude Code instead.")
            return 1
        REPORT_FILE.unlink(missing_ok=True)
        cmd = [claude, "-p", INGEST_PROMPT, "--permission-mode", "acceptEdits", "--allowedTools", ALLOWED]
        if args.model:
            cmd += ["--model", args.model]
        r = subprocess.run(cmd, cwd=VAULT, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            print(f"Claude Code exited with code {r.returncode}; stopping.")
            return 1
        if not REPORT_FILE.exists():
            print("The ingest run didn't write .brain/ingest-report.json; stopping so nothing loops.")
            return 1
        if cmd_apply(argparse.Namespace(report=None)) != 0:
            print("Some items weren't recorded (see above); they'll be retried next time.")
        if len(compute_pending(load_state())) >= len(pending):
            print("No progress this round; stopping.")
            return 1
        rounds += 1
    print(f"Stopped after {rounds} round(s); run again to continue.")
    return 0


QUESTION = re.compile(r"^\s*-\s*Q:\s*(.+?)\s*\|\s*expect:\s*(.+?)\s*$")


def cmd_eval(args) -> int:
    """evals/questions.md lines: `- Q: <question> | expect: <path fragment>[, <another>]`"""
    qfile = EVALS / "questions.md"
    text = re.sub(r"<!--.*?-->", "", qfile.read_text(encoding="utf-8"), flags=re.DOTALL) if qfile.exists() else ""
    questions = [m.groups() for line in text.splitlines() if (m := QUESTION.match(line))]
    if not questions:
        print("No questions in evals/questions.md (format: '- Q: question | expect: source path').")
        return 1
    claude = claude_cmd()
    if not claude:
        print("Claude Code CLI not found (install it, or set CLAUDE_BIN).")
        return 1
    passed, rows = 0, []
    for q, expect in questions:
        prompt = (f"Answer from the wiki only, following .claude/commands/query.md, but do not file the "
                  f"answer. Question: {q}\nEnd with a line 'SOURCES:' then one cited raw source path per line.")
        cmd = [claude, "-p", prompt, "--allowedTools", "Read,Glob,Grep"]
        if args.model:
            cmd += ["--model", args.model]
        out = subprocess.run(cmd, cwd=VAULT, capture_output=True, text=True, encoding="utf-8",
                             stdin=subprocess.DEVNULL).stdout
        cited = out.split("SOURCES:", 1)[1].lower() if "SOURCES:" in out else ""
        wanted = [e.strip().lower() for e in expect.split(",") if e.strip()]
        ok = bool(cited) and all(w in cited for w in wanted)
        passed += ok
        rows.append({"question": q, "expect": expect, "pass": ok, "cited": cited.strip()[:500]})
        print(f"{'PASS' if ok else 'FAIL'}  {q}")
    write_json(EVALS / f"results-{dt.datetime.now():%Y%m%d-%H%M%S}.json", rows)
    print(f"\n{passed}/{len(questions)} answered with the expected source.")
    return 0 if passed == len(questions) else 1


def cmd_agreement(args) -> int:
    """evals/my-sorting.csv columns: path,topic (your own call on where a source belongs)."""
    f = EVALS / "my-sorting.csv"
    if not f.exists():
        print("No evals/my-sorting.csv (columns: path,topic).")
        return 1
    by_path = {it["path"].lower(): it for it in load_state()["items"].values()}
    agree = total = 0
    with f.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            path, topic = (row.get("path") or "").strip().lower(), (row.get("topic") or "").strip().lower()
            if not path or not topic:
                continue
            it = by_path.get(path)
            if it is None:
                print(f"not filed yet: {row['path']}")
                continue
            ai = [t.lower().strip("[]") for t in it.get("topics", [])]
            total += 1
            hit = any(topic == t or topic in t or t in topic for t in ai)
            agree += hit
            if not hit:
                print(f"differs: {row['path']}  you: {row['topic']}  AI: {', '.join(it.get('topics', [])) or '-'}")
    if not total:
        print("No rows matched filed sources.")
        return 1
    print(f"\nAgreement: {agree}/{total} = {agree / total:.0%}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Second brain bookkeeping")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pending"); p.add_argument("--limit", type=int, default=10); p.add_argument("--json", action="store_true")
    p = sub.add_parser("apply"); p.add_argument("report", nargs="?")
    sub.add_parser("status")
    p = sub.add_parser("lint"); p.add_argument("--strict", action="store_true", help="unfiled sources are errors")
    p = sub.add_parser("auto"); p.add_argument("--batch", type=int, default=10); p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--model")
    p = sub.add_parser("eval"); p.add_argument("--model")
    sub.add_parser("agreement")
    args = ap.parse_args(argv)
    return {"pending": cmd_pending, "apply": cmd_apply, "status": cmd_status, "lint": cmd_lint,
            "auto": cmd_auto, "eval": cmd_eval, "agreement": cmd_agreement}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
