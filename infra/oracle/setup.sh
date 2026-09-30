#!/usr/bin/env bash
# Sets up (or updates) the site on a fresh Ubuntu server, e.g. Oracle Cloud's free
# Ampere VM. Run it from the repo folder on the server:
#   bash infra/oracle/setup.sh <domain>
# <domain> is the site's address, e.g. 203-0-113-7.sslip.io (a free name for the
# server's IP) or your own domain once its DNS points at the server.
# Safe to run again: it keeps the existing .env and data, and rebuilds the containers.
set -euo pipefail

cd "$(dirname "$0")/../.."

if [ ! -f .env ]; then
  DOMAIN="${1:?usage: bash infra/oracle/setup.sh <domain>}"
fi

# Docker
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

# Oracle's Ubuntu images only let SSH through their firewall: open HTTP and HTTPS.
# (The subnet's security list in the Oracle console must allow them too.)
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  fi
done
if command -v netfilter-persistent >/dev/null; then
  sudo netfilter-persistent save
fi

# Secrets, made once and kept on the server only.
if [ ! -f .env ]; then
  secret="$(openssl rand -base64 96 | tr -dc 'A-Za-z0-9' | head -c 64)"
  cat > .env <<ENV
DJANGO_SECRET_KEY=${secret}
POSTGRES_PASSWORD=$(openssl rand -hex 24)
SITE_DOMAIN=${DOMAIN}
DJANGO_ALLOWED_HOSTS=${DOMAIN},web,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN}
FRONTEND_URL=https://${DOMAIN}
AUTH_COOKIE_SECURE=true
TIME_ZONE=UTC
LOG_TIME_ZONE=Africa/Lagos
USE_S3=false
UPLOAD_MAX_FILE_BYTES=314572800
# Emails are only printed to the logs until an email sender is set up; share invite
# links by hand from the Members page meanwhile.
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=The Development League <no-reply@${DOMAIN}>
ENV
  chmod 600 .env
  echo "Created .env for ${DOMAIN}"
fi

sudo docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build
sudo docker compose --env-file .env -f infra/docker-compose.prod.yml ps
echo "Done. The site will be at https://$(grep '^SITE_DOMAIN=' .env | cut -d= -f2)"
