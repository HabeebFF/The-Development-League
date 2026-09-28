# The Development League

Official website for The Development League (Free Fire esports): standings, match
results, player stats and, above all, team rotation study.

Monorepo layout (grows step by step):

- `backend/` Django + DRF + Celery (Python 3.11+)
- `frontend/` Next.js + Tailwind website (see `frontend/README.md`)
- `infra/` Docker Compose for local development

## Backend: running locally

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build      # Postgres, Redis, API, worker, website
docker compose -f infra/docker-compose.yml exec web python manage.py createsuperuser
```

The website is on http://localhost:3000, the API on http://localhost:8000/api/v1 and Django
admin on http://localhost:8000/admin
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

## Seasons, fixtures and standings

Staff build the league with `/api/v1/admin/seasons`, `/admin/stages`, `/admin/groups`
(teams by slug), `/admin/match-days` and `/admin/matches` (fixtures: number, map,
scheduled time). Results only come from uploads. Setting a match back to `NEEDS_REVIEW`
hides it from standings; `PUBLISHED` brings it back. The Super Admin edits scoring at
`/api/v1/admin/scoring-rules`.

Standings are stored tables, rebuilt in the background whenever a match is uploaded,
published, hidden, moved or deleted, or the scoring rule or tiebreakers change. Each
season has a table for the whole season, each stage, each group and each match day.
Past matches are re-scored with the season's current rule on every rebuild. Teams
level on every tiebreaker share a rank. Staff can force a rebuild with
`POST /api/v1/admin/seasons/{slug}/rebuild-standings`.

Public reads: `/api/v1/seasons`, `/seasons/{slug}` (stages, groups, scoring),
`/seasons/{slug}/standings?stage=&group=&match_day=`, `/seasons/{slug}/fixtures?upcoming=true`,
`/match-days/{id}` (matches plus that day's table) and `/matches?season=&match_day=&map=&team=`,
`/matches/{id}` (full results with players). Unpublished matches are not shown.

## Maps, calibration and rotations

All positions are stored in game world coordinates (x, z). A map image is lined up with
the world by calibration points (a world position and where it is on the image):
2 points give a scale and offset per axis, 3 or more a full least-squares fit. The fit
error per point shows a bad click. The Super Admin uploads images and calibrates at
`/api/v1/admin/maps/{slug}` (multipart `image`), `/admin/maps/{slug}/calibration-points`
(`PUT` replaces all) and names places at `/admin/maps/{slug}/areas` (world polygons).
`/admin/maps/{slug}/reference-points` lists where fights happened on that map, to line
the image up against. Public: `/api/v1/maps`, `/maps/{slug}`.

Every uploaded match gets an auto-drafted rotation per team: a suggested drop (its
fights before the first zone shrinks), one point per zone phase (the median of where
its players got kills, died, respawned or teleported) and its final or elimination
spot. Staff correct it in the plotting tool:

- `GET, PUT /api/v1/matches/{id}/rotations/{team_slug}`: read or save all points
  (full replace). Points sent back unchanged keep their auto source.
- `POST .../confirm` and `POST .../reset` (back to the auto draft).
- `POST /api/v1/matches/{id}/redraft-rotations` redrafts teams still on auto.

Teams whose plan has `rotations.view` read `GET /matches/{id}/rotations` and
`GET /matches/{id}/zones`.
