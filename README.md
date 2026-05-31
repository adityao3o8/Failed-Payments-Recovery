# Recover

**Payment recovery SaaS for subscription businesses.** Automatically retry failed Stripe charges, send dunning emails, and track recovered revenue.

![Recover product dashboard](https://img.shields.io/badge/status-demo-green)
![Python](https://img.shields.io/badge/backend-FastAPI-34d399)
![React](https://img.shields.io/badge/frontend-React-60a5fa)

## Product

Recover is a B2B fintech product that helps SaaS companies reduce involuntary churn from failed payments:

| Feature | Description |
|---------|-------------|
| **Smart retries** | Classifies Stripe decline codes and schedules optimal retry timing |
| **Dunning emails** | Notifies customers when charges fail, before the next retry |
| **Recovery dashboard** | Real-time metrics, activity feed, and 7-day trend chart |
| **Retry rules** | Configurable recovery strategy (conservative / balanced / aggressive) |
| **Stripe integration** | Webhook ingestion with idempotent event processing |
| **Multi-tenant** | Workspace-scoped data model (merchant accounts) |

## Demo

1. **Landing page** — http://localhost:5173
2. **Product dashboard** — http://localhost:5173/app
3. **API docs** — http://localhost:8000/docs

## Quick start

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed_demo_data.py
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

> **Note:** Re-seed after pulling updates: `python scripts/seed_demo_data.py` (recreates the database schema).

## Architecture

```
                    ┌─────────────┐
  Stripe Webhooks ─►│   Recover   │
                    │   Backend   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        Decline       Retry Engine   Activity
        Classifier                      Log
              │            │            │
              └────────────┼────────────┘
                           ▼
                      PostgreSQL
                           │
                           ▼
                   React Product UI
              (Landing + Dashboard)
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/workspace` | Current merchant workspace |
| `GET /api/metrics` | Recovery KPIs |
| `GET /api/metrics/chart` | 7-day trend data |
| `GET /api/activity` | Activity feed |
| `GET /api/payments` | Failed/recovered payments |
| `GET /api/retry-policy` | Decline rules + strategy |
| `PATCH /api/workspace` | Update dunning / retry settings |
| `POST /webhooks/stripe` | Stripe webhook receiver |

## License

MIT
