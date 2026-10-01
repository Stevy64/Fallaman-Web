#!/usr/bin/env bash
# Mise à jour Fallaman sur VPS OVH (Docker Compose).
# Usage (depuis /var/www/fallaman/Fallaman, avec sudo si besoin) :
#   bash deploy/update.sh
#   bash deploy/update.sh --ref main
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REF="${1:-}"
cd "$APP_DIR"

if [[ ! -f .env ]]; then
  echo "ERREUR : .env manquant. Copie .env.production.example vers .env et renseigne les secrets."
  exit 1
fi

if [[ ! -f docker-compose.yml ]]; then
  echo "ERREUR : docker-compose.yml introuvable dans $APP_DIR"
  exit 1
fi

echo ">>> Répertoire : $APP_DIR"

if command -v git >/dev/null 2>&1 && [[ -d ../.git || -d .git ]]; then
  # Le dépôt git est souvent un niveau au-dessus (Fallaman_web/).
  if [[ -d ../.git ]]; then
    git -C .. fetch --prune
    if [[ -n "$REF" && "$REF" == --ref ]]; then
      BRANCH="${2:-main}"
      git -C .. checkout "$BRANCH"
      git -C .. pull --ff-only origin "$BRANCH"
    else
      git -C .. pull --ff-only
    fi
  else
    git pull --ff-only
  fi
fi

echo ">>> Build + démarrage des micro-services..."
docker compose up -d --build --remove-orphans

echo ">>> Attente health web..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${FALLAMAN_HTTP_PORT:-80}/health/" >/dev/null 2>&1; then
    echo "OK — Fallaman à jour (health 200)."
    docker compose ps
    exit 0
  fi
  sleep 2
done

echo "ATTENTION : health check encore KO après ~60s. Voir : docker compose logs --tail=80 web"
docker compose ps
exit 1
