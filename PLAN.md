# PLAN.md — ContextKeeper

## Overview
AI-powered Knowledge & Task Management Platform that captures meeting context, tracks action items, transfers knowledge, and provides intelligent catch-up briefs.

---

## Architecture

```
contextkeeper/
  app/
    main.py               # FastAPI app factory, middleware, routers
    config.py             # pydantic-settings, env only
    logging_config.py     # structlog, redaction, request-id contextvar
    middleware.py         # request-id, logging middleware
    db/
      __init__.py
      base.py             # SQLAlchemy base
      session.py          # engine, SessionLocal, get_db
      models.py           # all ORM models
    schemas/
      __init__.py
      people.py
      meetings.py
      items.py
      kb.py
      ai.py
      common.py
    routers/
      __init__.py
      people.py
      meetings.py
      items.py
      kb.py
      ai.py
      admin.py
    services/
      people.py
      meetings.py
      items.py
      carry_forward.py
      kb.py
      risk.py
      nudges.py
    ai/
      base.py             # AIProvider interface
      runner.py           # retries, timeout, JSON-repair, ai_runs logging
      fallback.py         # deterministic heuristic extraction
      providers/
        mock.py
        gemini.py
        anthropic.py
        openai.py
      prompts/            # versioned .md template files
        recap_v1.md
        catchup_v1.md
        kb_link_v1.md
        nudge_v1.md
        reassign_v1.md
      tasks/
        recap.py
        catchup.py
        kb_link.py
        nudge.py
        reassign.py
    templates/            # Jinja2
    static/               # CSS, JS
    seed.py
  tests/
  migrations/
  README.md  PLAN.md  Dockerfile  docker-compose.yml  .env.example  Makefile
```

---

## Data Model

### People
- `id`, `name`, `email`, `role`, `availability` (`available|on_leave`), `leave_start`, `leave_end`, `created_at`

### Meetings
- `id`, `title`, `type` (`meeting|handover`), `status` (`draft|scheduled|in_progress|completed|archived|cancelled`), `scheduled_at`, `agenda`, `raw_notes`, `summary`, `decisions`, `open_questions`, `risks`, `ai_generated`, `ai_run_id`, `created_at`, `updated_at`, `version`

### Participants
- `id`, `meeting_id`, `person_id`, `rsvp` (`invited|accepted|declined|no_response|attended|absent`)

### ActionItems
- `id`, `title`, `description`, `owner_id`, `due_date`, `status` (`open|in_progress|blocked|done|cancelled`), `priority` (`low|medium|high|critical`), `source_meeting_id`, `current_meeting_id`, `outcome`, `resolution_type` (`completed|dropped|superseded|deferred`), `carry_forward_count`, `ai_generated`, `ai_run_id`, `confidence`, `source_quote`, `created_at`, `closed_at`, `updated_at`, `version`

### ItemHistory (append-only)
- `id`, `item_id`, `event_type` (`created|reassigned|status_changed|carried_forward|due_date_changed|outcome_recorded`), `actor_id`, `old_value`, `new_value`, `timestamp`

### KBDocuments
- `id`, `title`, `content`, `doc_type`, `file_path`, `fts_content`, `created_at`, `updated_at`

### KBLinks
- `id`, `meeting_id`, `item_id`, `kb_doc_id`, `relevance_score`, `reason`, `accepted`, `ai_run_id`, `created_at`

### AIRuns
- `id`, `feature`, `provider`, `model`, `prompt_version`, `latency_ms`, `status` (`success|retry|fallback|error`), `prompt_tokens`, `completion_tokens`, `error_type`, `request_id`, `created_at`

---

## API List

### People
- `GET /api/people` — list all
- `POST /api/people` — create
- `GET /api/people/{id}` — get
- `PUT /api/people/{id}` — update (availability, role)
- `DELETE /api/people/{id}` — soft delete

### Meetings
- `GET /api/meetings` — list (filter: type, status, participant, date)
- `POST /api/meetings` — create
- `GET /api/meetings/{id}` — get with full detail
- `PUT /api/meetings/{id}` — update
- `POST /api/meetings/{id}/transition` — lifecycle transition
- `GET /api/meetings/{id}/participants` — list
- `POST /api/meetings/{id}/participants` — add participant + RSVP
- `PUT /api/meetings/{id}/participants/{person_id}` — update RSVP/attendance
- `POST /api/meetings/{id}/carry-forward` — carry open items to new meeting
- `POST /api/meetings/{id}/agenda-autopilot` — AI-proposed agenda

### Action Items
- `GET /api/items` — list (filter: owner, status, due_date, meeting)
- `POST /api/items` — create
- `GET /api/items/{id}` — get with history
- `PUT /api/items/{id}` — update (optimistic concurrency)
- `POST /api/items/{id}/close` — close with outcome (required)
- `POST /api/items/{id}/reassign` — reassign owner
- `GET /api/items/{id}/history` — full history

### AI
- `POST /api/ai/recap` — generate recap from raw input (returns draft, not committed)
- `POST /api/ai/recap/commit` — commit reviewed recap (idempotency key)
- `POST /api/ai/catchup` — generate catch-up brief
- `POST /api/ai/kb-link` — link meeting/item to KB docs
- `POST /api/ai/nudge` — draft nudge message
- `POST /api/ai/reassign-suggest` — suggest reassignment

### Knowledge Base
- `GET /api/kb` — list docs
- `POST /api/kb` — upload/create doc
- `GET /api/kb/{id}` — get doc
- `PUT /api/kb/{id}/links/{link_id}` — accept/reject AI link
- `GET /api/kb/search` — FTS5 search

### Risk
- `GET /api/risk` — radar: all items with risk scores + signals

### Admin
- `GET /admin/logs` — recent log tail (token protected)
- `GET /admin/ai-runs` — recent AI runs (token protected)

### System
- `GET /healthz` — health check

---

## Milestone Order

| # | Milestone | Key outputs |
|---|-----------|-------------|
| 1 | Skeleton + config + logging + request-ID middleware | `main.py`, `config.py`, `logging_config.py`, `middleware.py`, `/healthz` |
| 2 | DB models + migrations + people/meetings/items services | All models, Alembic setup, CRUD APIs |
| 3 | Lifecycle + carry-forward + validation | Transitions, history, carry-forward, close-requires-outcome |
| 4 | AI runner + providers + mock + recap | `runner.py`, `mock.py`, `recap.py`, `/api/ai/recap` |
| 5 | Catch-up brief + KB + linking | `catchup.py`, KB CRUD, FTS5, `kb_link.py` |
| 6 | Risk Radar + nudges + agenda autopilot | `risk.py`, `nudge.py`, `/api/risk` |
| 7 | UI (Jinja2 + HTMX + Alpine.js + Tailwind) | All 8 screens, responsive, accessible |
| 8 | Seed data + tests | `seed.py`, pytest suite |
| 9 | Docs + Docker + deploy config | README, Dockerfile, render.yaml, Makefile |

---

## Assumptions

1. SQLite WAL mode; Postgres-portable schema via `DATABASE_URL`.
2. Single-process deployment (no Celery); AI calls are synchronous per-request with timeout.
3. No real email sending; nudge messages are copy-to-clipboard only (SMTP behind `SMTP_ENABLED` flag).
4. Auth is out of scope; admin routes protected by `ADMIN_TOKEN` env var only.
5. Embeddings: TF-IDF/BM25 candidate retrieval + LLM rerank (no separate embedding API required).
6. File upload limited to `.txt`, `.md`, `.pdf`, `.docx`; max 10 MB.
7. PDF/DOCX text extraction via `pypdf2`/`python-docx`; best-effort.

