# Fallaman — web

> Trouvez quelqu'un. Trouvez du travail.

Plateforme de mise en relation entre particuliers et travailleurs au Gabon
(nounous, maçons, chauffeurs, ménage…). Django 5.2, HTMX, PostgreSQL, Celery.

**Production :** https://fallaman.gabomazone.com (OVH Cloud, Docker micro-services).

## Structure du dépôt

```
Fallaman_web/
├── .github/workflows/   CI + déploiement OVH
├── README.md
└── Fallaman/            projet Django (manage.py)
    ├── apps/            applications métier
    ├── config/          réglages (base / development / production)
    ├── deploy/          nginx, update.sh
    ├── docs/            architecture & manuels
    ├── docker-compose.yml
    └── Dockerfile
```

## Démarrer en local

```bash
cd Fallaman
docker compose -f docker-compose.dev.yml up
```

Site : http://localhost:8001  
OTP console : `123456` (logs `FALLAMAN DEV`).

Sans Docker : [Fallaman/docs/PRISE_EN_MAIN.md](Fallaman/docs/PRISE_EN_MAIN.md).

## Tests

```bash
cd Fallaman
python -m pytest
```

CI GitHub : `.github/workflows/ci.yml` (pytest + build image + smoke OVH).

## Déploiement production (OVH)

Manuel détaillé :

**[Fallaman/docs/DEPLOIEMENT_OVH.md](Fallaman/docs/DEPLOIEMENT_OVH.md)**

Architecture micro-services :

**[Fallaman/docs/ARCHITECTURE.md](Fallaman/docs/ARCHITECTURE.md)**

Résumé :

1. VPS Ubuntu + Docker + nginx + Certbot
2. DNS `fallaman.gabomazone.com` → IP VPS
3. `Fallaman/.env` depuis `.env.production.example`
4. `docker compose up -d --build` puis TLS
5. GitHub Actions Deploy (secrets `OVH_*`)

Alternative historique : [Fallaman/docs/DEPLOIEMENT_PYTHONANYWHERE.md](Fallaman/docs/DEPLOIEMENT_PYTHONANYWHERE.md).

## Connexion

- Première connexion / mot de passe oublié → code e-mail → mot de passe
- Ensuite → téléphone + mot de passe

## Paiements

Boosts payants via **SingPay** (HMAC webhook + verify serveur-à-serveur).
