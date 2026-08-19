# Conventions de l'API

L'API est servie par django-ninja sous le préfixe `/api`, et sa spécification OpenAPI est **dérivée du code** — jamais écrite à la main. La CI échoue si `openapi.json` dérive des routes, pour que les clients ne divergent pas de l'implémentation.

## Codes HTTP

| Code | Quand |
| --- | --- |
| `200` | Lecture ou action réussie qui renvoie un corps |
| `201` | Création d'une ressource |
| `204` | Action réussie sans corps |
| `401` | Requête non authentifiée |
| `404` | Ressource inexistante **ou** appartenant à un autre foyer |
| `409` | Conflit avec une ressource existante |
| `422` | Corps invalide au sens des schémas |

Le `403` n'est jamais renvoyé. Une ressource qui existe mais que l'appelant n'a pas le droit de voir répond `404`, exactement comme si elle n'existait pas : distinguer les deux cas révélerait l'existence de foyers, de personnes ou de voyages à un tiers.

Les routes du domaine sont donc portées par le chemin du foyer — `/api/households/{household_id}/persons`, `/api/households/{household_id}/trips` — et le cloisonnement est appliqué une fois pour toutes par la couche qui résout le foyer courant, jamais réécrit dans chaque route.

Cette règle n'a pas encore de porteur dans le code : les endpoints du domaine ne sont dans aucune des sous-issues de la migration. Elle s'applique dès qu'ils arrivent.

## Corps et schémas

Toutes les entrées et sorties sont en JSON.

Un schéma par opération : `XCreate`, `XUpdate`, `XRead`. Jamais un schéma fourre-tout partagé entre l'entrée et la sortie — c'est ce qui laisse fuiter un jour un champ interne dans une réponse, ou accepter un identifiant fourni par le client.

Rien du corps ne porte d'identité : les identifiants de ressource viennent du chemin. Un `household_id` glissé dans le corps est ignoré.

## Écriture partielle

`PATCH`, pas `PUT`. Le client édite un champ à la fois ; un `PUT` l'obligerait à réémettre une représentation complète, donc à écraser des champs qu'il ne connaît pas. Un champ absent et un `null` explicite laissent tous deux la valeur inchangée, et un corps vide est une requête valide sans effet.

## Collections

Les collections sont renvoyées comme des tableaux JSON nus, sans enveloppe ni pagination. C'est volontairement provisoire : aucune collection actuelle ne peut croître sans borne — les personnes d'un foyer, ses voyages. La pagination sera ajoutée quand une collection le justifiera, vraisemblablement les objets d'une liste, et pas avant, pour ne pas imposer dès maintenant une enveloppe à tous les appelants.

Une collection vide renvoie `[]` et non `404` : la collection existe, elle est vide.

## Authentification

Assurée par django-allauth en mode headless, sans qu'aucun template ne soit rendu. Les endpoints et le choix entre cookie de session et jeton sont documentés ici une fois la brique en place.

Le socle précédent était écrit à la main sur PyJWT et pwdlib, avec ses propres tables d'identités et de jetons de rafraîchissement. Il a été abandonné avec la migration vers Django : allauth couvre l'inscription, la connexion, la vérification d'email, la réinitialisation de mot de passe et les fournisseurs externes, c'est-à-dire précisément ce qu'il aurait fallu continuer d'écrire et de faire relire.

## Pourquoi Django et django-ninja

L'API est prioritaire ici pour servir plusieurs clients sans dupliquer la logique, ce qui suppose une spécification OpenAPI dérivée du code. django-ninja la génère comme le faisait FastAPI, en conservant Pydantic et les annotations de type, tout en donnant accès aux briques montées de l'écosystème Django — authentification, back-office, permissions, ordonnancement.

Le raisonnement complet, les candidats écartés et la correspondance brique par brique sont dans l'issue de migration plutôt que répétés ici.
