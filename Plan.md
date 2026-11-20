# Plan.md — Unified Node.js Frontend, SQLite DB, Auth & FastAPI Backend

## Architecture Overview
- **Database (`scripts/db.py` → `data/ai_finance.db`):** SQLite database with `users`, `sessions`, and `financial_plans` tables. Seeds default user (`username: "user"`, `password: "password"`, PBKDF2-SHA256 salted hash) and an initial sample plan on startup.
- **Backend API (`scripts/server.py`, FastAPI + Uvicorn on `127.0.0.1:8787`):**
  - `GET /` (service status JSON — resolves `{"detail":"Not Found"}`), `GET /health`, `GET /docs`
  - Auth: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
  - Plans CRUD & PDF: `GET/POST /plans`, `GET/PUT/DELETE /plans/{id}`, `GET /plans/{id}/pdf`
  - Direct PDF: `GET /demo`, `GET /demo-data`, `POST /generate`
- **Unified Node.js Frontend (`frontend/`, port `3000`):**
  - `frontend/server.js` serves static SPA files (`index.html`, `styles.css`, `app.js`) and reverse-proxies `/api/*` to the FastAPI backend (`http://127.0.0.1:8787` locally or `http://api:8787` in Docker).
  - Provides login (`user` / `password`), saved plans management, live score/metric dashboard, interactive form + JSON editor, and one-click PDF preview/download.
- **Launcher & Docker:**
  - `start.sh` starts both FastAPI (`8787`) and Node.js frontend (`3000`) with clean Ctrl+C shutdown (`--docker` starts both via `docker compose`).
  - `docker-compose.yml` + `frontend/Dockerfile` wire `api` and `frontend` with persistent `./data` SQLite volume.

## Execution Phases
1. **Phase 1 — Database Layer:** Create `scripts/db.py` with schema, PBKDF2 password hashing, default `user`/`password` seeding, session management, and plan CRUD.
2. **Phase 2 — FastAPI Backend:** Update `scripts/server.py` with `GET /`, auth routes, plan CRUD + PDF routes, and DB health check.
3. **Phase 3 — Unified Node.js Frontend:** Create `frontend/package.json`, `frontend/server.js`, `frontend/Dockerfile`, and `frontend/public/{index.html,styles.css,app.js}`.
4. **Phase 4 — Launcher, Docker & Docs:** Update `start.sh`, `docker-compose.yml`, and `AGENTS.md`.
5. **Phase 5 — Thorough E2E Testing:** Expand `tests/test_e2e.py` to test DB, Auth, CRUD, PDF rendering, and live Node.js-to-FastAPI proxying end-to-end, then run the full suite.
