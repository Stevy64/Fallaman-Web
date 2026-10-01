# Architecture Fallaman (DevOps / micro-services)

## Vue d’ensemble

Fallaman est une **PWA Django** déployée en **micro-services Docker** sur un VPS
**OVH Cloud**, derrière nginx + TLS Let’s Encrypt.

Domaine de production : **https://fallaman.gabomazone.com**

```
                    Internet (HTTPS)
                           │
              ┌────────────▼────────────┐
              │  nginx hôte (Certbot)   │  :443 → 127.0.0.1:8080
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  nginx (conteneur)      │  static / media / reverse-proxy
              └────────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌──────────┐     ┌────────────┐    ┌─────────────┐
   │ web      │     │ celery     │    │ celery-beat │
   │ Gunicorn │     │ worker     │    │ scheduler   │
   └────┬─────┘     └─────┬──────┘    └──────┬──────┘
        │                 │                  │
        └────────┬────────┴────────┬─────────┘
                 ▼                 ▼
           ┌──────────┐      ┌─────────┐
           │ Postgres │      │  Redis  │
           └──────────┘      └─────────┘
```

## Services

| Conteneur | Rôle |
|-----------|------|
| `fallaman-nginx` | Reverse-proxy HTTP, fichiers `/static/` et `/media/` |
| `fallaman-web` | Django 5.2 + Gunicorn (API templates HTMX + PWA) |
| `fallaman-celery` | Tâches asynchrones (notifications, maintenance…) |
| `fallaman-celery-beat` | Planification périodique |
| `fallaman-db` | PostgreSQL 16 (données métier) |
| `fallaman-redis` | Cache Django + broker Celery |

## Applications Django (`apps/`)

| App | Responsabilité |
|-----|----------------|
| `accounts` | Téléphone, OTP, mot de passe |
| `profiles` | Profil public / privé, WhatsApp |
| `listings` | Annonces emploi / mission |
| `taxonomy` | Catégories & métiers |
| `locations` | Provinces / villes |
| `messaging` | Conversations éphémères |
| `interactions` | Intérêt pour une annonce |
| `recommendations` | Boost payant (profil / annonce) |
| `payments` | SingPay (checkout, webhook, verify) |
| `notifications` | Cloche in-app + diffusions staff |
| `moderation` | Signalements |
| `dashboard` | Espace équipe |
| `core` | Middleware, health, PWA, rate-limit |

## Pipelines GitHub Actions

| Workflow | Déclencheur | Action |
|----------|-------------|--------|
| `.github/workflows/ci.yml` | push / PR | pytest, migrations, build image, smoke config OVH |
| `.github/workflows/deploy.yml` | push `main` + `workflow_dispatch` | SSH → `deploy/update.sh` sur le VPS |

## Sécurité production

- `config/settings/production.py` **refuse de démarrer** si secrets / OTP / SingPay incomplets.
- `SEED_DEMO=false` et `DEV_CONVENIENCES=false` en prod.
- Postgres et Redis **non exposés** sur Internet (réseau Docker uniquement).
- TLS terminé sur l’hôte ; Django lit `X-Forwarded-Proto`.

## Documentation associée

- Manuel détaillé : [DEPLOIEMENT_OVH.md](DEPLOIEMENT_OVH.md)
- Prise en main locale : [PRISE_EN_MAIN.md](PRISE_EN_MAIN.md)
- Alternative historique : [DEPLOIEMENT_PYTHONANYWHERE.md](DEPLOIEMENT_PYTHONANYWHERE.md)
