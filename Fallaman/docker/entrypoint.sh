#!/bin/sh
# Entrypoint des conteneurs Fallaman (web / celery).
# Variables optionnelles : RUN_MIGRATIONS, SEED_DEMO, COLLECTSTATIC (true|false).
# En production OVH, SEED_DEMO doit rester false (voir docker-compose.yml).
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo ">>> Migrations Fallaman..."
  python manage.py migrate --noinput
fi

if [ "${SEED_DEMO:-false}" = "true" ]; then
  echo ">>> Donnees de demonstration (DEV uniquement)..."
  python manage.py seed_demo --with-accounts
fi

if [ "${COLLECTSTATIC:-false}" = "true" ]; then
  echo ">>> Fichiers statiques..."
  python manage.py collectstatic --noinput
fi

exec "$@"
