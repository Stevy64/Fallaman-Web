#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo ">>> Migrations Fallaman..."
  python manage.py migrate --noinput
fi

if [ "${SEED_DEMO:-false}" = "true" ]; then
  echo ">>> Données de démonstration..."
  python manage.py seed_demo --with-accounts
fi

if [ "${COLLECTSTATIC:-false}" = "true" ]; then
  echo ">>> Fichiers statiques..."
  python manage.py collectstatic --noinput
fi

exec "$@"
