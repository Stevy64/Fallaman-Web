# Fallaman

**Trouvez quelqu'un. Trouvez du travail.**

Fallaman est une PWA mobile-first de mise en relation, pensée pour le Gabon. Un particulier peut chercher du travail et publier une annonce avec le même compte, sans profil entreprise ni CV obligatoire.

> **Documentation complète (web + mobile, dev et prod) :**  
> **[docs/PRISE_EN_MAIN.md](docs/PRISE_EN_MAIN.md)** — guide pas à pas.

## Démarrage rapide (web, local)

Prérequis : Python 3.12+ (3.13 accepté).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo --with-accounts
python manage.py runserver
```

Ouvrez [http://127.0.0.1:8000](http://127.0.0.1:8000).

**Connexion :** première visite → numéro + e-mail → code de vérification →
choix du mot de passe. Ensuite, numéro + mot de passe.
En développement, le code est `123456` (affiché à l'écran et dans le terminal).

Comptes de démonstration après `seed_demo --with-accounts` : `+24106222222` et
`+24106333333`, mot de passe `FallamanDemo2026`.

> Ces facilités (code OTP fixe, paiement simulé, compte équipe de
> démonstration) dépendent de `DEV_CONVENIENCES=true`. La configuration de
> production les désactive et refuse de démarrer si l'une d'elles est réactivée.
> Pour la mise en ligne, voir
> [docs/DEPLOIEMENT_PYTHONANYWHERE.md](docs/DEPLOIEMENT_PYTHONANYWHERE.md).

Créer un administrateur :

```powershell
python manage.py createsuperuser
```

Le tableau de bord métier est sur `/tableau-de-bord/` (compte staff). Django Admin reste sur `/admin/`.

## Tests

```powershell
python -m pytest
```

## Docker

Prérequis : Docker Desktop.

```powershell
.\dev.ps1
```

L’application s’ouvre sur [http://localhost:8000](http://localhost:8000).  
OTP de développement : `123456`.

Autres commandes : `.\dev.ps1 prod`, `logs`, `seed`, `superuser`, `down`, `clean`.  
Équivalent Make : `make dev`, `make prod`, `make down`.

## Application mobile (Flutter)

Coque native dans [`mobile/`](mobile/) (WebView de la PWA).

```powershell
# Terminal 1 — backend (port recommandé pour le mobile)
python manage.py runserver 8001

# Terminal 2
cd mobile
flutter pub get
flutter run
```

Détails : [docs/PRISE_EN_MAIN.md](docs/PRISE_EN_MAIN.md#6-application-mobile-flutter) et [mobile/README.md](mobile/README.md).

Sur l’accueil web, un **bouton double Android / iOS** pointe vers les liens configurés (`ANDROID_APP_URL`, `IOS_APP_URL` dans `.env`).

## Architecture

- Django 5.2, templates serveur, Bootstrap 5, HTMX
- Compte centré sur le téléphone + OTP
- Annonces **emploi** (30 jours) et **mission** (7 jours)
- Recherche avec synonymes métier
- Intérêt → messagerie temporaire (72 h d'inactivité, 7 jours max) → WhatsApp
- PWA : manifest, service worker, page hors-ligne
- App mobile Flutter (`mobile/`) : coque native + WebView
- Recommandations optionnelles payantes (SingPay) : boost annonce / profil
- Espace équipe : alertes, revenus reco, suivi conversations, diffusions

## Parcours principaux

1. Visiteur : accueil → recherche `nounou` → annonce → partage
2. Compte : téléphone → OTP → je suis intéressé → message → WhatsApp
3. Publication : Publier → mission → métier → lieu → montant → description
4. Boost optionnel : Gérer l’annonce → Mettre en avant → durée → SingPay
5. Demandeur : Profil → Être recommandé → durée → SingPay
6. Pourvoyeur : Accepter / refuser le candidat recommandé → Discuter / WhatsApp
7. Équipe : `/tableau-de-bord/` → alertes, recommandations, conversations, diffusions

## Sécurité

Fallaman ne demande jamais d'argent pour obtenir un emploi. Les signalements, le rate limiting et la messagerie éphémère sont prévus dès le MVP.
