#!/usr/bin/env bash
# Build the frontends and bring the stack up.
#
# Deliberately dumb and readable. A deploy nobody understands is a deploy
# nobody can fix at 2 a.m.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env.prod ]; then
  echo "error: .env.prod is missing. See infra/docker-compose.prod.yml." >&2
  exit 1
fi

echo "==> Verifying the API contract is current"
# A stale schema means a stale TypeScript client, and a client that disagrees
# with the server fails at a reception desk rather than here.
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod \
  run --rm --no-deps api python manage.py spectacular --file /tmp/schema.yaml --fail-on-warn

# One app for all three surfaces. It used to be three builds served from
# three roots; the router now decides which surface a person gets from the
# `kind` on their session, so there is one bundle and one origin to host.
echo "==> Building the web app"
( cd web && npm ci && npm run gen:api && npm run build )

echo "==> Staging static output"
rm -rf infra/www
mkdir -p infra/www
cp -r web/dist/. infra/www/

echo "==> Starting services (migrations run in the api entrypoint)"
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build

echo "==> Health"
docker compose -f infra/docker-compose.prod.yml --env-file .env.prod ps

cat <<'NOTE'

Deployed. Before this carries real patient data, confirm:
  - beat is running (no beat means no leave-now SMS, which is the product)
  - SMS_BACKEND is a real gateway, not the console one
  - an encrypted backup runs, and you have RESTORED from it at least once
  - /admin is IP-restricted and behind MFA
  - hosting location is lawful for Rwandan health data (docs/08 section 2)
NOTE
