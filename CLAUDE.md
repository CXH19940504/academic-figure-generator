# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

### Backend (Python 3.12+, FastAPI)

```bash
cd backend
source .venv/bin/activate   # virtualenv at backend/.venv/
pip install -e .            # install in editable mode (includes dev deps with [dev])
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Lint & format
ruff check app/
ruff format app/

# Run tests
pytest -v                    # all tests
pytest -v tests/test_foo.py  # single test file
pytest -v -k "test_name"     # specific test
```

`pytest` is configured with `asyncio_mode = "auto"` and `testpaths = ["tests"]`.

### Frontend (React 19, Vite, TypeScript)

```bash
cd frontend
npm install
npm run dev       # dev server at localhost:8081, proxies /api/v1 -> localhost:8000
npm run build     # tsc -b && vite build
npm run lint      # ESLint
```

## Environment Variables

All config lives in `.env` at project root. The backend reads it via `pydantic-settings` (`model_config = {"env_file": ".env"}`). Key vars:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude Agent SDK (prompt generation) |
| `NANOBANANA_API_KEY` | NanoBanana/Gemini API (image generation) |
| `NANOBANANA_API_BASE` | Default `https://api.keepgo.icu` |
| `NANOBANANA_MODEL` | Default `gemini-3-pro-image-preview` |
| `DATABASE_PATH` | SQLite path, auto-derived from it if omitted |
| `DATA_DIR` | Uploads/figures storage, default `./data/` |
| `CORS_ORIGINS` | JSON list, default `["http://localhost:3000","http://localhost:8081"]` |

`config.py` auto-computes `DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"`. The config class caches via `@lru_cache`.

## Architecture

### Data Flow

```
Upload PDF/DOCX/TXT → DocumentService.parse() → structured sections
    → ClaudeCodeService (Agent SDK, sync) → figure prompts (DB)
        → ImageService (NanoBanana API, async background task) → PNG figures (local filesystem)
```

### Backend Layers

- **`app/api/v1/`** — FastAPI routers: `projects`, `documents`, `prompts`, `images`, `color_schemes`, `health`
- **`app/models/`** — SQLAlchemy async ORM models (SQLite via aiosqlite). `Base` in `models/base.py` uses UUID primary keys. Models: `Project`, `Document`, `Prompt`, `Image`, `ColorScheme`
- **`app/schemas/`** — Pydantic request/response schemas
- **`app/services/`** — Business logic:
  - `claude_code_service.py` — Calls Claude Agent SDK with `academic-figure-prompt/SKILL.md` as system prompt. Sync (blocks the HTTP handler). Returns parsed JSON array of figure prompts.
  - `document_service.py` — PDF (PyMuPDF), DOCX (python-docx), TXT parsers. Validates file type via extension + magic bytes.
  - `image_service.py` — NanoBanana/Gemini API client. Sync HTTP call wrapped in `run_in_executor`. Maps resolution tiers (1K/2K/4K) and aspect ratios to pixel dimensions.
  - `local_storage_service.py` — Filesystem storage at `{DATA_DIR}/uploads/` and `{DATA_DIR}/figures/`. Replaces MinIO from the old Docker setup.
- **`app/core/`** — Middleware (CORS + request logging), custom exception hierarchy (`AppException` → `NotFoundException`, `BadRequestException`, etc.), and prompt templates.
- **`app/dependencies.py`** — AsyncSession DI (`get_db`), engine/session factory creation. SQLite uses `check_same_thread=False`.

### Key Design Decisions

- **No auth, no Celery, no Redis, no MinIO** — This is the simplified personal-use version. Image generation runs as `asyncio.create_task()` background coroutines (fire-and-forget). The frontend polls or uses SSE (`/images/{id}/stream`) for status.
- **Prompt generation is synchronous** — The Claude Agent SDK call blocks the HTTP handler for 30–120s. No queue or timeout involved.
- **SQLite schema is auto-created** on startup via `Base.metadata.create_all` in the lifespan handler. Preset color schemes are seeded idempotently.
- **Static file serving** — Everything under `DATA_DIR` is mounted at `/data` via `StaticFiles`.
- **Frontend proxy** — Vite dev server proxies `/api/v1` to `localhost:8000`. Production would need a reverse proxy or direct same-origin deployment.

### The SKILL.md Files

The `academic-figure-prompt/SKILL.md` (and `academic-figure-prompt-pastel/SKILL.md`) are the core IP — detailed system prompts for Claude that encode figure design methodology, color theory, layout rules, and anti-patterns. `ClaudeCodeService` loads the SKILL.md at init time and injects it as `system_prompt` in the Agent SDK call. The SKILL.md is also designed to be usable standalone as a Claude Code skill via `npx skills add`.

### Frontend

- **Pages**: `Projects` (list), `ProjectWorkspace` (documents/prompts/images for a project), `Generate` (direct prompt-to-image), `ColorSchemes` (browse/manage), `Settings`
- **State**: Zustand (`projectStore.ts`) — holds current project and project list
- **API client**: Axios with base URL from `VITE_API_BASE_URL` (defaults to `/api/v1`)
- **UI**: Radix UI primitives (dialog, dropdown, select, tabs, tooltip, etc.) wrapped as components in `components/ui/`, styled with Tailwind CSS + `tailwindcss-animate`
- **Routing**: react-router-dom v7

### Database

SQLite with async access via aiosqlite. All models use UUID string primary keys and inherit from a `Base` with `created_at`/`updated_at` timestamps. Soft-delete via `status = "deleted"` on projects. Documents track parse status (`parsing` → `completed`/`failed`). Images track generation status (`pending` → `generating` → `completed`/`failed`).

### Services & External APIs

- **Claude Agent SDK** (`claude-agent-sdk`) — streaming query with `ClaudeAgentOptions`. The service streams `AssistantMessage` chunks, concatenates text, then parses JSON from the result.
- **NanoBanana API** (`api.keepgo.icu`) — OpenAI-compatible `/v1/images/generations` endpoint. Expects base64 image responses. Resolution map: 1K=1024, 2K=2048, 4K=4096 base. Actual dimensions calculated from resolution tier × aspect ratio using area-preserving math, rounded to multiples of 8.
