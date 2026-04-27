# Paper Companion API

FastAPI backend for [paper-companion](../README.md). Deployed as Vercel Python Functions.

## Local development

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy env template and fill in values
cp .env.example .env

# Run with reload
uvicorn api.index:app --reload --port 8000
```

Open <http://localhost:8000/docs> for the Swagger UI.

## Deployment

This directory deploys as a separate Vercel project. The function entry point is `api/index.py`.

```bash
# From the api/ directory:
vercel link        # one-time
vercel             # preview deploy
vercel --prod      # production deploy
```

See [`../docs/DECISIONS.md`](../docs/DECISIONS.md) (ADR-006) for the reasoning behind Vercel Python Functions vs. Railway.

## Endpoints

| Method | Path     | Description                |
|--------|----------|----------------------------|
| GET    | /health  | Liveness probe             |
| GET    | /docs    | Swagger UI (FastAPI auto)  |

The ingest, search, and chat endpoints land in weeks 2–3 — see [`../docs/ROADMAP.md`](../docs/ROADMAP.md).
