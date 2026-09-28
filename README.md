# The Development League

Official website for The Development League (Free Fire esports): standings, match
results, player stats and, above all, team rotation study.

Monorepo layout (grows step by step):

- `backend/` Django + DRF + Celery (Python 3.11+)
- `frontend/` Next.js + Tailwind (coming later)
- `infra/` Docker and deployment (coming later)

## Backend: running locally

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build      # Postgres, Redis, API, worker
docker compose -f infra/docker-compose.yml exec web python manage.py createsuperuser
```

The API is on http://localhost:8000/api/v1 and Django admin on http://localhost:8000/admin
(create a season, stage and match day there before confirming uploads).

## Backend: running the tests

Tests need PostgreSQL (`DATABASE_URL`, default `postgres://tdl:tdl@localhost:5432/tdl`).

```bash
cd backend
python -m pip install -e ".[dev]"
pytest
```

## Uploading matches (staff API)

1. `POST /api/v1/uploads/batches` creates a batch.
2. Add files: `POST .../batches/{id}/files` (multipart, field `files`), or for big files
   `POST .../presign`, PUT each file to its URL, then `POST .../register`.
3. Files are read in the background; `GET .../batches/{id}` shows a preview per match id
   (teams, map, room name, what is missing). Game match ids are strings in JSON.
4. `POST .../batches/{id}/confirm` with a match day and number per new match (and
   optional in-game name -> team ids). Matches are built in the background.
5. Re-uploading a match updates it; nothing is duplicated.

## Log parsers

`backend/apps/ingest/parsers/` has one parser per Free Fire observer file type.
They are plain Python (no Django), never raise on bad content, and report what they
could not parse. See the module docstrings for the exact line formats.
