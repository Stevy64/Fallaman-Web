# Fallaman sur le cluster

Ce guide s'enchaîne après le guide Wayizé (`docs/premier-cluster.md` du dépôt Wayizé). On le lit de haut en bas. Les numéros 1 à 9 sont ceux de Fallaman. Ils ne reprennent pas les numéros du guide Wayizé.

Dans le terminal, on ne colle que le contenu d'un bloc de commandes (le cadre gris). Les titres, les phrases et les lignes « Ça a marché si » ne sont pas des commandes.

Le dépôt cloné a sa racine à `/srv/fallaman`. Le projet Django est dans le dossier `Fallaman/`.

## Avant l'étape 1

Sur le VPS, une seule fois, le guide Wayizé a déjà fait :

- les étapes 1 à 7 (SSH, système, k3s, kubectl, Traefik, cert-manager, Let's Encrypt) ;
- l'étape 10.2 (le Postgres du namespace `donnees`).

Vérifiez, puis restez dans ce document :

```bash
kubectl get nodes
kubectl get clusterissuer letsencrypt
kubectl -n donnees get deploy postgres
```

Ça a marché si le nœud est `Ready`, l'émetteur `letsencrypt` est `True`, et le déploiement `postgres` existe. Sinon, terminez ces étapes dans le guide Wayizé, puis revenez ici à l'étape 1.

Les commandes se lancent sur le VPS. Si `whoami` affiche `root`, enlevez `sudo`.

Fallaman, c'est trois processus de la même image, plus Redis :

| Processus | Rôle | Publié sur Internet |
| --- | --- | --- |
| `fallaman-web` | Le site. Gunicorn en local dans le pod, nginx sert `/media/`. | Oui, `fallaman.gabomazone.com` |
| `fallaman-worker` | Celery, un processus | Non |
| `fallaman-beat` | Expirations et maintenance | Non. Un seul exemplaire |
| `redis` | Cache, courtier (base 1) et résultats (base 2) | Non |

La base s'appelle `fallaman`. L'application lit `DATABASE_URL`. Le disque `fallaman-media` (2 Gio) est monté sur `/app/media`, uniquement dans le pod web.

`config.settings.production` refuse de démarrer si la clé est vide, si `OTP_PROVIDER=console`, si `EMAIL_HOST` est vide, ou s'il manque un identifiant SingPay. L'étape 5 s'arrête le temps de remplir ces valeurs.

## 1. Namespace

```bash
kubectl create namespace fallaman
kubectl get namespaces
```

Ça a marché si `fallaman` apparaît.

## 2. Nom de domaine

Même IPv4 que Wayizé. Dans la zone `gabomazone.com`, une entrée `A` pour `fallaman`, pas un `CNAME` en plus. Si cette entrée existe déjà et pointe vers une autre machine, changez sa cible vers l'IPv4 du VPS.

```bash
dig +short fallaman.gabomazone.com
dig +short wayize.gabomazone.com
```

Ça a marché si les deux commandes affichent la même adresse.

## 3. Base de données

```bash
APP_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
kubectl -n donnees exec -i deploy/postgres -- psql -U postgres -v ON_ERROR_STOP=1 <<SQL
CREATE USER fallaman WITH PASSWORD '${APP_PW}';
CREATE DATABASE fallaman OWNER fallaman;
SQL
```

Gardez `APP_PW` jusqu'à l'étape 5. Si l'utilisateur existe déjà, ne relancez pas le `CREATE`.

Ça a marché si `psql` répond deux fois `CREATE`.

## 4. Image

Faites le choix A ou le choix B, pas les deux. Notez la lettre : elle revient aux étapes 6 et 9.

Le dépôt doit contenir `Fallaman/deploy/k8s/` et `Fallaman/deploy/Dockerfile.fallaman`. Poussez-les sur `main` avant de cloner.

### Choix A — GitHub Actions

```bash
sudo mkdir -p /srv/fallaman
sudo chown "$USER:$USER" /srv/fallaman
git clone https://github.com/Stevy64/Fallaman-Web.git /srv/fallaman
cd /srv/fallaman
mkdir -p .github/workflows
cp Fallaman/deploy/fallaman-image.yml .github/workflows/fallaman-image.yml
git add .github/workflows/fallaman-image.yml
git commit -m "Build the Fallaman image on GHCR."
git push origin main
```

Si `git push` demande un mot de passe, c'est un jeton GitHub. Ne l'écrivez pas dans le dépôt.

L'onglet Actions doit devenir vert. L'image s'appelle `ghcr.io/stevy64/fallaman`, étiquette `main`. Le contexte de construction est le dossier `Fallaman/`. Rendez le paquet public, puis :

```bash
sudo k3s ctr images pull ghcr.io/stevy64/fallaman:main
```

Ça a marché si la commande se termine sans `unauthorized`.

Si le paquet reste privé :

```bash
read -rs GHCR_TOKEN
kubectl -n fallaman create secret docker-registry ghcr \
  --docker-server=ghcr.io \
  --docker-username=Stevy64 \
  --docker-password="$GHCR_TOKEN"
unset GHCR_TOKEN
```

Ajoutez `imagePullSecrets: [{name: ghcr}]` sous `spec.template.spec` de chaque Deployment et du Job. Passez à l'étape 5.

### Choix B — Construire sur le VPS

```bash
sudo apt install -y docker.io
sudo mkdir -p /srv/fallaman
sudo chown "$USER:$USER" /srv/fallaman
if [ ! -d /srv/fallaman/.git ]; then
  git clone https://github.com/Stevy64/Fallaman-Web.git /srv/fallaman
fi
cd /srv/fallaman
git pull --ff-only
sudo docker build -f Fallaman/deploy/Dockerfile.fallaman -t fallaman:1 Fallaman
sudo docker save fallaman:1 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep fallaman
```

Ça a marché si `grep` affiche `docker.io/library/fallaman:1`.

Passez à l'étape 5. À l'étape 6, la commande sera `fallaman-deploy local`.

## 5. Variables

La clé Django et le mot de passe de l'étape 3 sont générés ici. L'hôte SMTP et les quatre identifiants SingPay viennent de vous. Le fichier part avec ces lignes vides. Le Secret n'est créé qu'une fois qu'elles sont remplies.

`DJANGO_SECURE_SSL_REDIRECT=true` marque les cookies comme sûrs. nginx repasse `X-Forwarded-Proto` tel que Traefik l'a reçu, y compris pour la sonde.

```bash
WEB_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
sudo mkdir -p /etc/fallaman
sudo tee /etc/fallaman/app.env >/dev/null <<EOF
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=${WEB_KEY}
DJANGO_ALLOWED_HOSTS=fallaman.gabomazone.com,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://fallaman.gabomazone.com
DJANGO_SECURE_SSL_REDIRECT=true
TRUST_PROXY_HEADERS=true
DATABASE_URL=postgresql://fallaman:${APP_PW}@postgres.donnees.svc.cluster.local:5432/fallaman?sslmode=disable
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
CELERY_TASK_ALWAYS_EAGER=false
OTP_PROVIDER=email
OTP_CODE_TTL_SECONDS=300
OTP_MAX_ATTEMPTS=5
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=Fallaman <no-reply@gabomazone.com>
SINGPAY_API_KEY=
SINGPAY_API_SECRET=
SINGPAY_MERCHANT_ID=
SINGPAY_DISBURSEMENT_ID=
SINGPAY_ENVIRONMENT=production
SINGPAY_WEBHOOK_SECRET=
DEV_CONVENIENCES=false
ANDROID_APP_URL=#
IOS_APP_URL=#
SENTRY_ENVIRONMENT=production
EOF
sudo chmod 600 /etc/fallaman/app.env
unset WEB_KEY APP_PW
sudoedit /etc/fallaman/app.env
```

Dans l'éditeur, remplissez `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, et les quatre `SINGPAY_API_KEY`, `SINGPAY_API_SECRET`, `SINGPAY_MERCHANT_ID`, `SINGPAY_DISBURSEMENT_ID`. Ne posez pas `DEMO_STAFF_PASSWORD`. Ne mettez pas `OTP_PROVIDER=console`.

Le callback à déclarer chez SingPay est `https://fallaman.gabomazone.com/paiements/singpay/callback/`.

Puis seulement :

```bash
sudo k3s kubectl -n fallaman create secret generic fallaman --from-env-file=/etc/fallaman/app.env
```

Ça a marché si `kubectl -n fallaman get secrets` liste `fallaman`. Si une clé manque, le pod bouclera à l'étape 6 et les journaux citeront `ImproperlyConfigured`. Corrigez le fichier, supprimez le Secret, recréez-le, relancez l'étape 6.

## 6. Lancer

```bash
sudo install -m 755 /srv/fallaman/Fallaman/deploy/k8s/update.sh /usr/local/bin/fallaman-deploy
```

Si vous avez choisi A à l'étape 4 :

```bash
fallaman-deploy
```

Si vous avez choisi B à l'étape 4 :

```bash
fallaman-deploy local
```

Le script attend Redis, joue la migration, puis lance le site, le worker et beat. Si la migration échoue, il s'arrête.

```bash
kubectl -n fallaman logs job/fallaman-migrate
```

Ça a marché si la commande se termine sans erreur.

## 7. Vérifier

```bash
kubectl -n fallaman get certificate
curl -fsS https://fallaman.gabomazone.com/health/
```

Ça a marché si `fallaman-tls` est `READY` = `True` et si `curl` affiche `"status": "ok"` et `"service": "fallaman"`.

S'il reste `False` : `kubectl -n fallaman describe certificate fallaman-tls`.

## 8. Compte administrateur

Le compte de démonstration n'est pas créé.

```bash
kubectl -n fallaman exec -it deploy/fallaman-web -c gunicorn -- python manage.py createsuperuser
```

Ouvrez `https://fallaman.gabomazone.com/` puis `https://fallaman.gabomazone.com/admin/`.

```bash
kubectl -n fallaman logs deploy/fallaman-web -c gunicorn
kubectl -n fallaman logs deploy/fallaman-worker
kubectl -n fallaman logs deploy/fallaman-beat
```

## 9. Mettre à jour

### Si vous aviez choisi A

Quand le job Actions est vert :

```bash
cd /srv/fallaman
git pull --ff-only
fallaman-deploy
curl -fsS https://fallaman.gabomazone.com/health/
```

Pour revenir à un commit, remplacez `:main` par le SHA du job, dans le Job de migration et dans chaque conteneur de l'image.

### Si vous aviez choisi B

```bash
cd /srv/fallaman
git pull --ff-only
sudo docker build -f Fallaman/deploy/Dockerfile.fallaman -t fallaman:1 Fallaman
sudo docker save fallaman:1 | sudo k3s ctr images import -
fallaman-deploy local
curl -fsS https://fallaman.gabomazone.com/health/
```

## À ne pas faire

- Refaire les étapes 1 à 7 du guide Wayizé, ni installer un second Postgres.
- Publier 8000 ou 6379.
- Activer `ufw`.
- Commiter `/etc/fallaman/app.env`, poser `OTP_PROVIDER=console`, ou réutiliser le Secret `wayize`.
- Lancer `fallaman-deploy` sans `local` si l'image a été construite sur le VPS.
- Lancer deux exemplaires de `fallaman-beat`.
- Relancer `CREATE USER` si la base existe déjà.
