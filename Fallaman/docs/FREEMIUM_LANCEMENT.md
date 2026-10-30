# Fallaman : lancement gratuit, offres et gestion

## Ce que les utilisateurs obtiennent gratuitement

Rechercher un travailleur, consulter les annonces, publier un besoin, candidater et prendre contact restent gratuits. L'accueil propose deux entrées : trouver quelqu'un et trouver du travail. La publication comporte trois étapes. Les suggestions combinent métier ET ville.

L'annuaire est volontaire : chaque travailleur active sa présence, indique son métier, sa ville et sa disponibilité. Une disponibilité doit être confirmée au moins tous les 30 jours. Les anciens profils ne sont pas inscrits automatiquement. Un profil public ou un numéro confirmé ne constituent pas une garantie sur les compétences.

Les conversations expirent après 30 jours pour les nouvelles conversations. Les anciennes conservent leur échéance. Les messages nécessaires à un signalement ouvert sont conservés jusqu'à son traitement.

## Monétisation progressive

Les ventes sont désactivées par défaut. Dans **Administration → Pilotage → Offres et lancement**, l'équipe peut activer séparément les boosts et les packs, modifier les prix et définir l'audience minimale.

| Offre | Prix initial | Prestation |
|---|---:|---|
| Boost d'annonce | 1 000 FCFA | Mise en avant pendant 3 jours, identifiée « Sponsorisé » |
| Pack recruteur | 10 000 FCFA | 30 jours, 4 crédits de boost et une demande d'aide à la rédaction |

Le pack se renouvelle manuellement. Les crédits doivent être utilisés pendant sa validité ; un boost activé conserve ses trois jours. Le pack se justifie surtout par l'aide humaine : si cette aide ne peut pas être assurée, laisser le pack désactivé. Quatre boosts seuls coûtent initialement 4 000 FCFA : présenter clairement cette différence au recruteur.

Une vente nécessite une annonce éligible et au moins le nombre configuré de profils disponibles dans le même métier et la même ville (3 par défaut). Ce seuil protège d'une vente sans audience identifiable, mais ne garantit aucun contact ni recrutement. La fermeture des nouvelles ventes n'annule pas les crédits déjà achetés.

## Routine de gestion

Chaque jour, traiter les signalements et les annonces à modérer, répondre aux demandes d'aide, vérifier les paiements en attente chez SingPay et examiner les annonces sans contact après 48 heures. Une annonce masquée ou clôturée ne doit pas être republiée par un paiement tardif ; un paiement correspondant apparaît comme prestation annulée à examiner pour remboursement.

Chaque semaine, suivre dans Pilotage :

- Les annonces ayant reçu un premier contact sous 48 heures, jugé pertinent ensuite par leur auteur. Le dénominateur exclut les annonces qui n'ont pas encore 48 heures.
- Les résultats positifs déclarés et ceux confirmés par les deux personnes.
- Les employeurs qui publient de nouveau, les clients qui rachètent et les demandes de support.
- Les encaissements SingPay confirmés, les dépenses saisies et leur différence.

Un clic WhatsApp indique une intention de contact, pas une conversation ni une embauche. Les retours sont déclaratifs et facultatifs. Les filtres géographiques concernent les mises en relation ; les finances couvrent toute l'application. Le solde affiché n'est pas un bénéfice comptable : saisir notamment les frais de paiement, le support, l'hébergement, l'acquisition et les remboursements effectués. Saisir un remboursement ne le déclenche pas chez SingPay.

## Plan terrain sur 90 jours

**Jours 1–30 : constituer une offre utile.** Choisir dans l'administration les raccourcis Libreville, Owendo et Akanda lorsqu'ils existent dans la liste, et trois métiers selon les besoins recueillis sur le terrain. L'accès reste ouvert au reste du Gabon. Recruter personnellement une première cohorte de travailleurs volontaires, les aider à compléter leur profil et recueillir de vrais besoins d'employeurs. Garder les ventes fermées. Revoir chaque semaine les demandes sans réponse et les motifs d'abandon.

**Jours 31–60 : vérifier la valeur.** Faire confirmer les disponibilités et les résultats. Quand les mises en relation aboutissent régulièrement dans un métier et une ville, tester le boost auprès de quelques recruteurs. Comparer la réponse pertinente et la satisfaction des annonces sponsorisées avec les autres en tenant compte de leurs différences. Ajuster le prix depuis l'administration ; ne pas conclure à un effet du boost sur quelques observations.

**Jours 61–90 : tester les achats répétés.** Proposer le pack uniquement aux recruteurs récurrents si l'équipe peut assurer l'aide incluse. Mesurer les rachats, le temps de support et les dépenses réelles. Étendre les métiers ou les villes lorsque la qualité des mises en relation se maintient. Le recrutement terrain et le support restent des actions humaines à organiser ; ils ne sont pas exécutés automatiquement par l'application.

## Mise en service

1. Sauvegarder la base de production et les médias, puis tester la restauration dans un environnement séparé.
2. Livrer le code, installer les dépendances habituelles, exécuter `python manage.py migrate`, puis `python manage.py collectstatic --noinput` et redémarrer les services web et les tâches planifiées.
3. Vérifier la publication, l'inscription, la présence volontaire dans l'annuaire et les droits administrateur.
4. Pour une inscription sans email, configurer le fournisseur WhatsApp et ses identifiants puis `OTP_PROVIDER=whatsapp`. Tant qu'il n'est pas configuré, conserver le canal opérationnel existant. Tester la réception sur un vrai téléphone avant le lancement.
5. Configurer SingPay et vérifier un paiement réel avec son retour serveur avant d'activer les ventes. Un retour navigateur seul ne doit pas suffire à créditer une prestation. Tester également un échec et une notification répétée.
6. Renseigner les liens des stores seulement lorsque les applications sont effectivement disponibles. La coque Flutter cible `https://fallaman.gabomazone.com` en version release ; sa publication nécessite une compilation et une validation sur appareil.

Les migrations ajoutent les paramètres, les contacts, les résultats, les packs, le suivi d'aide et les dépenses. Elles ajoutent aussi le consentement à l'annuaire aux profils et le type de paiement du pack. Pour revenir en arrière après des paiements réels, préparer une procédure conservant toutes les transactions : ne pas restaurer aveuglément une ancienne sauvegarde ni supprimer les nouvelles tables.

Ces modifications sont préparées et testées localement. Leur présence dans le dépôt ne constitue pas un déploiement de production, une validation réelle des fournisseurs ni une publication sur les stores.
