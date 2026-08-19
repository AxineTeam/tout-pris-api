# Conventions de l'API

## Codes HTTP

| Code | Quand |
| --- | --- |
| `200` | Lecture ou action réussie qui renvoie un corps |
| `201` | Création d'une ressource |
| `204` | Action réussie sans corps (suppression, révocation) |
| `401` | Requête non authentifiée : bearer absent, illisible, expiré, ou compte disparu |
| `404` | Ressource inexistante **ou** appartenant à un autre foyer |
| `409` | Conflit avec une ressource existante (email déjà inscrit) |
| `422` | Corps invalide au sens des schémas Pydantic |

Le `403` n'est jamais renvoyé. Une ressource qui existe mais que l'appelant n'a pas le droit de voir répond `404`, exactement comme si elle n'existait pas : distinguer les deux cas révélerait l'existence de foyers, de personnes ou de voyages à un tiers. La dépendance `get_current_household` implémente cette règle par une seule requête qui joint `household_members` sur l'utilisateur courant — une ligne absente et un foyer inexistant produisent la même réponse.

Les routes du domaine sont donc portées par le chemin du foyer : `/households/{household_id}/persons`, `/households/{household_id}/trips`, etc. Le cloisonnement est appliqué par la dépendance, pas par chaque route.

## Corps et schémas

Toutes les entrées et sorties sont en JSON, y compris l'authentification : le client est une application mobile, pas un navigateur, et n'a aucune raison de passer par le formulaire `application/x-www-form-urlencoded` d'OAuth2.

Un schéma Pydantic par opération : `XCreate`, `XUpdate`, `XRead`. Jamais un schéma fourre-tout partagé entre l'entrée et la sortie — c'est ce qui laisse fuiter un jour un hash de mot de passe dans une réponse, ou accepter un `id` fourni par le client.

## Collections

Les collections sont renvoyées comme des tableaux JSON nus, sans enveloppe ni pagination. C'est volontairement provisoire : aucune collection actuelle ne peut croître sans borne (les personnes d'un foyer, ses voyages). La pagination sera ajoutée quand une collection le justifiera — vraisemblablement les objets d'une liste — et pas avant, pour ne pas imposer dès maintenant une enveloppe à tous les appelants.

## Ressources et verbes

Une ressource est nommée au pluriel et n'est jamais un verbe : `/households`, `/households/{household_id}/persons`. Une ressource qui n'existe que dans un foyer est imbriquée sous lui, jamais exposée à la racine avec un identifiant global : `/persons/{person_id}` obligerait chaque route à retrouver le foyer pour vérifier l'accès, alors que l'imbrication le confie à `get_current_household` une fois pour toutes. L'imbrication s'arrête à deux niveaux ; une ressource plus profonde sera rattachée au foyer directement plutôt qu'enchaînée.

| Verbe | Chemin | Succès |
| --- | --- | --- |
| `POST` | collection | `201` avec la ressource créée |
| `GET` | collection | `200` avec un tableau |
| `GET` | élément | `200` avec la ressource |
| `PATCH` | élément | `200` avec la ressource à jour |
| `DELETE` | élément | `204` sans corps |

`PATCH` et non `PUT` : le client mobile modifie un champ à la fois, et un `PUT` l'obligerait à renvoyer une représentation complète — donc à écraser les champs qu'il ne connaît pas encore. Un champ absent du corps laisse la valeur inchangée, un champ à `null` aussi : aucun champ modifiable n'est actuellement effaçable, et un corps vide est une requête valide qui ne change rien.

L'identifiant d'une ressource et son foyer de rattachement ne sont jamais lus dans le corps : ils viennent du chemin. `POST /households/{household_id}/persons` avec un `household_id` dans le corps l'ignore. C'est ce qui rend le cloisonnement infalsifiable côté client.

## Foyers et personnes

- `POST /households` — crée le foyer **et** la ligne `household_members` de l'appelant avec le rôle `owner`. C'est aujourd'hui le seul moyen d'entrer dans un foyer : l'inscription n'en crée aucun et il n'existe pas encore d'invitation.
- `GET /households` — ne renvoie que les foyers dont l'appelant est membre. Un compte sans foyer reçoit `[]`, jamais `404` : la collection existe, elle est vide.
- `GET`, `PATCH`, `DELETE /households/{household_id}` — passent par `get_current_household`, donc `404` sur un foyer inconnu comme sur un foyer dont l'appelant n'est pas membre.
- `DELETE /households/{household_id}` — supprime le foyer, ses membres et ses personnes en cascade.
- `/households/{household_id}/persons` — les cinq opérations passent d'abord par le foyer. Une personne dont l'identifiant existe mais qui appartient à un autre foyer répond `404 Person not found`, exactement comme un identifiant inexistant.

Le rôle `owner` n'ouvre aujourd'hui aucun droit particulier : n'importe quel membre peut renommer ou supprimer le foyer. La colonne est posée pour une différenciation ultérieure des droits, elle n'est pas encore appliquée.

Une personne n'est pas rattachable à un compte par l'API : `PersonCreate` et `PersonUpdate` n'acceptent que `name`. Accepter un `user_id` fourni par le client laisserait rattacher n'importe quel compte à une personne de son propre foyer, et l'échec ou le succès de la clé étrangère révélerait quels identifiants de compte existent. Le rattachement viendra avec le flux d'invitation, qui sera consenti par le compte invité.

## Authentification

L'accès est un jeton porteur : `Authorization: Bearer <access_token>`.

- `POST /auth/register` — `{email, password}` puis `201` avec une paire de jetons. Crée un `User` et son `Identity` de fournisseur `password`. Ne crée aucun foyer.
- `POST /auth/login` — `{email, password}` puis `200` avec une paire de jetons.
- `POST /auth/refresh` — `{refresh_token}` puis `200` avec une nouvelle paire. Le jeton présenté est révoqué au passage.
- `POST /auth/logout` — `{refresh_token}` puis `204`. Révoque la ligne, et répond `204` même si elle était déjà révoquée ou inconnue.
- `GET /auth/me` — `200` avec le compte authentifié.

Un échec de connexion renvoie toujours `Invalid credentials`, que l'email soit inconnu ou le mot de passe faux, et le temps de réponse est égalisé en vérifiant le mot de passe fourni contre un hash impossible à satisfaire quand aucune identité ne correspond. Sans cela, la durée de la réponse suffirait à énumérer les comptes.

### Deux jetons, deux natures

L'`access_token` est un JWT HS256 court (15 minutes par défaut) portant `sub`, `iat` et `exp`. Il n'est pas révocable : sa durée de vie est sa seule limite, et c'est assumé.

Le `refresh_token` est au contraire opaque — 32 octets aléatoires — et n'existe en base que sous forme de condensat SHA-256. Il est donc révocable, ce qui est toute la raison de ne pas en faire un JWT : une déconnexion doit réellement fermer la session. Il est aussi tourné à chaque rafraîchissement, l'ancien étant révoqué au moment où le nouveau est émis, ce qui borne la fenêtre d'exploitation d'un jeton volé.

Le SHA-256 suffit ici, là où le mot de passe exige argon2 : un jeton de 256 bits tiré au hasard n'est pas attaquable par dictionnaire, un mot de passe si.

### Ce qui n'est pas fait dans ce socle

La limitation de débit sur `/auth/login`, la détection de réutilisation d'un jeton de rafraîchissement déjà tourné (révocation de toute la famille), la vérification d'email et la réinitialisation de mot de passe ne sont pas implémentées. Elles viendront dans leurs propres lots.

`/auth/refresh` ne verrouille pas la ligne qu'il fait tourner : deux appels simultanés portant le même jeton peuvent réussir tous les deux et repartir avec deux paires valides. C'est le même trou que la détection de réutilisation doit couvrir, et il se ferme au même endroit — un `SELECT ... FOR UPDATE` ou une révocation conditionnelle rendant la rotation atomique.

`refresh_tokens` ne se purge jamais : chaque connexion et chaque rotation ajoute une ligne, révoquée mais conservée. De l'ordre de quelques dizaines de milliers de lignes par an et par compte actif, ce que l'index sur `token_hash` absorbe sans peine. C'est de l'hygiène à traiter un jour, pas un problème de tenue en charge.

`SECRET_KEY` n'a **aucune valeur par défaut dans l'application** : `Settings()` lève `Field required` au démarrage si la variable d'environnement est absente. Une clé de signature publiée dans le dépôt serait exploitable par quiconque lit le code, quel que soit le mode de déploiement. Les deux fichiers compose et le `Makefile` fournissent un placeholder `change-me-...` pour le développement et les tests ; en production la variable doit porter au moins 32 octets aléatoires, longueur en dessous de laquelle PyJWT émet un avertissement.

## Pourquoi pas fastapi-users

`fastapi-users` couvre exactement ce périmètre, et a pourtant été écarté :

- le projet est en mode maintenance déclaré, aucune fonctionnalité nouvelle n'y sera ajoutée ;
- il est exclusivement asynchrone, ce qui imposerait de basculer toute la pile (voir plus bas) ;
- surtout, il impose ses colonnes sur le modèle `User` : `hashed_password`, `is_active`, `is_superuser`, `is_verified`. Or `User` doit rester nu et déléguer l'authentification à `Identity`, une ligne par fournisseur, pour que Google ou Facebook s'ajoutent plus tard sans migration destructive. Un `hashed_password` sur `User` ferme cette porte le jour de son ajout.

Les autres candidats répondent à d'autres questions :

- **Authlib** et **httpx-oauth** sont des briques OAuth/OIDC : elles savent parler à un fournisseur, pas gérer des comptes, des mots de passe ni des sessions. Elles resteront pertinentes quand les fournisseurs externes arriveront, à côté de ce socle et non à sa place.
- **AuthX** ne fait que le JWT — soit la partie la plus courte à écrire ici, et celle qui ne couvre ni les identités ni la révocation.
- **python-social-auth** est pensé pour Django ; son intégration FastAPI est marginale et son modèle de données étranger au nôtre.
- Un **fournisseur d'identité externe** (Keycloak, Auth0, Clerk) est surdimensionné pour un backend familial auto-hébergé sur un Raspberry Pi : il ajouterait un service à opérer, ou une dépendance payante à un tiers, pour une inscription par email et mot de passe.

Le socle écrit à la main tient en quatre fichiers courts et n'emprunte que deux bibliothèques éprouvées et à responsabilité unique : PyJWT pour signer, pwdlib pour hacher en argon2.

## Pourquoi la pile reste synchrone

Les routes sont déclarées en `def`, pas en `async def`. FastAPI exécute alors chaque route dans le threadpool d'anyio : la boucle d'événements n'est jamais bloquée, et le code appelle SQLAlchemy 2.0 en synchrone sans précaution particulière.

Passer à l'asynchrone n'apporterait rien ici et coûterait cher :

- SQLite sérialise les écritures de toute façon, un seul écrivain à la fois ; la concurrence gagnée serait fictive ;
- SQLAlchemy async repose sur greenlet, ce qui transforme le moindre accès paresseux hors contexte en `MissingGreenlet` et impose de charger explicitement chaque relation (`selectinload`) sous peine d'erreur à l'exécution plutôt qu'à l'écriture ;
- les tests devraient basculer sur `AsyncClient` et un plugin asyncio, et le hachage argon2 resterait de toute façon un travail CPU à déporter dans un thread.

Le jour où la base deviendra PostgreSQL et où la charge le justifiera, la bascule se fera route par route. Elle n'est pas un prérequis de l'authentification.
