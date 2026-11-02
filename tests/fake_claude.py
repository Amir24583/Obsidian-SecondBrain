#!/usr/bin/env python3
"""Stand-in for `claude -p` in tests: files each pending source as one source page,
handles changed/moved/deleted, updates the index and log, writes the ingest report.
It does what CLAUDE.md asks of the AI, minus the thinking."""
import json
import re
import sys
from pathlib import Path

vault = Path.cwd()
if "Question:" in " ".join(sys.argv):
    # Query mode (sb.py eval): cite every filed source.
    state = json.loads((vault / ".brain" / "state.json").read_text(encoding="utf-8"))
    print("Answer.\nSOURCES:\n" + "\n".join(it["path"] for it in state["items"].values()))
    sys.exit(0)
batch = json.loads((vault / ".brain" / "pending.json").read_text(encoding="utf-8"))["batch"]
index = vault / "wiki" / "index.md"
items = []
for p in batch:
    slug = re.sub(r"[^a-z0-9]+", "-", p["key"].lower()).strip("-") if p["key"].startswith("raw:") \
        else re.sub(r"[^a-z0-9]+", "-", p["key"].lower()).strip("-") or "page"
    page = vault / "wiki" / "sources" / f"{slug}.md"
    rel = page.relative_to(vault).as_posix()
    if p["change"] == "deleted":
        page.unlink(missing_ok=True)
        index.write_text("\n".join(l for l in index.read_text(encoding="utf-8").splitlines()
                                   if f"[[{rel[:-3]}]]" not in l) + "\n", encoding="utf-8")
        items.append({"key": p["key"], "status": "retracted"})
        continue
    target = p["path"][:-3] if p["path"].endswith(".md") else p["path"]
    body = (vault / p["path"]).read_text(encoding="utf-8")
    page.write_text(f"---\ntype: source\ntitle: {p['title']}\nkind: note\nraw: [\"[[{target}]]\"]\n"
                    f"topics: [school]\n---\n\n{body}\n", encoding="utf-8")
    if f"[[{rel[:-3]}]]" not in index.read_text(encoding="utf-8"):
        with index.open("a", encoding="utf-8") as f:
            f.write(f"- [[{rel[:-3]}]] — {p['title']}\n")
    with (vault / "wiki" / "log.md").open("a", encoding="utf-8") as f:
        f.write(f"## [2026-11-02] ingest | {p['title']} | {p['key']}\n")
    items.append({"key": p["key"], "status": "ingested", "pages": [rel], "topics": ["school"]})
(vault / ".brain" / "ingest-report.json").write_text(json.dumps({"items": items}), encoding="utf-8")
print(f"filed {len(items)}")
