# Recover — Payment Failure Recovery Engine

Smart retry and dunning system for failed subscription payments. Classifies Stripe decline codes, schedules intelligent retries, and tracks recovered revenue.

## The Problem

Subscription businesses lose **5–15% of revenue** to failed payments — expired cards, insufficient funds, bank declines. Blind retries waste API calls and annoy customers. Ignoring soft declines leaves money on the table.

## What This Does

1. **Ingests** failed payment webhooks from Stripe
2. **Classifies** decline codes as hard vs soft vs retryable
3. **Schedules** smart retries with exponential backoff tuned per decline type
4. **Tracks** recovery rate, revenue saved, and attempt history

## Architecture

```
Stripe Webhook → Decline Classifier → Retry Engine → Scheduler
                                              ↓
                                         PostgreSQL
                                              ↓
                                      Dashboard API
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for dashboard)

### 1. Start infrastructure (optional — SQLite works out of the box)

```bash
docker compose up -d   # PostgreSQL + Redis
```

Without Docker, the backend defaults to SQLite — no setup needed.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed_demo_data.py
uvicorn app.main:app --reload --port 8000
```

### 3. Dashboard

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — API docs at http://localhost:8000/docs

### 4. Stripe webhooks (optional)

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Set `STRIPE_WEBHOOK_SECRET` in `backend/.env` from the CLI output.

## Key Concepts (for interviews)

| Concept | Implementation |
|---------|----------------|
| Decline classification | Hard vs soft vs retryable per Stripe/network codes |
| Retry backoff | 1d → 3d → 7d for soft declines; shorter for `insufficient_funds` |
| Idempotency | Webhook event IDs deduplicated in DB |
| Max retries | Configurable per decline type; hard declines skip retry |
| Recovery metric | `(recovered_amount / failed_amount) * 100` |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/metrics` | Recovery stats, revenue saved |
| GET | `/api/payments` | Failed & recovered payments |
| GET | `/api/payments/{id}` | Payment detail + retry history |
| POST | `/webhooks/stripe` | Stripe webhook receiver |
| POST | `/api/simulate/failure` | Demo: simulate a failed payment |

## Project Structure

```
backend/
  app/
    models/          # SQLAlchemy models
    services/        # Decline classifier, retry engine
    api/             # REST routes
    webhooks/        # Stripe webhook handler
  alembic/           # DB migrations
  scripts/           # Seed data
frontend/
  src/               # React dashboard
```

## License

MIT
