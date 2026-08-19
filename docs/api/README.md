# Conventions de l'API

L'API est servie par Django REST Framework sous le préfixe `/api/`, et sa spécification OpenAPI est **dérivée du code** par drf-spectacular — jamais écrite à la main. La CI échoue si `openapi.yaml` dérive des routes, pour que les clients ne divergent pas de l'implémentation.

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

## Chemins

Les chemins portent une barre oblique finale, convention de Django et des routeurs DRF : `/api/health/`, `/api/households/{household_id}/persons/`.

## Corps et schémas

Toutes les entrées et sorties sont en JSON.

Un serializer par opération : `XCreate`, `XUpdate`, `XRead`. Jamais un schéma fourre-tout partagé entre l'entrée et la sortie — c'est ce qui laisse fuiter un jour un champ interne dans une réponse, ou accepter un identifiant fourni par le client.

Rien du corps ne porte d'identité : les identifiants de ressource viennent du chemin. Un `household_id` glissé dans le corps est ignoré.

## Écriture partielle

`PATCH`, pas `PUT`. Le client édite un champ à la fois ; un `PUT` l'obligerait à réémettre une représentation complète, donc à écraser des champs qu'il ne connaît pas. Un champ absent et un `null` explicite laissent tous deux la valeur inchangée, et un corps vide est une requête valide sans effet.

## Collections

Les collections sont renvoyées comme des tableaux JSON nus, sans enveloppe ni pagination. C'est volontairement provisoire : aucune collection actuelle ne peut croître sans borne — les personnes d'un foyer, ses voyages. La pagination sera ajoutée quand une collection le justifiera, vraisemblablement les objets d'une liste, et pas avant, pour ne pas imposer dès maintenant une enveloppe à tous les appelants.

Une collection vide renvoie `[]` et non `404` : la collection existe, elle est vide.

## Authentification

Assurée par django-allauth en mode headless, sans qu'aucun template ne soit rendu. Les endpoints et le choix entre cookie de session et jeton sont documentés ici une fois la brique en place.

Le socle précédent était écrit à la main sur PyJWT et pwdlib, avec ses propres tables d'identités et de jetons de rafraîchissement. Il a été abandonné avec la migration vers Django : allauth couvre l'inscription, la connexion, la vérification d'email, la réinitialisation de mot de passe et les fournisseurs externes, c'est-à-dire précisément ce qu'il aurait fallu continuer d'écrire et de faire relire.

## Pourquoi Django et DRF

L'API est prioritaire ici pour servir plusieurs clients sans dupliquer la logique, ce qui suppose une spécification OpenAPI dérivée du code. drf-spectacular la génère depuis les vues et les serializers, et la CI vérifie qu'elle ne dérive pas.

DRF est la couche API de référence de l'écosystème Django : c'est elle que les briques tierces intègrent d'origine, django-allauth en tête, et elle apporte montées les permissions, la limitation de débit et la négociation de contenu que la façade aurait dû assembler autrement.

Pydantic ne quitte pas le projet pour autant, et `drf-pydantic` est câblé : un modèle Pydantic expose son serializer DRF dérivé par `Model.drf_serializer`, ce qui permet à un même modèle d'être à la fois la cible d'un appel PydanticAI et le schéma d'une réponse. `/api/health/` en est l'exemple vivant plutôt qu'une promesse — la spécification générée est identique à celle qu'un serializer écrit à la main produisait.

Deux façons de déclarer un schéma coexistent donc, et le choix n'est pas laissé au goût : `ModelSerializer` pour ce qui est adossé à l'ORM, puisqu'il dérive les champs du modèle Django, et Pydantic pour ce qui n'a pas de table derrière lui — la sortie d'un modèle de langage, une réponse calculée. C'est la vraie contrepartie de DRF : l'uniformité de déclaration, pas Pydantic lui-même.

La spécification est émise en OpenAPI 3.0.3, défaut de drf-spectacular ; `OAS_VERSION` force 3.1.0 si un générateur de client le réclame.

Le raisonnement complet, les candidats écartés et la correspondance brique par brique sont dans l'issue de migration plutôt que répétés ici.
