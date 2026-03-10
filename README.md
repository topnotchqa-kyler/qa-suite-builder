# QA Suite Builder

Generate a comprehensive, structured QA test suite for any website — powered by Playwright crawling and Claude AI.

## How it works

1. **Crawl** — Playwright maps every reachable page: DOM structure, form fields, button labels, nav items, API calls
2. **Generate** — Claude generates test cases grounded in the actual UI (real field names, real interactions)
3. **Download** — Formatted `.xlsx` workbook with Dashboard, per-section sheets, status dropdowns, priority tags, color coding

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- An Anthropic API key

---

### Backend

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Create .env from example
cp .env.example .env
# → Edit .env and add your ANTHROPIC_API_KEY

# Start the server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install Node dependencies
npm install

# Start the dev server
npm run dev
# → Open http://localhost:3000
```

---

## Project Structure

```
qa-suite-builder/
├── backend/
│   ├── main.py          # FastAPI routes (thin handlers)
│   ├── crawler.py       # Playwright crawl service
│   ├── generation.py    # Anthropic AI generation service
│   ├── xlsx_builder.py  # openpyxl workbook builder
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
│   ├── App.jsx      # Main React component
│   └── main.jsx     # Entry point
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Health check |
| `POST` | `/api/crawl` | Crawl only — returns raw JSON |
| `POST` | `/api/generate` | Full pipeline → `.xlsx` download |
| `POST` | `/api/generate-from-crawl` | Generate from existing crawl data |

### Request body (`/api/generate`)

```json
{
  "url": "https://example.com",
  "username": null,
  "password": null
}
```

---

## Output Format

The `.xlsx` workbook contains:

- **Dashboard sheet** — summary, stats table with COUNTIF formulas per status/section
- **Per-section sheets** — one per crawled page, with columns:
  - ID, Title, Description, Preconditions, Steps, Expected Result
  - **Status** — dropdown: Not Run / Pass / Fail / Blocked / In Progress
  - **Priority** — dropdown: Critical / High / Medium / Low
  - **Category** — Functional / UI / Form Validation / Navigation / API / etc.
- Color-coded status and priority cells
- Frozen header rows

---

## Configuration

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required) |

Crawler limits (editable in `crawler.py`):
- `MAX_PAGES = 30` — max pages crawled per run
- `MAX_DEPTH = 3` — max link depth from base URL

---

## Coding conventions

- Functional React components with hooks
- FastAPI route handlers are thin — business logic lives in service modules
- All AI generation logic lives in `generation.py`
- All crawl logic lives in `crawler.py`
- All workbook formatting lives in `xlsx_builder.py`
- Never hardcode API keys — use environment variables
