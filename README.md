# Second Brain

An Obsidian vault that sorts itself. You, your agents and the
[OneNote → Obsidian converter](https://github.com/Amir24583/Onenote-SecondBrain)
drop sources in; Claude Code reads them and keeps a linked wiki up to date, so
both you and your agents can find and build on what you've learned.

It follows Andrej Karpathy's "LLM Wiki" pattern: raw sources that are never
edited, a wiki the AI writes, and a rules file (`CLAUDE.md`) that says how.

## How it fits together

```
OneNote ──converter──▶ OneNote Journals/ ─┐
web clips, PDFs, notes ──▶ raw/inbox/ ────┼──▶ /ingest (Claude Code) ──▶ wiki/  ◀── you and your agents read
agents' findings ──────▶ raw/agents/ ─────┘                                      index.md first
```

- **Sources** (`raw/`, `OneNote Journals/`) are read-only to the AI.
- **The wiki** (`wiki/`) has one page per source, plus entity, concept, topic
  and question pages. Every claim cites the source page it came from.
- **Sorting** is by topics the AI derives from your sources: it starts from a
  short list and creates, merges or splits topics as evidence builds up
  (recorded in `wiki/conventions.md`).
- **Bookkeeping** (`.brain/sb.py`) tracks which sources are filed, by OneNote
  page ID where the converter provides one, so edits, moves and deletes in
  OneNote flow through to the wiki.

## Setup

Needs Python 3.9+, Obsidian and [Claude Code](https://claude.com/claude-code).

```
python setup.py --vault "C:\Users\you\Documents\Second Brain" --converter "C:\Users\you\Documents\OneNote2Obsidian"
```

or double-click `Setup.bat`. This creates the vault (or adds to an existing
one), installs the rules and tools, and, with `--converter`, points the
converter at this vault and makes every sync file new pages automatically.
Re-run it to update; your notes, wiki and filing records are kept.

## Daily use

In Claude Code, opened in the vault folder:

| Command | What it does |
| --- | --- |
| `/ingest` | File everything new, changed, moved or deleted into the wiki |
| `/query <question>` | Answer from the wiki with citations; optionally file the answer |
| `/lint` | Fix broken links, uncited claims, missing index entries; merge or split topics |

Without opening Claude Code:

| Command | What it does |
| --- | --- |
| `python .brain/sb.py status` | Filed, skipped and pending counts |
| `python .brain/sb.py auto` | File everything pending (runs Claude Code headless in batches of 10) |
| `python .brain/sb.py lint` | Consistency check and source reconciliation |
| `python .brain/sb.py eval` | Ask the questions in `evals/questions.md`, check each answer cites the right source |
| `python .brain/sb.py agreement` | Compare your own sorting (`evals/my-sorting.csv`) with the AI's |

For sources you drop into `raw/inbox/`, schedule `.brain/after-sync.bat`
(Windows Task Scheduler) or `.brain/after-sync.sh` (cron) to run hourly or daily.

## How you know it's working

- `sb.py lint` reconciles every source: filed, skipped with a reason, or pending.
  Nothing disappears silently.
- Running `sb.py auto` again with no new sources changes no files.
- `sb.py eval` checks answers against sources you chose, not the AI's opinion of itself.
- `sb.py agreement` scores the AI's sorting against yours on a sample you label.

## Agents

Agents read `AGENTS.md` in the vault: start at `wiki/index.md`, cite pages, and
write findings, decisions and lessons as new files in `raw/agents/`. They never
edit the wiki directly; the next ingest files their notes.

## Layout

| Path | What |
| --- | --- |
| `system/` | Installed into the vault on every setup: `CLAUDE.md`, `AGENTS.md`, `.claude/` commands and permissions, `.brain/` tools |
| `vault/` | Copied into the vault only if missing: `Home.md`, wiki skeleton, `raw/`, templates, eval files |
| `extras/notion/` | Optional: push a note to Notion for sharing |
| `tests/` | `python -m unittest discover tests` |
