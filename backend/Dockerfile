FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY apps ./apps
COPY config ./config
COPY common ./common
COPY manage.py ./
RUN pip install --no-cache-dir .

# /data/media and /app/staticfiles are where compose mounts volumes; a new named volume copies
# the folder's owner, so the app user can save uploads, map images and static files.
RUN useradd --create-home app && mkdir -p /data/media /app/staticfiles && chown -R app /app /data
USER app

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
