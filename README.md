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

## Accounts and roles

- **Super Admin**: a Django superuser. Manages staff at `/api/v1/admin/staff`.
- **League Staff / Analyst**: upload matches and manage teams, players, aliases, rosters
  and game UID claims (`/api/v1/admin/...`).
- **Team Manager / Team Player**: members of a team. Managers invite players
  (`/api/v1/teams/{slug}/invites`); only staff can invite or promote managers.
- **Plans and features**: pages are gated by feature codes (`rotations.view`,
  `zone_analysis`, ...). League teams get the `league_team` plan with every feature;
  a paid plan for outside teams is just another plan with fewer features.

Sign-in uses JWT in httpOnly cookies. The website calls `GET /api/v1/auth/csrf` once,
then sends the `csrftoken` cookie value in the `X-CSRFToken` header on every write
(`/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/password-reset[/confirm]`).
Players ask to link their game UID with `POST /api/v1/me/link-uid`; staff approve it.
