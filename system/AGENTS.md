# Using this second brain as an agent

This vault is a personal knowledge base maintained by an AI under the rules in
`CLAUDE.md`. If you are an agent working for its owner, here is how to use it.

## Reading

1. Start at `wiki/index.md`. It lists every wiki page by topic with a one-line summary.
2. Open the pages you need. Each claim links to a `wiki/sources/` page, and each
   source page links (`raw:`) to the original file. Go to the original when the
   detail matters.
3. `confidence:` in a page's frontmatter says how well supported it is. Treat
   `low` as a lead, not a fact. `## Open questions` sections list known disagreements.
4. Cite what you used: `wiki/concepts/mean-reversion.md`, or the source path.

## Writing

Don't edit `wiki/`. Record what you learned as a new Markdown file in
`raw/agents/`, and the next ingest files it into the wiki:

- Name: `raw/agents/YYYY-MM-DD-<agent>-<short-topic>.md`
- Frontmatter:
  ```yaml
  ---
  agent: <your name or role>
  date: 2026-11-02
  kind: finding | decision | lesson | source-summary
  confidence: high | medium | low
  links: []        # URLs, repo paths or wiki pages this is based on
  ---
  ```
- Body: what you found, decided or learned, and how you know. Separate verified
  facts from assumptions. One subject per file.
- A decision needs who approved it. A lesson needs what happened and what to do next time.
- Never write secrets, credentials or private details about people.

Files in `raw/` are never edited after they're written. To correct one, write a
new file that says what it supersedes.
