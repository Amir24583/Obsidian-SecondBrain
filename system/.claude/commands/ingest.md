---
description: File pending sources (OneNote pages, inbox, agent notes) into the wiki
---
Follow the **Ingest** workflow in CLAUDE.md.

1. Read `wiki/conventions.md` and `wiki/index.md`.
2. Run `python .brain/sb.py pending --limit 10` (or read `.brain/pending.json` if you can't run commands). $ARGUMENTS
3. If this is a large first import with no topics yet, do the taxonomy pass from CLAUDE.md first.
4. Handle each item by its `change` (new, changed, moved, deleted), writing and updating wiki pages with citations.
5. Append to `wiki/log.md`, write `.brain/ingest-report.json`, then run `python .brain/sb.py apply`.
6. Finish with a short summary: sources filed, pages created and updated, topics added, anything you skipped and why, and contradictions you found.
