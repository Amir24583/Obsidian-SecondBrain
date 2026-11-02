# Notion structure — the sharing layer

Notion is **not** your main brain here — Obsidian is. Notion's job is the stuff Obsidian is bad at: **sharing pages, real-time collaboration, structured databases with views, and access from any browser**. Build only what you'll actually share.

> This is a blueprint to build by hand in Notion — it takes about 15 minutes. If you'd rather automate pushing notes across, see `scripts/notion_push.py` and `sync-setup.md`.

---

## Top-level structure

Create one **workspace teamspace or top page** called `Second Brain`, with these sub-pages:

```
Second Brain (page)
├── 📥 Shared Inbox            (page — quick capture from phone/web)
├── 🎯 Projects               (database)
├── 🌱 Areas                  (database)
├── 📚 Resources / Reading    (database)
├── 📄 PDF Library            (database)
└── 🌐 Published Notes        (pages you share publicly)
```

The databases below mirror your PARA folders so mental models match across tools.

---

## Database 1 — Projects

| Property | Type | Notes |
|---|---|---|
| Name | Title | |
| Status | Select | `Active`, `On hold`, `Done` |
| Area | Relation → Areas | |
| Deadline | Date | |
| Priority | Select | `High`, `Med`, `Low` |
| Next action | Text | |
| Link (Obsidian) | URL | `obsidian://` deep link back to the canonical note |

**Views:** Board by Status · Calendar by Deadline · Table filtered to `Active`.

## Database 2 — Areas

| Property | Type | Notes |
|---|---|---|
| Name | Title | |
| Standard | Text | What "good" looks like |
| Review cadence | Select | `Weekly`, `Monthly`, `Quarterly` |
| Projects | Relation → Projects | |

## Database 3 — Resources / Reading

| Property | Type | Notes |
|---|---|---|
| Title | Title | |
| Type | Select | `Article`, `Book`, `Video`, `Course`, `PDF` |
| Topic | Multi-select | e.g. `ML`, `Finance` |
| Status | Select | `To read`, `Reading`, `Done` |
| Rating | Select | ⭐ 1–5 |
| Source URL | URL | |
| My notes | Text / page | Short takeaway (the deep note stays in Obsidian) |

**Views:** Board by Status (a reading pipeline) · Gallery by Topic.

## Database 4 — PDF Library

| Property | Type | Notes |
|---|---|---|
| Title | Title | |
| File | Files & media | Upload the actual PDF if you want it in the cloud |
| Author | Text | |
| Pages | Number | |
| Topic | Multi-select | |
| Summary | Text | Auto-fillable from `pdf_index.py` output |
| Read? | Checkbox | |

This is your **cloud-accessible, searchable PDF list** — Notion full-text-searches uploaded PDFs, so you can find and read them from any browser or your phone. (Your *local* copy + literature notes still live in Obsidian.)

---

## How the two tools stay in sync mentally

| Obsidian (source of truth) | Notion (sharing layer) |
|---|---|
| `01-Projects/` folder | Projects database |
| `02-Areas/` folder | Areas database |
| `03-Resources/` folder | Resources database |
| `PDFs/` folder + `_PDF-Index.md` | PDF Library database |
| Zettelkasten | *(stays in Obsidian — rarely shared)* |

Only push a note to Notion when you specifically want to **share or collaborate**. Everything else stays local. See `sync-setup.md` for the mechanics.
