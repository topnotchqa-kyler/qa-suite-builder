# QA Suite Builder

Generate a comprehensive, structured QA test suite for any website — powered by Playwright crawling and Claude AI.

**Live:** [suitegen.dev](https://suitegen.dev)

## How it works

1. **Discover** — The crawler fetches the site's `sitemap.xml` to get a complete URL inventory upfront. If no sitemap is found it falls back to BFS link-following.
2. **Select** — URLs are grouped into unique pages and template families (blog posts, location pages, career listings, etc.). Only the structurally distinct pages and a small number of representatives per template are scheduled for crawling, keeping the budget focused on what matters.
3. **Crawl** — Playwright loads each selected page and extracts DOM structure, headings, form fields, button labels, navigation, API calls, and hidden content revealed by tabs and accordions.
4. **Generate** — Claude produces test cases grounded in the actual UI: real field names, real interactions, template-aware framing for repeated page types.
5. **Download** — A formatted `.xlsx` workbook with a Dashboard summary sheet and one sheet per page section.

---

## URL Discovery Strategy

### Sitemap mode (primary)

When a site has `sitemap.xml` the crawler reads it before opening any page. Sitemap index files (e.g. WordPress sites with separate `post-sitemap.xml`, `location-sitemap.xml`, etc.) are handled automatically — all child sitemaps are fetched in parallel and their filenames are used as template hints.

The result is a complete URL inventory available before the first page loads:

```json
{
  "site_architecture": {
    "total_urls_in_sitemap": 908,
    "unique_pages": 29,
    "template_families": {
      "/blog/": 80,
      "/locations/": 129,
      "/career-listings/": 479,
      "/menu-category/": 9
    },
    "pages_selected_for_crawl": 20,
    "discovery_method": "sitemap"
  }
}
```

`site_architecture` is included in all API responses so the full inventory is visible without crawling every page.

### BFS mode (fallback)

Sites without a sitemap are crawled via breadth-first link following. Navigation links are always prioritised so top-level sections are reached before content pages. BFS stops at `MAX_DEPTH` link hops from the base URL.

### Template deduplication

Both modes apply the same deduplication logic: URL paths with a slug or numeric terminal segment are identified as template instances (e.g. `/blog/spring-at-ziggis/` → template key `/blog/`). At most `MAX_TEMPLATE_REPS` representatives are crawled per family. The AI is told the page is a template representative so it writes pattern-level tests rather than tests specific to one instance.

---

## Local vs. Production

The hosted version at suitegen.dev runs on Railway, which enforces a **300-second HTTP request timeout**. The production crawler defaults are sized to complete comfortably within that window.

When running locally there is no timeout constraint, so limits can be raised freely via environment variables.

| Variable | Production default | Recommended local value | Effect |
|----------|--------------------|-------------------------|--------|
| `MAX_PAGES` | `20` | `50` | Max pages crawled per run |
| `MAX_DEPTH` | `2` | `3` | Max BFS link depth from base URL (sitemap mode ignores this) |
| `MAX_TEMPLATE_REPS` | `1` | `3` | Representatives crawled per detected template family |

Set these in `backend/.env` for local development — see `.env.example` for the exact syntax. They are never committed and are not required in Railway (defaults apply).

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

# Create .env from example and add your API key + optional higher limits
cp .env.example .env

# Start the server
python3 -m uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install Node dependencies
npm install

# Create .env.local and point it at the local backend
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
│   ├── crawler.py           # Playwright crawl + sitemap discovery
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
| `POST` | `/api/crawl` | 20/hr per IP | Crawl only — returns raw JSON including `site_architecture` |
| `POST` | `/api/generate` | 10/hr per IP | Full pipeline → `.xlsx` download |
| `POST` | `/api/generate?format=json` | 10/hr per IP | Full pipeline → JSON (skips xlsx build, fast for iteration) |
| `POST` | `/api/generate-from-crawl` | 10/hr per IP | Generate from existing crawl data |

### Request body

```json
{
  "url": "https://example.com",
  "username": null,
  "password": null
}
```

`username` and `password` are optional credentials for password-protected sites. The crawler first attempts HTTP Basic Auth, then detects and submits HTML login forms automatically.

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

## Coding Conventions

- Functional React components with hooks
- FastAPI route handlers are thin — business logic lives in service modules
- All AI generation logic lives in `generation.py`
- All crawl logic lives in `crawler.py`
- All workbook formatting lives in `xlsx_builder.py`
- Never hardcode API keys — use environment variables
