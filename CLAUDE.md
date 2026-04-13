# CLAUDE.md — Career Coaching Board

This file is read by Claude Code at the start of every session.
Follow these instructions for all edits to this project.

---

## Project overview

A self-contained career coaching dashboard for Cassan (career coach).
Built as a single HTML file (`index.html`) with a local Python server (`cap_server.py`).

**Purpose:** Manage coachee profiles, track 3-session coaching programmes,
generate Career Action Plans (CAPs) as PPTX, and sync data from Notion.

---

## File structure

```
coaching-board/
├── index.html              ← Entire frontend — all HTML, CSS, JS in one file
├── cap_server.py           ← Local Python server (port 5050)
├── BCG_CAP_Template.pptx   ← CAP template (NOT committed to git)
├── CLAUDE.md               ← This file
├── README.md               ← User-facing setup guide
├── .gitignore
├── push-to-github.sh       ← First-time GitHub setup
├── update-github.sh        ← Push updates to GitHub
├── notion_coachees.csv     ← Notion import file (Coachees DB)
├── notion_sessions.csv     ← Notion import file (Sessions DB)
└── notion_setup_guide.md   ← Notion setup instructions
```

---

## index.html — structure

The entire app lives in `index.html`. It is a single-page app with JS-based routing.

### CSS variables (defined in `:root`)
- `--bg`, `--surface`, `--surface2`, `--border` — backgrounds and borders
- `--text`, `--muted` — text colours
- `--accent`, `--accent-light` — green (primary brand colour)
- `--danger`, `--warn`, `--info`, `--purple` — semantic colours
- `--radius`, `--radius-sm` — border radii
- `--sidebar` — sidebar width (220px)

### Pages (each a `div.page` or `div.board-page`, hidden by default)
| Page ID | Route key | Nav index |
|---|---|---|
| `page-dashboard` | `dashboard` | 0 |
| `page-coachees` | `coachees` | 1 |
| `page-profile` | (shown via `showProfile(id)`) | 1 |
| `page-calendar` | `calendar` | 2 |
| `page-resources` | `resources` | 3 |

### Navigation
- `navigate(page)` — switches active page, highlights nav item
- `navMap` — maps page keys to nav item indices
- Always call `navigate()` rather than toggling classes directly

### Core data
- `profiles` — object keyed by coachee ID (`james`, `maya`, `tom`, `priya`, `aisha`)
  - Each profile contains all coachee fields, `sessionProgress[]`, `sessionList[]`
- `actionState` — tracks CAP checkbox state: `{coacheeId_cap1: bool, ...}`
- `todaySessions` — array of today's session data for dashboard render
- `profileResumeStore` — stores uploaded resume data URLs per profile ID
- `profileCAPStore` — stores exported CAP attachment records per profile ID
- `lastCAPJson` — the last AI-generated CAP JSON (used for PPTX export)
- `currentProfileId` — ID of the currently open profile

### Key functions
| Function | Purpose |
|---|---|
| `renderDashboard()` | Renders today's sessions + CAP due items on dashboard |
| `showProfile(id)` | Opens a coachee profile page and renders all sections |
| `generateCAP()` | Calls Anthropic API, generates CAP JSON, renders preview |
| `exportPPTX()` | POSTs CAP JSON to cap_server.py, downloads PPTX, attaches to profile |
| `syncFromNotion()` | Fetches coachee data from Notion via cap_server.py proxy, merges into profile |
| `checkNotionStatus()` | Checks if cap_server.py is running and Notion is configured |
| `renderCAPAttachments(id)` | Shows saved CAP files under the generator card |
| `toggleProfileAction(id, el)` | Toggles a CAP checkbox in the profile + re-renders dashboard |
| `toggleCAPFromDashboard(id, el)` | Toggles a CAP checkbox from the dashboard + syncs to profile |

---

## cap_server.py — structure

Local HTTP server on `http://localhost:5050`.

### Configuration constants (edit these to activate features)
```python
NOTION_TOKEN       = ""   # secret_xxx from notion.so/my-integrations
NOTION_COACHEES_DB = ""   # 32-char Notion database ID
NOTION_SESSIONS_DB = ""   # 32-char Notion database ID
MAKE_WEBHOOK_CAP_EXPORTED  = ""   # Make.com webhook URL
MAKE_WEBHOOK_STAGE_CHANGED = ""   # Make.com webhook URL
MAKE_WEBHOOK_SESSION_DONE  = ""   # Make.com webhook URL
```

### Routes
| Method | Path | Purpose |
|---|---|---|
| POST | `/generate` | Generate PPTX from CAP JSON using BCG template |
| GET | `/notion/coachee?name=X` | Fetch coachee + sessions from Notion |
| GET | `/notion/status` | Check if Notion is configured |
| OPTIONS | `*` | CORS preflight |

### Key functions
- `generate_pptx(cap_data)` — fills BCG template, returns bytes
- `fill_slide1(xml, cap)` — populates slide 1 (session summary)
- `fill_slide2(xml, cap)` — populates slide 2 (action plan timeline)
- `fetch_coachee_from_notion(name)` — queries Notion API, returns mapped profile dict
- `fire_webhook(url, payload)` — POST to Make.com webhook, silent on failure
- `notion_prop(page, name)` — safely extracts a Notion property value

---

## Coachee profile fields

Every coachee in `profiles` has these fields:

**Identity:** `initials`, `name`, `role`, `bg`, `color`, `goal`, `status`, `start`, `tags[]`

**Contact & intake:** `contact`, `email`, `employment`, `industry`, `targetTitles`, `bookingPref`, `assignedCoach`, `urgency`

**Programme:** `stage`, `progressStatus`, `outcome`, `priority`, `risks`, `s1date`, `s2date`, `s3date`

**Checklist:** `aiCoach`, `cvReceived`, `linkedinProvided`, `riasecDone`, `riasecCodes`, `careerMatch`

**GROW:** `goals`, `reality`, `options`, `wayForward`

**Sessions:** `sessionProgress[{num, label, status, title}]`, `sessionList[{date, time, title, status, next, meetUrl}]`

---

## Conventions

- **Never split into multiple files** — keep everything in `index.html` and `cap_server.py`
- **CSS variables only** — never hardcode colours; use `var(--accent)` etc.
- **No external CDN dependencies** — the dashboard must work offline (no CDN links)
- **Google Fonts** is the only external link allowed (`DM Sans` + `DM Serif Display`)
- **Fonts in use:** `DM Serif Display` for headings, `DM Sans` for body
- **Font weights:** 400 (regular) and 500 (medium) only — never 600 or 700
- **Sentence case** everywhere — no ALLCAPS labels, no Title Case in UI
- **No `<form>` tags** — use button `onclick` handlers instead
- **`cap_server.py` is Python 3.8+ stdlib only** — no pip installs required
- **BCG_CAP_Template.pptx** must never be committed to git (in `.gitignore`)
- **Notion token** must never be committed to git — it lives only in `cap_server.py`

---

## CAP (Career Action Plan) flow

1. Coach uploads session summary or pastes text into the CAP generator card
2. `generateCAP()` sends it to the Anthropic API (`claude-sonnet-4-20250514`)
3. AI returns structured JSON matching the BCG template fields
4. Preview renders inline in the dashboard
5. Coach clicks "Export PPTX" → `exportPPTX()` POSTs JSON to `cap_server.py /generate`
6. Server fills `BCG_CAP_Template.pptx` and returns the file
7. File downloads to computer AND is saved to `profileCAPStore[profileId]`
8. The attachment appears under "Saved CAPs" in the profile

---

## Notion sync flow

1. Coach opens a coachee profile → `showProfile(id)` runs
2. `checkNotionStatus()` pings `cap_server.py /notion/status`
3. Coach clicks "Sync from Notion" → `syncFromNotion()` runs
4. Dashboard calls `cap_server.py /notion/coachee?name=X`
5. Server queries Notion Coachees DB + Sessions DB
6. Returns mapped JSON → dashboard merges into `profiles[id]`
7. `showProfile(id)` re-renders with fresh data
8. Green banner confirms sync with timestamp

---

## How to run locally

```bash
# Start the server (required for Notion sync + PPTX export)
python cap_server.py

# Open the dashboard
open index.html   # Mac
start index.html  # Windows
```

## How to push to GitHub

```bash
# First time
./push-to-github.sh

# Every update
./update-github.sh "describe what changed"
```
