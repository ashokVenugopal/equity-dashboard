# Equity Dashboard

Personal equity dashboard for Indian markets. Bloomberg-terminal aesthetic, built on top of the equity-experiments ecosystem.

## Architecture

- **Backend**: Python FastAPI at `backend/` — thin API over equity-shared views/queries
- **Frontend**: Next.js 14 (App Router, SSR) at `frontend/` — dark theme, monospace, GSAP scrolling
- **Data**: Read-only SQLite connection to `equity-experiments-2/data/pipeline/facts.sqlite3`
- **Observations**: Separate SQLite at `data/observations.sqlite3` (read-write)

## Key Conventions

- All data queries go through `equity-shared` views (`best_facts_*`, `best_prices`, `best_technicals`). Never query raw `facts` table.
- Cell formatting rules (money/percent/ratio/volume) are defined in `backend/core/formatting.py` and mirrored in `frontend/src/lib/formatters.ts`.
- Logging follows flight recorder pattern: step announcements, progress counters, summaries. See `project_guidelines.md`.
- Tests: pytest, `test_<function>_<scenario>` naming, no network calls, in-memory SQLite fixtures.
- Observation logging uses upsert on `data_point_ref` for idempotency.

## Running

```bash
# Backend
cd backend && pip install -r requirements.txt && pip install -e ../../equity-shared
python main.py

# Frontend
cd frontend && npm install && npm run dev

# Both
make dev

# Tests
make test
```

## Related Projects

All under `equity-experiments/`:
- `equity-shared` — Schema, views, queries, concepts, rules (pip-installable)
- `equity-experiments-2` — Data pipeline (downloaders, parsers, calculators, CLI)
- `equity-chatbased-interface` — Chainlit chatbot with LangGraph agent
