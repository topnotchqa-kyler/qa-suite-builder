# QA Suite Builder

Generate a comprehensive, structured QA test suite for any website — powered by Playwright crawling and Claude AI.

**Live:** [suitegen.dev](https://suitegen.dev)

## How it works

1. **Discover** — The crawler fetches the site's `sitemap.xml` to get a complete URL inventory upfront. If no sitemap is found it falls back to BFS link-following.
2. **Select** — URLs are grouped into unique pages and template families (blog posts, location pages, career listings, etc.). Only the structurally distinct pages and a small number of representatives per template are scheduled for crawling, keeping the budget focused on what matters.
3. **Crawl** — Playwright loads each selected page and extracts DOM structure, headings, form fields, button labels, navigation, API calls, and hidden content revealed by tabs and accordions.
4. **Review** — The site architecture card shows total URLs, template families, and pages selected before generation begins. You can inspect what was found and decide whether to proceed.
5. **Generate** — Claude produces test cases grounded in the actual UI: real field names, real interactions, template-aware framing for repeated page types.
6. **Browse & export** — Test cases are displayed inline, grouped by page section, with expandable detail panels. A shareable link and `.xlsx` download are available from the viewer.

### Two-step UI flow

```
[Enter URL + API key] → Crawl → [Architecture card + "Generate" button]
                                          ↓
                               Generate → [Inline test suite viewer]
                                                    ↓
                                         Browse · Copy link · Download .xlsx
```

The crawl and generation steps run separately so you can inspect the site architecture before spending API credits on generation.

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

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | ✅ | Set to `8000` — Railway routes to this port |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key (bypasses RLS) |
| `SUPABASE_ENV` | ✅ | `production` in Railway, `development` locally — stamps every saved row |
| `ANTHROPIC_API_KEY` | Optional | Fallback API key for local dev. In production users supply their own key via the UI |

**Frontend (Vercel)**

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | ✅ | Backend URL, e.g. `https://your-service.railway.app` |

### Supabase setup

Create a free [Supabase](https://supabase.com) project and run the following migration in the SQL editor:

```sql
create table test_suites (
  id           uuid primary key default gen_random_uuid(),
  created_at   timestamptz not null default now(),
  base_url     text not null,
  site_name    text not null default '',
  environment  text not null default 'production',
  crawl_data   jsonb not null,
  test_suite   jsonb not null
);

create index on test_suites (created_at desc);
create index on test_suites (environment);
```

Use the **service role** key (not the anon key) so the backend can write without RLS getting in the way.

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

# Create .env from example — fill in Supabase keys + optional higher limits
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
│   ├── storage.py           # Supabase persistence (save / get / list suites)
│   ├── xlsx_builder.py      # openpyxl workbook builder
│   ├── Dockerfile           # Backend-only Dockerfile
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── App.jsx              # Main React component (all UI + inline styles)
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
| `POST` | `/api/generate-from-crawl` | 10/hr per IP | Generate from existing crawl data → `.xlsx` download |
| `POST` | `/api/generate-from-crawl?format=json` | 10/hr per IP | Generate from existing crawl data → JSON (used by inline viewer) |
| `GET`  | `/api/suites` | — | List the 20 most recent saved suites (metadata only) |
| `GET`  | `/api/suites/{id}` | — | Fetch a saved suite by UUID — returns `crawl_data` + `test_suite` |
| `GET`  | `/api/suites/{id}/xlsx` | — | Build and download `.xlsx` for a saved suite — no AI call |

### Request body (`/api/crawl`, `/api/generate`)

```json
{
  "url": "https://example.com",
  "username": null,
  "password": null
}
```

`username` and `password` are optional credentials for password-protected sites. The crawler first attempts HTTP Basic Auth, then detects and submits HTML login forms automatically.

### API key

Generation endpoints require an Anthropic API key. Pass it in the `X-Api-Key` request header. The backend falls back to the `ANTHROPIC_API_KEY` environment variable for local development.

In the UI, the key is entered once per session — it lives only in React state and is never written to localStorage or sent to any server other than the Anthropic API.

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

## Shareable links

After generation completes the browser URL updates to `/?suite=<uuid>`. Anyone with that link can open the same test suite without re-crawling or re-generating — the suite is loaded directly from Supabase.

The inline viewer includes a **Copy link** button for sharing. The `.xlsx` download for a saved suite is instant (no AI call) because it rebuilds the workbook from the stored `test_suite` JSON.

---

## Security

- **SSRF protection** — user-supplied URLs are validated before crawling; private IP ranges, loopback addresses, and cloud metadata endpoints are blocked
- **Rate limiting** — per-IP request limits enforced on all generation endpoints
- **User-supplied API keys** — Anthropic API keys are entered by the user and sent only to the Anthropic API via the `X-Api-Key` header. Keys are never written to any storage — they live only in browser memory for the duration of the session
- **No auth credentials stored** — `username`/`password` fields for protected sites are used only during the crawl and are never persisted

---

## Coding Conventions

- Functional React components with hooks
- FastAPI route handlers are thin — business logic lives in service modules
- All AI generation logic lives in `generation.py`
- All crawl logic lives in `crawler.py`
- All workbook formatting lives in `xlsx_builder.py`
- All Supabase persistence lives in `storage.py` — storage failures are best-effort and never abort generation
- Never hardcode API keys — use environment variables
