# ════════════════════════════════════════════
# FALLAMAN — Commandes simplifiées (comme Gabomazone)
# Usage : make <commande>
# Sous Windows : .\dev.ps1
# ════════════════════════════════════════════

DC_DEV := docker compose -f docker-compose.dev.yml
DC := docker compose

.PHONY: help dev dev-build prod build down restart logs logs-web logs-celery ps \
        migrate migrate-dev seed seed-dev shell shell-dev superuser superuser-dev \
        test collectstatic clean

help:
	@echo "Commandes Fallaman :"
	@echo "  make dev           - Lance l'environnement de developpement (conteneurs)"
	@echo "  make dev-build     - Reconstruit et lance en developpement"
	@echo "  make prod          - Lance l'environnement de production"
	@echo "  make down          - Arrete les conteneurs de developpement"
	@echo "  make logs          - Logs en temps reel (dev)"
	@echo "  make migrate-dev   - Applique les migrations (dev)"
	@echo "  make seed-dev      - Charge les donnees de demonstration (dev)"
	@echo "  make shell-dev     - Shell Django (dev)"
	@echo "  make superuser-dev - Cree un superutilisateur (dev)"
	@echo "  make test          - Lance les tests dans le conteneur"
	@echo "  make clean         - Supprime conteneurs et volumes"

dev:
	$(DC_DEV) up

dev-build:
	$(DC_DEV) up --build

prod:
	$(DC) up -d --build
	@echo ">>> Fallaman lance sur http://localhost:8000"

build:
	$(DC) build --no-cache

down:
	$(DC_DEV) down
	$(DC) down

restart:
	$(DC_DEV) restart web

logs:
	$(DC_DEV) logs -f

logs-web:
	$(DC_DEV) logs -f web

logs-celery:
	$(DC_DEV) logs -f celery

ps:
	$(DC_DEV) ps

migrate:
	$(DC) exec web python manage.py migrate

migrate-dev:
	$(DC_DEV) exec web python manage.py migrate

seed:
	$(DC) exec web python manage.py seed_demo --reference-only

seed-dev:
	$(DC_DEV) exec web python manage.py seed_demo --with-accounts

shell:
	$(DC) exec web python manage.py shell

shell-dev:
	$(DC_DEV) exec web python manage.py shell

superuser:
	$(DC) exec web python manage.py createsuperuser

superuser-dev:
	$(DC_DEV) run --rm web python manage.py createsuperuser

test:
	$(DC_DEV) exec web python -m pytest

collectstatic:
	$(DC) exec web python manage.py collectstatic --noinput

clean:
	$(DC_DEV) down -v
	$(DC) down -v
