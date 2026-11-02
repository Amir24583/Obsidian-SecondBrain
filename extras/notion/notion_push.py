#!/usr/bin/env python3
"""
notion_push.py — push a single Obsidian markdown note to Notion as a new page.

One-way, on demand: run it when you decide to *share* a note. Obsidian stays the
source of truth; this just publishes a copy.

Setup (see docs/sync-setup.md):
  1. Create an integration:  https://www.notion.so/my-integrations
  2. Share your target Notion page with that integration (page ••• → Connections).
  3. Create a .env file next to this repo root:
        NOTION_TOKEN=secret_xxx
        NOTION_PARENT_PAGE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  4. pip install -r scripts/requirements.txt

Usage:
    python scripts/notion_push.py "obsidian-vault/03-Resources/My Note.md"

This is intentionally minimal — it maps headings, paragraphs, bullets, and
numbered lists. It does NOT resolve [[wikilinks]] (Notion has no equivalent) —
they're pushed as plain text. Extend map_block() for more markdown features.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency 'requests'. Run: pip install -r scripts/requirements.txt")

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"


def load_env() -> tuple[str, str]:
    """Read NOTION_TOKEN and NOTION_PARENT_PAGE_ID from environment or .env."""
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
    token = os.environ.get("NOTION_TOKEN")
    parent = os.environ.get("NOTION_PARENT_PAGE_ID")
    if not token or not parent:
        sys.exit(
            "Set NOTION_TOKEN and NOTION_PARENT_PAGE_ID (in .env or your shell).\n"
            "See docs/sync-setup.md → Option C."
        )
    return token, parent


def strip_frontmatter(text: str) -> tuple[str, str]:
    """Return (title_guess, body) — drops YAML frontmatter, finds an H1 title."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    lines = text.splitlines()
    title = "Untitled"
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = i + 1
            break
    return title, "\n".join(lines[body_start:]).strip()


def rich_text(content: str) -> list[dict]:
    """Notion rich_text array. Wikilinks are flattened to plain text."""
    content = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", content)  # [[a|b]] -> b
    content = re.sub(r"\[\[([^\]]+)\]\]", r"\1", content)             # [[a]]   -> a
    return [{"type": "text", "text": {"content": content[:2000]}}] if content else []


def map_block(line: str) -> dict | None:
    """Map one markdown line to a Notion block. Returns None for blank lines."""
    stripped = line.strip()
    if not stripped:
        return None
    for level, prefix in ((3, "### "), (2, "## "), (1, "# ")):
        if stripped.startswith(prefix):
            return {"object": "block", "type": f"heading_{level}",
                    f"heading_{level}": {"rich_text": rich_text(stripped[len(prefix):])}}
    if re.match(r"^[-*]\s+\[[ xX]\]\s+", stripped):  # task
        checked = stripped[stripped.index("[") + 1] in "xX"
        body = re.sub(r"^[-*]\s+\[[ xX]\]\s+", "", stripped)
        return {"object": "block", "type": "to_do",
                "to_do": {"rich_text": rich_text(body), "checked": checked}}
    if re.match(r"^[-*]\s+", stripped):  # bullet
        return {"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": rich_text(stripped[2:])}}
    if re.match(r"^\d+\.\s+", stripped):  # numbered
        return {"object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": rich_text(re.sub(r'^\d+\.\s+', '', stripped))}}
    if stripped.startswith("> "):  # quote
        return {"object": "block", "type": "quote",
                "quote": {"rich_text": rich_text(stripped[2:])}}
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": rich_text(stripped)}}


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/notion_push.py <path-to-note.md>")
    note_path = Path(sys.argv[1])
    if not note_path.exists():
        sys.exit(f"Note not found: {note_path}")

    token, parent = load_env()
    title, body = strip_frontmatter(note_path.read_text(encoding="utf-8"))

    blocks = [b for b in (map_block(l) for l in body.splitlines()) if b]
    blocks = blocks[:100]  # Notion caps children per create request

    payload = {
        "parent": {"page_id": parent},
        "properties": {"title": {"title": rich_text(title)}},
        "children": blocks,
    }
    resp = requests.post(
        f"{API}/pages",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 300:
        sys.exit(f"❌ Notion API error {resp.status_code}: {resp.text}")

    url = resp.json().get("url", "(page created)")
    print(f"✅ Pushed '{title}' to Notion:\n   {url}")


if __name__ == "__main__":
    main()
