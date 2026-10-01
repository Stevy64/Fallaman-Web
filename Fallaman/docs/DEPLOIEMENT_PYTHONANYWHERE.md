# Déploiement Fallaman sur PythonAnywhere

> **Cible officielle de production : OVH Cloud** —
> voir [DEPLOIEMENT_OVH.md](DEPLOIEMENT_OVH.md) (`fallaman.gabomazone.com`).
> Ce document reste utile pour un staging léger ou un historique de migration.

> À lire en entier avant le premier déploiement. Les sections **Prérequis** et
> **Paiement SingPay** décrivent deux contraintes de la plateforme qui peuvent
> bloquer la mise en production.

---

## 1. Prérequis — trois contraintes PythonAnywhere

Le projet a été conçu pour Docker (Postgres + Redis + Celery). PythonAnywhere
n'offre aucun des trois. Voici ce que cela change.

### 1.1 Un compte payant est nécessaire pour SingPay

Les comptes **gratuits** de PythonAnywhere ne peuvent joindre qu'une liste
blanche de sites. `gateway.singpay.ga` n'y figure pas : tout appel à
`init_payment` et `verify_payment` échouera.

**Conséquence : le paiement ne peut pas fonctionner sur un compte gratuit.**
Il faut au minimum une offre « Hacker ».

### 1.2 Pas de Celery

Aucun worker ni `celery beat` ne tourne. Les tâches sont exécutées en direct
(`CELERY_TASK_ALWAYS_EAGER` s'active automatiquement quand `CELERY_BROKER_URL`
est vide) et la maintenance périodique passe par une commande dédiée — voir
§ 6. Sans cette planification, **les annonces n'expirent jamais et les
recommandations payantes restent actives après leur échéance**.

### 1.3 Pas de Redis

Le cache bascule sur une table de base de données (§ 4). Ce cache porte les
compteurs de limitation de débit : il doit exister, sinon chaque requête
échoue.

---

## 2. Récupérer le code

Dans une console Bash PythonAnywhere :

```bash
git clone <votre-dépôt> ~/fallaman-web
# Le projet Django est dans le sous-dossier Fallaman/ du dépôt.
cd ~/fallaman-web/Fallaman
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

> Toutes les commandes qui suivent partent de `~/fallaman-web/Fallaman`,
> le dossier qui contient `manage.py`.

Si Python 3.13 n'est pas proposé, 3.12 convient (`requires-python = ">=3.12"`).

---

## 3. Configurer l'environnement

```bash
cp .env.production.example .env
nano .env
```

Générer la clé secrète :

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

`config/settings/production.py` **refuse de démarrer** si l'un de ces points
n'est pas respecté — c'est volontaire, chacun est directement exploitable :

| Contrôle | Pourquoi |
|---|---|
| `DJANGO_SECRET_KEY` ≠ valeur d'exemple | Signature des sessions et des cookies |
| `DJANGO_ALLOWED_HOSTS` sans `*` | Empoisonnement d'en-tête `Host` |
| `OTP_PROVIDER` ≠ `console` | Sinon le code est figé : n'importe qui entre sur n'importe quel compte |
| Identifiants WhatsApp présents si `OTP_PROVIDER=whatsapp` | Sinon personne ne reçoit son code : site en ligne mais inaccessible |
| Identifiants SingPay présents | Sinon le paiement (et le démarrage) est bloqué |
| `DEMO_STAFF_PASSWORD` vide | Ce compte est administrateur, et son mot de passe est dans le dépôt |

### Envoi du code de connexion

Les membres se connectent au numéro de téléphone + mot de passe. Le code par
e-mail ne sert qu'à la première connexion et aux mots de passe oubliés.
`OTP_PROVIDER=email` est le réglage attendu — voir § 10 pour le SMTP.

---

## 4. Base de données et cache

Créer la base depuis l'onglet **Databases**, puis :

```bash
cd ~/fallaman-web/Fallaman
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable      # indispensable : porte les quotas
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
```

Charger le référentiel métiers/villes (sans aucun compte de démonstration) :

```bash
.venv/bin/python manage.py seed_demo --reference-only
```

> Ne jamais lancer `seed_demo --with-accounts` en production : la commande
> refuse de s'exécuter, car elle créerait un administrateur au mot de passe
> connu publiquement.

---

## 5. Onglet « Web »

1. **Add a new web app** → *Manual configuration* → Python 3.13.
2. **Virtualenv** : `/home/<votrecompte>/fallaman-web/Fallaman/.venv`
3. **Source code** : `/home/<votrecompte>/fallaman-web/Fallaman`
4. **WSGI configuration file** : remplacer tout le contenu par celui de
   [deploy/pythonanywhere_wsgi.py](../deploy/pythonanywhere_wsgi.py), en
   substituant `<votrecompte>`.
5. **Static files** :

   | URL | Directory |
   |---|---|
   | `/static/` | `/home/<votrecompte>/fallaman-web/Fallaman/staticfiles` |
   | `/media/` | `/home/<votrecompte>/fallaman-web/Fallaman/media` |

6. **Force HTTPS** : activé.
7. **Reload**.

> Les fichiers média sont servis depuis votre propre domaine. C'est pour cela
> que [apps/core/uploads.py](../apps/core/uploads.py) refuse `.html` et `.svg` :
> un tel fichier téléversé s'exécuterait dans le contexte du site.

---

## 6. Tâches planifiées (onglet « Tasks »)

Sans elles, rien n'expire. À créer :

```
# Horaire
cd ~/fallaman-web/Fallaman && .venv/bin/python manage.py run_maintenance --hourly

# Quotidienne
cd ~/fallaman-web/Fallaman && .venv/bin/python manage.py run_maintenance --daily
```

Les offres gratuites ne permettent qu'**une** tâche quotidienne : utiliser
alors `run_maintenance` sans option (toutes les tâches), en acceptant que les
expirations aient jusqu'à 24 h de retard.

Détail des travaux : `run_maintenance --help`.

---

## 7. Paiement SingPay

### 7.1 URL de notification (webhook)

À déclarer côté SingPay :

```
https://<votredomaine>/paiements/singpay/callback/
```

### 7.2 Signature des webhooks

Le webhook n'est accepté que si **les deux** conditions sont réunies :

1. En-tête `X-Signature` valide — HMAC-SHA256 avec `SINGPAY_WEBHOOK_SECRET`
   (à défaut `SINGPAY_API_SECRET`), et `X-Timestamp` daté de moins de
   5 minutes (anti-rejeu).
2. Statut **reconfirmé auprès de l'API SingPay** par un appel serveur-à-serveur.
   Le contenu du webhook n'est jamais cru sur parole, même signé.

Sont également vérifiés avant tout crédit : le montant encaissé doit égaler le
montant attendu, et la transaction distante doit porter notre référence.

**Schéma de signature** — vérifié sur le code de production Gabomazone
(`payments/services/singpay.py`, `_generate_signature`) :

```
HMAC-SHA256(SINGPAY_API_SECRET, X-Timestamp + json.dumps(payload, sort_keys=True, separators=(',',':')))
```

C'est la première variante essayée par `_signature_candidates()`. Trois autres
conventions restent acceptées par sécurité.

> **Format de `X-Timestamp` :** non documenté par SingPay, et Gabomazone le
> traite comme une chaîne opaque. Fallaman sait lire l'epoch (secondes ou
> millisecondes) et l'ISO 8601. Face à un format inconnu, il journalise un
> avertissement et **laisse passer** le webhook — la signature et la
> revérification API restent appliquées. Une fois le format observé dans les
> logs, passez `SINGPAY_WEBHOOK_REQUIRE_FRESH_TIMESTAMP=true` pour activer
> l'anti-rejeu strict.

### 7.3 Reprendre les identifiants Gabomazone

Les deux projets utilisent **exactement les mêmes noms de variables**. Il n'y a
donc rien à renommer : copiez les quatre valeurs depuis le `.env` de
`Gabomazone-EAMAC/gabomazone-app/` vers celui de Fallaman.

```
SINGPAY_API_KEY
SINGPAY_API_SECRET
SINGPAY_MERCHANT_ID
SINGPAY_DISBURSEMENT_ID
```

> Vérifiez auprès de SingPay si votre contrat autorise le même portefeuille
> pour deux sites distincts, ou s'il vous faut un second jeu d'identifiants.
> Deux applications partageant le même `SINGPAY_MERCHANT_ID` verront leurs
> transactions mélangées dans le tableau de bord SingPay.

### 7.4 Recette avant ouverture

- [ ] Un paiement en sandbox aboutit et active bien la recommandation.
- [ ] Le webhook rejoué une seconde fois n'active pas l'achat deux fois.
- [ ] Un `POST` sur l'URL de callback **sans** en-tête `X-Signature` renvoie 400.
- [ ] Sans identifiants SingPay, la page de recommandation affiche
      « paiement indisponible » et **non** un formulaire gratuit.

---

## 8. Après chaque mise à jour

```bash
cd ~/fallaman-web
git pull
cd Fallaman
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
```

puis **Reload** dans l'onglet « Web ».

---

## 9. Diagnostic

| Symptôme | Piste |
|---|---|
| Erreur 502 au démarrage | Journal d'erreurs de l'onglet « Web » : un `ImproperlyConfigured` y détaille le réglage fautif |
| « Trop de tentatives » systématique | `createcachetable` n'a pas été lancé |
| Connexion impossible | Canal d'envoi mal configuré : voir § 10.3 pour tester WhatsApp en direct |
| Paiement « indisponible » | Identifiants SingPay absents, ou compte PythonAnywhere gratuit (§ 1.1) |
| Annonces qui n'expirent jamais | Tâches planifiées non créées (§ 6) |


---

## 10. Connexion et envoi des e-mails

### 10.1 Comment se connectent les membres

| Moment | Ce qui se passe |
|---|---|
| **Première connexion** | Numéro + adresse e-mail → un code à 6 chiffres arrive par e-mail → le membre choisit son mot de passe |
| **Connexions suivantes** | Numéro + mot de passe. Plus aucun message envoyé |
| **Mot de passe oublié** | Même parcours qu'une première connexion, mais le code part **toujours** à l'adresse déjà enregistrée |

Un seul e-mail par compte, à l'inscription : le volume reste négligeable, et
l'offre gratuite de n'importe quel service d'envoi suffit largement.

> **Le numéro de téléphone n'est plus vérifié.** Le code arrive par e-mail :
> rien ne prouve que la personne possède la ligne. Le badge « Téléphone
> vérifié » n'est donc plus attribué automatiquement — l'équipe le pose depuis
> le tableau de bord (fiche membre). C'est volontaire : mieux vaut un badge
> rare et vrai qu'un badge automatique et faux.

### 10.2 Configurer l'envoi (SMTP)

N'importe quel service SMTP convient. Deux options gratuites courantes :

| Service | Offre gratuite | Remarque |
|---|---|---|
| **Brevo** (ex-Sendinblue) | ~300 e-mails/jour | Bonne délivrabilité, interface en français |
| **Gmail** | ~500 e-mails/jour | Exige un « mot de passe d'application » et la validation en deux étapes |

Renseignez ensuite dans `.env` :

```
OTP_PROVIDER=email
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=Fallaman <no-reply@votredomaine.ga>
```

`config/settings/production.py` refuse de démarrer si `OTP_PROVIDER=email`
sans `EMAIL_HOST` : sans envoi, personne ne pourrait créer de compte.

> **Délivrabilité :** un `DEFAULT_FROM_EMAIL` sur un domaine que vous
> contrôlez, avec SPF et DKIM configurés, évite que les codes finissent en
> courrier indésirable. C'est le principal point de friction du parcours.

### 10.3 Vérifier

```bash
cd ~/fallaman-web/Fallaman
.venv/bin/python manage.py shell -c "
from apps.accounts.otp_delivery import deliver_email
deliver_email('+241XXXXXXXX', '123456', 'vous@exemple.com')
"
```

Une erreur `OTPDeliveryError` en indique la cause. Le détail SMTP est dans
`logs/fallaman.log`.

### 10.4 Comptes créés avant les mots de passe

Un compte existant sans adresse e-mail enregistrée **ne peut pas être activé en
libre-service** : accepter une adresse saisie librement reviendrait à offrir le
compte au premier venu connaissant le numéro. Ces comptes affichent un message
invitant à contacter l'équipe, qui renseigne l'adresse depuis l'administration
Django avant que le membre relance l'activation.

### 10.5 Autre canal

`OTP_PROVIDER=whatsapp` existe aussi dans
[apps/accounts/otp_delivery.py](../apps/accounts/otp_delivery.py) et fonctionne
avec la WhatsApp Cloud API de Meta, si vous préférez ce canal plus tard. Il
demande un compte Meta Business et un modèle de message approuvé — d'où le
choix de l'e-mail par défaut.
