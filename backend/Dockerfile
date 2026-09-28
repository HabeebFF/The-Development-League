FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY apps ./apps
COPY config ./config
COPY common ./common
COPY manage.py ./
RUN pip install --no-cache-dir .

RUN useradd --create-home app && chown -R app /app
USER app

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
