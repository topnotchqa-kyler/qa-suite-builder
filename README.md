# QA Suite Builder

Generate a comprehensive, structured QA test suite for any website — powered by Playwright crawling and Claude AI.

**Live:** [suitegen.dev](https://suitegen.dev)

## How it works

1. **Crawl** — Playwright maps every reachable page: DOM structure, form fields, button labels, nav items, API calls
2. **Generate** — Claude generates test cases grounded in the actual UI (real field names, real interactions)
3. **Download** — Formatted `.xlsx` workbook with Dashboard, per-section sheets, status dropdowns, priority tags, color coding

---

## Deployment

| Service | Platform | Branch |
|---------|----------|--------|
| Frontend | Vercel ([suitegen.dev](https://suitegen.dev)) | `main` |
| Backend | Railway | `main` |

Environment variables required:

**Backend (Railway)**

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `PORT` | Set to `8000` (required — Railway routes to this port) |

**Frontend (Vercel)**

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend URL, e.g. `https://your-service.railway.app` |

---

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 18+
- An Anthropic API key

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

# Create .env.local from example
cp .env.example .env.local
# → Set VITE_API_URL=http://localhost:8000

# Start the dev server
npm run dev
# → Open http://localhost:5173
```

---

## Project Structure

```
qa-suite-builder/
├── Dockerfile               # Root Dockerfile used by Railway
├── railway.json             # Railway deploy config
├── vercel.json              # Vercel build config
├── backend/
│   ├── main.py              # FastAPI routes (thin handlers)
│   ├── crawler.py           # Playwright crawl service
│   ├── generation.py        # Anthropic AI generation service
│   ├── xlsx_builder.py      # openpyxl workbook builder
│   ├── Dockerfile           # Backend-only Dockerfile
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── App.jsx              # Main React component
    ├── main.jsx             # Entry point
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── .env.example
```

---

## API Endpoints

| Method | Path | Rate limit | Description |
|--------|------|------------|-------------|
| `GET`  | `/health` | — | Health check |
| `POST` | `/api/crawl` | 20/hr per IP | Crawl only — returns raw JSON |
| `POST` | `/api/generate` | 10/hr per IP | Full pipeline → `.xlsx` download |
| `POST` | `/api/generate-from-crawl` | 10/hr per IP | Generate from existing crawl data |

### Request body (`/api/generate`)

```json
{
  "url": "https://example.com",
  "username": null,
  "password": null
}
```

`username` and `password` are optional HTTP Basic Auth credentials for password-protected sites.

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

## Security

- **SSRF protection** — user-supplied URLs are validated before crawling; private IP ranges, loopback addresses, and cloud metadata endpoints are blocked
- **Rate limiting** — per-IP request limits enforced on all generation endpoints
- **No credentials stored** — API keys and auth credentials are never persisted

---

## Configuration

Crawler limits (editable in `crawler.py`):

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_PAGES` | `15` | Max pages crawled per run |
| `MAX_DEPTH` | `2` | Max link depth from base URL |

---

## Coding conventions

- Functional React components with hooks
- FastAPI route handlers are thin — business logic lives in service modules
- All AI generation logic lives in `generation.py`
- All crawl logic lives in `crawler.py`
- All workbook formatting lives in `xlsx_builder.py`
- Never hardcode API keys — use environment variables
