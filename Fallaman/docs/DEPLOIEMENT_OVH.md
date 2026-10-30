# Manuel de déploiement Fallaman — OVH Cloud

**Domaine :** `https://fallaman.gabomazone.com`  
**Stack :** Docker Compose (micro-services) + nginx + Let’s Encrypt + GitHub Actions

Si le VPS fait déjà tourner le cluster k3s de Wayizé, suivez [ovh-cluster.md](ovh-cluster.md). Ce manuel reste le chemin Docker sur une machine vide.  

Ce guide couvre le **premier déploiement** et les **mises à jour** en production.

Documents liés :

- Architecture : [ARCHITECTURE.md](ARCHITECTURE.md)
- Variables d’environnement : [../.env.production.example](../.env.production.example)
- Script de mise à jour : [../deploy/update.sh](../deploy/update.sh)

---

## Sommaire

1. [Prérequis OVH](#1-prérequis-ovh)
2. [DNS](#2-dns)
3. [Préparation du VPS](#3-préparation-du-vps)
4. [Clone du dépôt](#4-clone-du-dépôt)
5. [Fichier `.env` de production](#5-fichier-env-de-production)
6. [Premier lancement Docker](#6-premier-lancement-docker)
7. [nginx hôte + HTTPS (Let’s Encrypt)](#7-nginx-hôte--https-lets-encrypt)
8. [Compte administrateur & données de référence](#8-compte-administrateur--données-de-référence)
9. [SingPay (webhooks)](#9-singpay-webhooks)
10. [GitHub Actions (CI / Deploy)](#10-github-actions-ci--deploy)
11. [Mises à jour quotidiennes](#11-mises-à-jour-quotidiennes)
12. [Supervision & dépannage](#12-supervision--dépannage)
13. [Checklist go-live](#13-checklist-go-live)
14. [Rollback](#14-rollback)

---

## 1. Prérequis OVH

| Élément | Recommandation |
|---------|----------------|
| Produit | **VPS** OVH (Ubuntu 22.04 ou 24.04 LTS) |
| CPU / RAM | 2 vCPU / **4 Go** minimum (8 Go confortable avec Celery) |
| Disque | 40 Go+ SSD |
| Réseau | IPv4 publique, ports **22 / 80 / 443** ouverts |
| Domaine | `fallaman.gabomazone.com` géré chez OVH (ou DNS pointant vers le VPS) |
| Accès | Clé SSH (désactiver le login root par mot de passe) |

Optionnel : **Object Storage** OVH pour les médias (évolution future). Le MVP stocke `/media` dans un volume Docker.

---

## 2. DNS

Dans la zone DNS `gabomazone.com` :

| Type | Nom | Cible |
|------|-----|-------|
| **A** | `fallaman` | IP publique du VPS |
| (optionnel) **AAAA** | `fallaman` | IPv6 du VPS |

Propagation : quelques minutes à 1 h. Vérifier :

```bash
dig +short fallaman.gabomazone.com A
```

---

## 3. Préparation du VPS

Connecte-toi en SSH :

```bash
ssh ubuntu@IP_DU_VPS
```

### 3.1 Paquets système

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  ca-certificates curl git ufw \
  docker.io docker-compose-v2 \
  nginx certbot python3-certbot-nginx
```

### 3.2 Docker sans root

```bash
sudo usermod -aG docker "$USER"
# Déconnexion / reconnexion SSH obligatoire
```

Vérifie :

```bash
docker version
docker compose version
```

### 3.3 Pare-feu

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

### 3.4 Répertoire applicatif

```bash
sudo mkdir -p /var/www/fallaman /var/www/certbot
sudo chown "$USER":"$USER" /var/www/fallaman
```

---

## 4. Clone du dépôt

```bash
cd /var/www/fallaman
git clone https://github.com/<ORG_OU_USER>/Fallaman_web.git .
# Adapter l’URL à ton dépôt GitHub privé/public.
```

Structure attendue :

```text
/var/www/fallaman/
├── .github/workflows/     # CI + Deploy
├── README.md
└── Fallaman/              # projet Django (manage.py, Docker…)
    ├── docker-compose.yml
    ├── Dockerfile
    ├── deploy/
    ├── apps/
    └── …
```

---

## 5. Fichier `.env` de production

```bash
cd /var/www/fallaman/Fallaman
cp .env.production.example .env
chmod 600 .env
nano .env
```

### Valeurs minimales obligatoires

```bash
DJANGO_SECRET_KEY=<générer — voir commande ci-dessous>
DJANGO_ALLOWED_HOSTS=fallaman.gabomazone.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://fallaman.gabomazone.com
DJANGO_SECURE_SSL_REDIRECT=true
TRUST_PROXY_HEADERS=true

FALLAMAN_HTTP_PORT=8080
POSTGRES_PASSWORD=<mot-de-passe-fort>

OTP_PROVIDER=email
EMAIL_HOST=smtp.brevo.com          # ou autre
EMAIL_PORT=587
EMAIL_HOST_USER=…
EMAIL_HOST_PASSWORD=…
DEFAULT_FROM_EMAIL=Fallaman <no-reply@gabomazone.com>

SINGPAY_API_KEY=…
SINGPAY_API_SECRET=…
SINGPAY_MERCHANT_ID=…
SINGPAY_DISBURSEMENT_ID=…
SINGPAY_ENVIRONMENT=production
```

Générer la clé secrète :

```bash
python3 - <<'PY'
from secrets import token_urlsafe
print(token_urlsafe(50))
PY
```

> `production.py` **bloque le démarrage** si `OTP_PROVIDER=console`, si SingPay
> est incomplet, ou si `DEMO_STAFF_PASSWORD` est défini. C’est voulu.

---

## 6. Premier lancement Docker

```bash
cd /var/www/fallaman/Fallaman
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8080/health/
```

Services attendus : `fallaman-nginx`, `fallaman-web`, `fallaman-celery`,
`fallaman-celery-beat`, `fallaman-db`, `fallaman-redis` — tous **healthy** / **running**.

Logs en cas d’échec :

```bash
docker compose logs --tail=100 web
docker compose logs --tail=50 nginx
```

---

## 7. nginx hôte + HTTPS (Let’s Encrypt)

Le conteneur nginx écoute sur **127.0.0.1:8080**. L’hôte termine le TLS.

### 7.1 Site temporaire HTTP (pour Certbot)

```bash
sudo tee /etc/nginx/sites-available/fallaman >/dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name fallaman.gabomazone.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/fallaman /etc/nginx/sites-enabled/fallaman
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 7.2 Certificat

```bash
sudo certbot --nginx -d fallaman.gabomazone.com \
  --agree-tos -m admin@gabomazone.com --redirect
```

### 7.3 Config TLS durable (recommandé)

Après le premier certificat, tu peux remplacer le site par le fichier du dépôt :

```bash
sudo cp /var/www/fallaman/Fallaman/deploy/nginx-host.conf \
        /etc/nginx/sites-available/fallaman
sudo nginx -t && sudo systemctl reload nginx
```

Vérifie :

```bash
curl -fsSI https://fallaman.gabomazone.com/health/
```

Attendu : `HTTP/2 200` (ou 200 HTTP/1.1).

---

## 8. Compte administrateur & données de référence

```bash
cd /var/www/fallaman/Fallaman
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo --reference-only
```

- Tableau de bord métier : `https://fallaman.gabomazone.com/tableau-de-bord/`
- Django Admin : `https://fallaman.gabomazone.com/admin/`

**Ne jamais** lancer `seed_demo --with-accounts` en production (refuse si
`DEV_CONVENIENCES=false`).

---

## 9. SingPay (webhooks)

Dans le Workspace SingPay, configure l’URL de retour / webhook vers :

```text
https://fallaman.gabomazone.com/paiements/…
```

(Routes exactes : voir `apps/payments/urls.py` — webhook + return/cancel.)

Contrôles côté Fallaman :

1. Signature HMAC (`SINGPAY_WEBHOOK_SECRET` ou `SINGPAY_API_SECRET`)
2. Re-vérification serveur-à-serveur du statut
3. Égalité du montant

Tester un boost profil / annonce en sandbox puis basculer
`SINGPAY_ENVIRONMENT=production`.

---

## 10. GitHub Actions (CI / Deploy)

### 10.1 CI (automatique)

Fichier : `.github/workflows/ci.yml`

- pytest
- contrôle des migrations
- build Docker `runner`
- smoke `production` avec `fallaman.gabomazone.com`

### 10.2 Deploy (push sur `main`)

Fichier : `.github/workflows/deploy.yml`

Secrets GitHub à créer :

| Secret | Exemple |
|--------|---------|
| `OVH_HOST` | `203.0.113.10` |
| `OVH_USER` | `ubuntu` |
| `OVH_SSH_KEY` | clé privée OpenSSH |
| `OVH_SSH_PORT` | `22` (optionnel) |
| `OVH_DEPLOY_PATH` | `/var/www/fallaman` |

Sur le VPS, autorise la clé publique correspondante dans
`~/.ssh/authorized_keys`. Le déploiement exécute `Fallaman/deploy/update.sh`.

Environment GitHub : `production` (protection optionnelle : reviewers, wait timer).

### 10.3 Première clé deploy

```bash
# Sur ton poste
ssh-keygen -t ed25519 -f fallaman-deploy -N ""
# Ajoute fallaman-deploy.pub sur le VPS
# Colle le contenu de fallaman-deploy dans le secret OVH_SSH_KEY
```

---

## 11. Mises à jour quotidiennes

### Automatique

Push sur `main` → workflow **Deploy OVH**.

### Manuel sur le VPS

```bash
cd /var/www/fallaman/Fallaman
bash deploy/update.sh
# ou
make update
make health
```

---

## 12. Supervision & dépannage

| Symptôme | Commande / piste |
|----------|------------------|
| Conteneur unhealthy | `docker compose ps` puis `docker compose logs --tail=120 web` |
| 502 Bad Gateway | nginx hôte → `curl 127.0.0.1:8080/health/` ; Docker down ? |
| Migrations | `docker compose exec web python manage.py showmigrations` |
| OTP non reçu | SMTP `.env`, logs `EMAIL_*`, spam |
| Celery inactif | `docker compose logs celery celery-beat` |
| Disque plein | `df -h` ; volumes Docker `docker system df` |
| Certificat | `sudo certbot renew --dry-run` |

Sauvegardes recommandées (cron quotidien) :

```bash
# Exemple : dump Postgres
0 3 * * * docker exec fallaman-db pg_dump -U fallaman fallaman | gzip > /var/backups/fallaman-$(date +\%F).sql.gz
```

Conserver aussi une copie chiffrée du `.env` hors du VPS (gestionnaire de secrets).

---

## 13. Checklist go-live

- [ ] DNS `fallaman.gabomazone.com` → IP VPS
- [ ] `.env` renseigné (SECRET, Postgres, SMTP, SingPay)
- [ ] `docker compose up -d --build` OK
- [ ] `https://fallaman.gabomazone.com/health/` → 200
- [ ] Superutilisateur créé
- [ ] `seed_demo --reference-only` (métiers / villes)
- [ ] Connexion membre réelle (OTP e-mail)
- [ ] Webhook SingPay configuré + test paiement
- [ ] Secrets GitHub Actions + deploy test (`workflow_dispatch`)
- [ ] Sauvegarde Postgres planifiée
- [ ] PWA installable (HTTPS obligatoire)

---

## 14. Rollback

```bash
cd /var/www/fallaman
git log --oneline -5
git checkout <commit_stable>
cd Fallaman
bash deploy/update.sh
```

Ou via GitHub : revert du merge + re-déploiement automatique.

Restaurer une base :

```bash
gunzip -c /var/backups/fallaman-YYYY-MM-DD.sql.gz \
  | docker exec -i fallaman-db psql -U fallaman fallaman
```

---

## Annexe — Ports

| Port | Binding | Service |
|------|---------|---------|
| 22 | public | SSH |
| 80 / 443 | public | nginx hôte (TLS) |
| 8080 | `127.0.0.1` | nginx Docker → Gunicorn |
| 5432 / 6379 | **interne Docker seulement** | Postgres / Redis |

---

## Annexe — Alternative PythonAnywhere

Conservée pour historique / staging léger :
[DEPLOIEMENT_PYTHONANYWHERE.md](DEPLOIEMENT_PYTHONANYWHERE.md).  
La **cible officielle** reste OVH + Docker pour Celery, Redis et egress SingPay.
