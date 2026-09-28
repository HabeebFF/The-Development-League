# The Development League

Official website for The Development League (Free Fire esports): standings, match
results, player stats and, above all, team rotation study.

Monorepo layout (grows step by step):

- `backend/` Django + DRF + Celery (Python 3.11+)
- `frontend/` Next.js + Tailwind (coming later)
- `infra/` Docker and deployment (coming later)

## Backend: running the tests

```bash
cd backend
python -m pip install -e ".[dev]"
pytest
```

## Log parsers

`backend/apps/ingest/parsers/` has one parser per Free Fire observer file type.
They are plain Python (no Django), never raise on bad content, and report what they
could not parse. See the module docstrings for the exact line formats.
