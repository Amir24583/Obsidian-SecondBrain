---
description: Health-check the wiki and fix what's wrong
---
Follow the **Lint** workflow in CLAUDE.md.

1. Run `python .brain/sb.py lint` and fix every error it reports. Fix warnings unless there's a reason not to.
2. Then check what the script can't: contradictions between pages, claims newer sources overturn, concepts that deserve their own page, topics to merge or split (record decisions in `wiki/conventions.md`).
3. Refresh `wiki/overview.md`.
4. Log what you did in `wiki/log.md`, and run the lint again to confirm it's clean.
