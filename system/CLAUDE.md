# Second brain: rules for the AI that maintains this vault

This vault is a personal knowledge base built on Andrej Karpathy's "LLM Wiki"
pattern. People and agents drop sources in; you, the AI, read them and keep a
wiki of linked pages up to date. You write the wiki. Nobody else edits it by
hand except to correct you, and when they do, keep their correction.

Read `wiki/conventions.md` before any task. It holds this vault's own decisions
(topic names, naming habits, what to skip) and overrides the defaults below.

## Layers

| Layer | Where | Who writes it |
| --- | --- | --- |
| Sources | `raw/` and `OneNote Journals/` | People, agents, the OneNote converter. **Never edit, move or delete anything here.** |
| Wiki | `wiki/` | You. |
| Rules | `CLAUDE.md` (this file), `wiki/conventions.md` | This file comes from the second-brain kit; you maintain `conventions.md`. |
| Bookkeeping | `.brain/` | `sb.py` and the ingest report. Don't edit `state.json` by hand. |

Sources:
- `OneNote Journals/<Notebook>/<Section>/<Page>.md`: OneNote pages, written by the
  OneNote → Obsidian converter on every sync. Ignore `* MOC.md` files, the
  `<!-- related:auto -->` block at the end of each page and dot-folders; those are
  the converter's navigation, not content. A page that embeds a PDF of handwriting
  may have a transcription in a collapsed callout on the page. Use it.
- `raw/inbox/`: anything a person saves (web clips, PDFs, notes, transcripts).
- `raw/agents/`: notes agents leave: findings, decisions, lessons from their work.
- `raw/assets/`: images that sources embed. Not sources on their own.

## Wiki page types

Every page under `wiki/` (except `index.md`, `log.md`, `overview.md`,
`conventions.md`) starts with frontmatter. File names are lowercase-kebab-case.

| Type | Folder | One page per | Must have |
| --- | --- | --- | --- |
| `source` | `wiki/sources/` | source (or a run of closely related short sources, like one class's notes for a week) | `raw:` link(s) to the source file(s) |
| `entity` | `wiki/entities/` | named thing: person, company, tool, library, course, dataset, project | `sources:` |
| `concept` | `wiki/concepts/` | idea, method, technique, term | `sources:` |
| `topic` | `wiki/topics/` | broad area that groups entities and concepts (the "sorting" layer) | `sources:` |
| `question` | `wiki/questions/` | answer worth keeping, comparison or synthesis | `sources:` |

```yaml
---
type: concept
title: Mean reversion
topics: ["[[quant-trading]]"]
sources: ["[[sources/2026-10-12-pairs-trading-notes]]", "[[sources/ernie-chan-ch3]]"]
updated: 2026-11-02
confidence: medium   # high = several sources agree; medium = one good source; low = inferred or disputed
---
```

Source pages use `raw: ["[[OneNote Journals/College/Biology/Cells]]"]` instead of
`sources:`, plus `kind: onenote | clip | pdf | note | agent`, `date:` (when it was
written, from the source) and `topics:`.

### Writing pages

- **Cite everything.** Each claim in an entity, concept, topic or question page
  traces back to a source page, by the `sources:` list and, for anything specific
  (a number, a quote, a decision), an inline link: `... a 2.0 z-score entry ([[sources/x]])`.
  If you can't cite it, don't write it, or mark it `(unsourced, my inference)`.
- **Merge, don't duplicate.** Search the wiki (Glob/Grep, then `wiki/index.md`)
  before creating a page. Prefer updating an existing page.
- **Contradictions are content.** When a new source disagrees with a page, keep
  both claims, cite both, add the newer one's date, and list it under
  `## Open questions`. Never silently overwrite.
- **Link densely.** Use `[[page-name]]` for every entity or concept that has a
  page; create a page when something comes up in two or more sources.
- **Keep the person's words close.** For their own notes (OneNote, inbox notes),
  summarise faithfully; don't upgrade a guess into a fact.
- **Sensitive content.** Don't copy passwords, keys, account numbers, health or
  other private details about people into the wiki. Note "contains credentials,
  not copied" on the source page.

## Sorting (topics)

Topics are how the vault sorts itself. They're derived from what's actually in
the sources, not fixed up front:

1. A new source gets 1 to 3 topics from the existing list in `wiki/index.md`.
2. If nothing fits, tag it with the closest topic and add a candidate under
   `## Candidate topics` in `wiki/conventions.md` with the source linked.
3. When a candidate has 3 or more sources, create the topic page, retag those
   sources, record the decision in `conventions.md` and the log.
4. During lint, propose merging topics that overlap heavily or splitting ones
   with more than ~40 pages. Record merges in `conventions.md` so they stick.

Starting topics (rename, merge or drop them as the corpus shows what matters):
quant-trading, markets-and-finance, cybersecurity, ai-and-ml, software-engineering,
business-ideas, school, personal.

For a large first import (more than ~30 pending sources with no topics yet), do
a taxonomy pass first: list titles and first lines of all pending sources, group
them, and write the starting topic list to `conventions.md` before filing.

## Workflows

### Ingest (`/ingest`, or automatically after a OneNote sync)

1. Get the batch: `.brain/pending.json` (refresh with `python .brain/sb.py pending`
   if you can run commands). Each item has `key`, `path` and `change`:
   - `new`: read the source; write its source page; update or create the entity,
     concept and topic pages it touches; add new pages to `wiki/index.md`.
   - `changed`: re-read the source, update its source page and anything that
     cited it (`previous_pages` lists them). Note what changed.
   - `moved`: the content is the same; update the `raw:` link and nothing else.
   - `deleted`: the source is gone. Remove its source page, remove its citations
     from other pages, and drop claims that now have no source. Report it as `retracted`.
2. Skip a source (status `skipped`, with a reason) only if it's empty, a
   duplicate of another source, or pure navigation. Short is not a reason to skip.
3. Append one line per source to `wiki/log.md`:
   `## [2026-11-02] ingest | <title> | <key>` then a line on what you changed.
4. Write `.brain/ingest-report.json`:
   ```json
   {"items": [
     {"key": "<key from pending>", "status": "ingested", "pages": ["wiki/sources/x.md", "wiki/concepts/y.md"], "topics": ["quant-trading"]},
     {"key": "...", "status": "skipped", "reason": "empty page"},
     {"key": "...", "status": "retracted"}
   ]}
   ```
   `pages` are vault-relative paths of every wiki page you created or changed for
   that source, source page first. Then run `python .brain/sb.py apply` if you
   can run commands (the automatic run does it for you).

### Query (`/query <question>`)

Read `wiki/index.md`, then the relevant pages, then the sources they cite when
the detail matters. Answer with inline citations to source pages. If the answer
is worth keeping (it took several pages to assemble, or the person asks), file
it as a `question` page and add it to the index and log.

### Lint (`/lint`)

Run `python .brain/sb.py lint` and fix what it reports (broken links,
missing frontmatter, pages missing from the index, unfiled sources). Then check
what a script can't: contradictions, stale claims that newer sources overturn,
concepts mentioned in several places without their own page, topics to merge or
split. Log what you fixed.

## index.md, log.md, overview.md

- `wiki/index.md`: the catalogue. One section per topic; under it every page in
  that topic as `- [[page]] — one-line summary`. Agents read this first, so keep
  it accurate and short.
- `wiki/log.md`: append-only record of every ingest, query filed, and lint.
  Never rewrite old entries.
- `wiki/overview.md`: a one-page picture of what this person knows and is
  working on, by topic, refreshed during lint.

## For agents using this vault

Agents (Claude Code threads, OpenClaw agents, scripts) follow `AGENTS.md`. In short:
read `wiki/index.md` first, cite wiki pages in what you produce, and record what
you learn as a new file in `raw/agents/`, never by editing the wiki directly.
