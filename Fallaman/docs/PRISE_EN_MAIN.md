# Prise en main Fallaman

Guide pas à pas pour lancer et utiliser **la web app** (développement et production) et **l’application mobile Flutter**.

---

## Sommaire

1. [Vue d’ensemble](#1-vue-densemble)
2. [Web app — développement local](#2-web-app--développement-local)
3. [Web app — Docker (dev)](#3-web-app--docker-dev)
4. [Web app — production](#4-web-app--production)
5. [Comptes, OTP et espaces staff](#5-comptes-otp-et-espaces-staff)
6. [Application mobile Flutter](#6-application-mobile-flutter)
7. [Boutons de téléchargement (accueil)](#7-boutons-de-téléchargement-accueil)
8. [Recommandations payantes (SingPay)](#8-recommandations-payantes-singpay)
9. [Tests](#9-tests)
10. [Dépannage](#10-dépannage)

---

## 1. Vue d’ensemble

| Composant | Dossier / URL | Rôle |
|---|---|---|
| Web app (Django / PWA) | racine du dépôt | Site + API templates HTMX |
| App mobile | `mobile/` | Coque Flutter (WebView) vers la web app |
| Tableau de bord métier | `/tableau-de-bord/` | Modération / suivi (staff) |
| Django Admin | `/admin/` | Administration technique |

**Slogan :** Trouvez quelqu'un. Trouvez du travail.

---

## 2. Web app — développement local

### Prérequis

- Windows, macOS ou Linux
- **Python 3.12+** (3.13 accepté)
- Git

### Étape 1 — Cloner et entrer dans le projet

```powershell
cd C:\Users\Steevi\Documents\GitHub\Fallaman\Fallaman
```

### Étape 2 — Créer l’environnement virtuel

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Sous macOS / Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Étape 3 — Installer les dépendances

```powershell
pip install -r requirements.txt
```

### Étape 4 — Configurer l’environnement

```powershell
copy .env.example .env
```

Ouvrez `.env` et vérifiez au minimum :

```env
DJANGO_SETTINGS_MODULE=config.settings.development
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:8001
DATABASE_URL=sqlite:///db.sqlite3
OTP_DEV_CODE=123456
```

Pour l’app mobile en debug, préférez le serveur sur le **port 8001** (voir section mobile) et ajoutez ce port dans `DJANGO_CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS` si besoin.

### Étape 5 — Base de données et données de démo

```powershell
python manage.py migrate
python manage.py seed_demo
```

### Étape 6 — Lancer le serveur

Port classique :

```powershell
python manage.py runserver
```

→ [http://127.0.0.1:8000](http://127.0.0.1:8000)

Port recommandé avec l’app mobile :

```powershell
python manage.py runserver 8001
```

→ [http://127.0.0.1:8001](http://127.0.0.1:8001)

### Étape 7 — Vérifier

1. Accueil : hero, recherche, annonces.
2. Connexion téléphone → code OTP **`123456`** (mode console / dev).
3. Publier une annonce depuis le bouton **Publier**.

---

## 3. Web app — Docker (dev)

### Prérequis

- Docker Desktop démarré

### Lancer

```powershell
.\dev.ps1
```

→ [http://localhost:8000](http://localhost:8000)  
OTP de développement : **`123456`**

### Commandes utiles

| Commande | Action |
|---|---|
| `.\dev.ps1` | Stack développement |
| `.\dev.ps1 prod` | Stack production locale (détachée) |
| `.\dev.ps1 logs` | Logs en direct |
| `.\dev.ps1 seed` | Recharger la démo |
| `.\dev.ps1 migrate` | Migrations |
| `.\dev.ps1 superuser` | Créer un admin |
| `.\dev.ps1 test` | Tests dans le conteneur |
| `.\dev.ps1 down` | Arrêter |
| `.\dev.ps1 clean` | Arrêter + supprimer les volumes |

Équivalents Make : `make dev`, `make prod`, `make down`.

---

## 4. Web app — production

### Étape 1 — Variables d’environnement

Créez un `.env` de production (ne pas committer) :

```env
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=une-clé-longue-et-secrète
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=fallaman.ga,www.fallaman.ga
DJANGO_CSRF_TRUSTED_ORIGINS=https://fallaman.ga,https://www.fallaman.ga
DJANGO_SECURE_SSL_REDIRECT=true

DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/fallaman
REDIS_URL=redis://HOST:6379/0
CELERY_BROKER_URL=redis://HOST:6379/1
CELERY_RESULT_BACKEND=redis://HOST:6379/2
CELERY_TASK_ALWAYS_EAGER=false

OTP_PROVIDER=console
# Remplacer par le vrai provider SMS en prod

ANDROID_APP_URL=https://play.google.com/store/apps/details?id=com.fallaman.fallaman_mobile
IOS_APP_URL=https://apps.apple.com/app/idXXXXXXXX
```

### Étape 2 — Déploiement Docker (stack prod du dépôt)

```powershell
.\dev.ps1 prod
```

Ou, sur le serveur :

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

### Étape 3 — Checklist production

- [ ] `DJANGO_DEBUG=false` et `SECRET_KEY` fort
- [ ] HTTPS + `CSRF_TRUSTED_ORIGINS` corrects
- [ ] PostgreSQL (pas SQLite) et sauvegardes
- [ ] Redis / Celery actifs pour les tâches (expiration annonces, conversations…)
- [ ] Provider OTP SMS configuré (plus le code fixe `123456`)
- [ ] Liens Play Store / App Store renseignés (`ANDROID_APP_URL`, `IOS_APP_URL`)
- [ ] URL de production cohérente avec l’app mobile (`FALLAMAN_URL`)

### Étape 4 — Fichiers statiques et médias

Les statics sont servis via WhiteNoise. Les uploads vont dans `MEDIA_ROOT` (volume persistant recommandé en Docker).

---

## 5. Comptes, OTP et espaces staff

### Connexion utilisateur

1. Aller sur `/connexion/`
2. Saisir un numéro gabonais
3. Entrer le code OTP

En **développement** : code **`123456`** (aussi affiché / loggé selon la config).

### Créer un superutilisateur

```powershell
python manage.py createsuperuser
```

### Espaces

| URL | Accès |
|---|---|
| `/` | Public |
| `/connexion/` | Membres (téléphone + mot de passe) |
| `/connexion/activation/` | Première connexion / mot de passe oublié (code par e-mail) |
| `/connexion/equipe/` | Équipe (staff) |
| `/tableau-de-bord/` | Dashboard métier (staff) |
| `/admin/` | Django Admin |

Les comptes de démonstration ne sont créés que sur demande explicite :

```bash
python manage.py seed_demo --with-accounts
```

La commande **refuse de s'exécuter** si `DEV_CONVENIENCES` est faux, car elle
crée un administrateur dont le mot de passe est connu. Ce mot de passe se règle
via `DEMO_STAFF_PASSWORD` dans `.env` (valeur locale par défaut :
`FallamanAdmin2026!`, téléphone `+24106111111`, OTP `123456`).

En production, utiliser `seed_demo --reference-only` (métiers et villes
uniquement) puis `createsuperuser`. Voir
[DEPLOIEMENT_PYTHONANYWHERE.md](DEPLOIEMENT_PYTHONANYWHERE.md).

---

## 6. Application mobile Flutter

Projet indépendant dans [`mobile/`](../mobile/). Encapsulation native de la PWA (WebView), design aligné (orange `#FE724C`, marine `#0B1F3A`, Poppins).

### Prérequis

1. [Flutter SDK](https://docs.flutter.dev/get-started/install) 3.10+
2. Android Studio / SDK **ou** Xcode (iOS)
3. Web app Fallaman **démarrée** (idéalement `runserver 8001`)

Vérifier Flutter :

```powershell
flutter doctor
```

### Étape 1 — Dépendances

```powershell
cd mobile
flutter pub get
```

### Étape 2 — URL cible selon l’appareil

| Cible | URL Fallaman |
|---|---|
| Émulateur Android (debug) | `http://10.0.2.2:8001` |
| Simulateur iOS (debug) | `http://127.0.0.1:8001` |
| Téléphone physique (debug) | `http://IP_LAN_DU_PC:8001` |
| Release / prod | `https://fallaman.ga` (ou votre domaine) |

Les valeurs debug Android / iOS sont les **défauts** du code. Sinon :

```powershell
flutter run --dart-define=FALLAMAN_URL=http://10.0.2.2:8001
```

Sur téléphone physique, autorisez le HTTP local côté appareil / firewall, et utilisez l’IP du PC (ex. `http://192.168.1.20:8001`).

### Étape 3 — Lancer

1. Terminal 1 — backend :

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver 8001
```

2. Terminal 2 — mobile :

```powershell
cd mobile
flutter run
```

### Étape 4 — Parcours à tester dans l’app

1. Splash Fallaman
2. Accueil web dans la WebView
3. Recherche / détail d’annonce
4. Connexion OTP
5. Lien WhatsApp / téléphone → app native
6. Mode avion → écran hors ligne → Réessayer

### Builds release

```powershell
cd mobile

# Android APK
flutter build apk --release --dart-define=FALLAMAN_URL=https://fallaman.ga

# Android App Bundle (Play Store)
flutter build appbundle --release --dart-define=FALLAMAN_URL=https://fallaman.ga

# iOS (macOS + Xcode requis)
flutter build ios --release --dart-define=FALLAMAN_URL=https://fallaman.ga
```

Artefacts :

- APK : `mobile/build/app/outputs/flutter-apk/app-release.apk`
- AAB : `mobile/build/app/outputs/bundle/release/app-release.aab`

### Structure mobile

```
mobile/lib/
  main.dart
  app.dart
  config/       # URL + thème
  screens/      # splash, shell WebView, offline
  services/     # liens externes
  widgets/      # loader
```

Plus de détail : [`mobile/README.md`](../mobile/README.md).

---

## 7. Boutons de téléchargement (accueil)

Sur la page d’accueil, le bandeau hero propose un **bouton double** Android / iOS.

Configurez les URLs dans `.env` :

```env
ANDROID_APP_URL=https://play.google.com/store/apps/details?id=com.fallaman.fallaman_mobile
IOS_APP_URL=https://apps.apple.com/app/idXXXXXXXX
```

Tant que les stores ne sont pas prêts, laissez `#` (valeur par défaut) : les boutons restent visibles pour la démo.

---

## 8. Recommandations payantes (SingPay)

Système **optionnel** pour booster une annonce ou se faire recommander auprès des pourvoyeurs d’offres.

### Principe

| Offre | Qui | Effet |
|---|---|---|
| Boost annonce | Pourvoyeur | Priorité dans recherche / accueil + notifications aux profils matchés |
| Recommandation profil | Demandeur | Notifie les auteurs d’offres matchées + apparait sur leurs annonces |

Publier et postuler restent **gratuits**.

### Tarif (durée → montant)

Montant = tarif journalier × jours × (1 − remise volume).

| Durée | Remise | Annonce (500 F/j) | Profil (400 F/j) |
|---|---|---|---|
| 1 jour | 0 % | 500 FCFA | 400 FCFA |
| 3 jours | 5 % | 1 425 FCFA | 1 140 FCFA |
| 7 jours | 12 % | 3 080 FCFA | 2 464 FCFA |
| 14 jours | 20 % | 5 600 FCFA | 4 480 FCFA |

Variables `.env` : `RECO_LISTING_DAILY_RATE`, `RECO_PROFILE_DAILY_RATE`.

### Paiement SingPay

Comme Gabomazone : init → page SingPay (Airtel / Moov) → webhook / retour → activation.

```env
SINGPAY_API_KEY=
SINGPAY_API_SECRET=
SINGPAY_MERCHANT_ID=
SINGPAY_DISBURSEMENT_ID=
SINGPAY_ENVIRONMENT=sandbox
SINGPAY_MOCK=false
```

Sans clés (ou `SINGPAY_MOCK=true`) : **paiement simulé** local (`/paiements/simulation/...`).

### Parcours UI

1. Annonce → **Gérer** → **Mettre en avant** → choisir durée → payer  
2. Profil → **Demander à être recommandé** → durée → payer  
3. Historique : `/mes-recommandations/`

### Ranking

Ordre des listes : boost actif → `boost_score` (montant + durée + temps restant) → date de publication.

---

## 9. Tests

### Web

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

### Mobile

```powershell
cd mobile
flutter analyze
flutter test
```

---

## 10. Dépannage

| Problème | Piste |
|---|---|
| Page blanche / static 404 | `python manage.py collectstatic` (prod) ; vider le cache navigateur (`?v=` CSS) |
| CSRF / 403 | Ajouter l’URL exacte dans `DJANGO_CSRF_TRUSTED_ORIGINS` |
| App mobile « Impossible de charger » | Backend démarré ? Bonne URL (`10.0.2.2` vs `127.0.0.1` vs IP LAN) ? |
| Cleartext Android bloqué | Le manifeste mobile autorise le HTTP en debug ; en release, utilisez **HTTPS** |
| OTP refusé | En dev, utiliser `123456` ; vérifier `OTP_DEV_CODE` |
| Docker « not running » | Démarrer Docker Desktop puis `.\dev.ps1` |
| WhatsApp ne s’ouvre pas depuis l’app | Application WhatsApp installée ; schemes déclarés Android/iOS |
| Paiement SingPay échoue | Vérifier les 3 clés ; sinon laisser vide pour le mock local |
| Boost inactif après paiement | Vérifier webhook `/paiements/singpay/callback/` ou page retour ; Celery `expire-recommendation-boosts` |

---

## Prochaines étapes utiles

1. Publier l’AAB / IPA sur Play Store et App Store.
2. Renseigner `ANDROID_APP_URL` et `IOS_APP_URL` en production.
3. Brancher un vrai provider SMS pour l’OTP.
4. Configurer SingPay production et pointer `FALLAMAN_URL` mobile vers HTTPS.
5. Pointer l’app mobile release vers l’URL HTTPS définitive via `FALLAMAN_URL`.
