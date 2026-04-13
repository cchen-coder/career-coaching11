# Career Coaching Board

A self-contained career coaching dashboard built for Cassan.

## Files

| File | Purpose |
|---|---|
| `index.html` | Main dashboard — open this in your browser |
| `cap_server.py` | Local Python server for PPTX export + Notion sync |
| `BCG_CAP_Template.pptx` | Your CAP template (add this manually — not committed) |
| `notion_coachees.csv` | Notion import file — Coachees database |
| `notion_sessions.csv` | Notion import file — Sessions database |
| `notion_setup_guide.md` | Step-by-step Notion setup instructions |

## Quick start

1. Open `index.html` in your browser — the dashboard runs immediately
2. For Notion sync + PPTX export, start the local server:
   ```
   python cap_server.py
   ```
3. Configure Notion credentials in `cap_server.py`:
   ```python
   NOTION_TOKEN       = "secret_xxxx"
   NOTION_COACHEES_DB = "your-db-id"
   NOTION_SESSIONS_DB = "your-db-id"
   ```

## Requirements

- Python 3.8+
- `BCG_CAP_Template.pptx` placed in the same folder as `cap_server.py`
- Notion integration token from notion.so/my-integrations

## Notes

- `BCG_CAP_Template.pptx` is excluded from the repo (add to `.gitignore`)
- `cap_server.py` runs on `http://localhost:5050`
- The dashboard works fully offline — the server is only needed for Notion sync and PPTX export
