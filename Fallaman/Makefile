# ════════════════════════════════════════════
# FALLAMAN — Commandes DevOps
# Usage : make <commande>   |   Windows : .\dev.ps1
# ════════════════════════════════════════════

DC_DEV := docker compose -f docker-compose.dev.yml
DC := docker compose

.PHONY: help dev dev-build prod prod-build down restart logs logs-web logs-celery ps \
        migrate migrate-dev seed seed-dev shell shell-dev superuser superuser-dev \
        test collectstatic health clean update

help:
	@echo "Commandes Fallaman :"
	@echo "  make dev           - Environnement de developpement"
	@echo "  make dev-build     - Rebuild + lance le developpement"
	@echo "  make prod          - Production Docker (OVH)"
	@echo "  make prod-build    - Rebuild images + lance la production"
	@echo "  make update        - git pull + rebuild prod (VPS)"
	@echo "  make health        - Verifie /health/ via nginx"
	@echo "  make down          - Arrete les stacks"
	@echo "  make logs          - Logs temps reel (dev)"
	@echo "  make migrate-dev   - Migrations (dev)"
	@echo "  make seed-dev      - Donnees de demonstration (dev)"
	@echo "  make shell-dev     - Shell Django (dev)"
	@echo "  make superuser-dev - Superutilisateur (dev)"
	@echo "  make test          - pytest dans le conteneur"
	@echo "  make clean         - Conteneurs + volumes"

dev:
	$(DC_DEV) up

dev-build:
	$(DC_DEV) up --build

prod:
	$(DC) up -d
	@echo ">>> Fallaman prod — health : make health"

prod-build:
	$(DC) up -d --build --remove-orphans
	@echo ">>> Fallaman prod rebuild — health : make health"

update:
	bash deploy/update.sh

build:
	$(DC) build --no-cache

down:
	-$(DC_DEV) down
	-$(DC) down

restart:
	$(DC_DEV) restart web

logs:
	$(DC_DEV) logs -f

logs-web:
	$(DC) logs -f web nginx

logs-celery:
	$(DC) logs -f celery celery-beat

ps:
	$(DC) ps

migrate:
	$(DC) exec web python manage.py migrate --noinput

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

health:
	@curl -fsS "http://127.0.0.1:$${FALLAMAN_HTTP_PORT:-80}/health/" && echo && $(DC) ps

clean:
	-$(DC_DEV) down -v
	-$(DC) down -v
