# Claude Instructions — QA Suite Builder

## Workflow

- All feature work branches off `v2`. PRs merge back into `v2`. `v2` → `main` only when ready to ship.
- `develop` and `main` are frozen for v1 hotfixes only — no v2 work goes there.
- The user merges PRs themselves and confirms with "PR has been merged."
- After every PR merge, update `README.md` to reflect any new files, env vars, endpoints, setup steps, or behaviour changes introduced by that PR.
- After every edit session, verify with a preview screenshot and a console error check before declaring work done.

## Testing

- Add unit tests whenever introducing or modifying pure functions (no I/O, no external deps).
- Add unit tests for any security-critical logic (e.g. URL validation, JWT parsing).
- Tests live in `backend/tests/` (pytest) and `frontend/tests/` (vitest).
- Use `pytest-mock` / `unittest.mock` to mock external dependencies (Anthropic API, Supabase, Playwright) — never make real API calls in tests.
- Do not add tests for Playwright browser automation functions — the mocking cost outweighs the benefit at this stage.
- Run `pytest backend/tests/` before opening a PR if any backend Python files were changed.

## Code Style

- FastAPI route handlers stay thin — business logic belongs in service modules (`crawler.py`, `generation.py`, `storage.py`, `auth.py`, `xlsx_builder.py`).
- All React UI and styles live in `frontend/App.jsx` — inline styles in the `styles` object at the bottom of the file.
- Never hardcode API keys or secrets — use environment variables.
- Storage failures (`storage.py`) are always best-effort and must never abort generation.
- Auth is always optional — anonymous usage must continue to work without a token.

## Dev Servers

- Frontend: `npm run dev` in `frontend/` → http://localhost:3000
- Backend: `python3 -m uvicorn main:app --reload --port 8000` in `backend/`
- `launch.json` is configured — use `preview_start` (frontend) and `preview_start` (backend) via the MCP preview tool.
