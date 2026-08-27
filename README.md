# Fallaman — web

> Trouvez quelqu'un. Trouvez du travail.

Plateforme de mise en relation entre particuliers et travailleurs au Gabon
(nounous, maçons, chauffeurs, ménage…). Django 5.2, HTMX, PostgreSQL.

## Structure du dépôt

Le projet Django vit dans le sous-dossier [`Fallaman/`](Fallaman/) — c'est là
que se trouve `manage.py`.

```
Fallaman/
├── apps/            applications métier (annonces, paiements, messagerie…)
├── config/          réglages Django (base / development / production)
├── templates/       gabarits HTML
├── tests/           suite pytest
├── deploy/          fichier WSGI pour PythonAnywhere
└── docs/            prise en main et déploiement
```

## Démarrer en local

```bash
cd Fallaman
docker compose -f docker-compose.dev.yml up
```

Le site répond sur http://localhost:8001.

En développement, le code de connexion s'affiche dans les logs du conteneur
(`OTP_PROVIDER=console`, code `123456`) :

```bash
docker compose -f docker-compose.dev.yml logs -f web | grep "FALLAMAN DEV"
```

Sans Docker : voir [Fallaman/docs/PRISE_EN_MAIN.md](Fallaman/docs/PRISE_EN_MAIN.md).

## Tests

```bash
cd Fallaman
python -m pytest
```

## Déploiement

Voir [Fallaman/docs/DEPLOIEMENT_PYTHONANYWHERE.md](Fallaman/docs/DEPLOIEMENT_PYTHONANYWHERE.md).

Deux points à connaître avant de déployer :

- **Un compte PythonAnywhere payant est nécessaire.** Les comptes gratuits
  n'ont pas d'accès sortant libre : ni l'envoi des codes par e-mail (SMTP), ni
  les appels à SingPay ne fonctionneraient.
- `config/settings/production.py` **refuse de démarrer** si un réglage
  sensible est laissé en l'état (clé secrète d'exemple, `OTP_PROVIDER=console`,
  `SINGPAY_MOCK=true`…). C'est volontaire : chacun de ces cas est directement
  exploitable.

## Connexion

- **Première connexion / mot de passe oublié** — un code à six chiffres part
  par e-mail, puis le membre choisit son mot de passe.
- **Connexions suivantes** — numéro de téléphone + mot de passe.

Pour un compte existant, le code part toujours à l'adresse enregistrée, jamais
à celle saisie dans le formulaire : sans cette règle, connaître un numéro de
téléphone suffirait à s'emparer du compte.

## Paiements

Recommandations payantes (mise en avant d'annonce ou de profil) via
**SingPay**. Avant toute activation, deux vérifications indépendantes :
signature HMAC du webhook, **et** statut reconfirmé auprès de l'API SingPay par
un appel serveur-à-serveur. Le montant encaissé doit égaler le montant attendu.
