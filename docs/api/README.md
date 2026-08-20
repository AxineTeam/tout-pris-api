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

Assurée par django-allauth en mode headless (`HEADLESS_ONLY`), monté sur `/api/auth/`, sans qu'aucun template ne soit rendu : les vues d'allauth qui rendaient des pages ne sont même pas déclarées dans l'URLconf, seuls subsistent les endpoints JSON et les callbacks des fournisseurs sur `/accounts/`.

Un seul client allauth est activé, le client `browser` : la session est portée par le cookie `sessionid`, `httpOnly` et marqué `Secure` en production. Le front étant servi sur le même domaine, ce cookie bat le jeton sur la révocation immédiate et sur l'exposition aux XSS, et évite une danse de refresh côté client. Le client `app` d'allauth, qui authentifie par jeton `X-Session-Token`, reste désactivé : l'activer ouvrirait un second chemin d'authentification à côté de la session, exactement ce que le retrait de `BasicAuthentication` avait fermé. `SessionAuthentication` de DRF lit cette même session, sans classe d'authentification supplémentaire.

Les endpoints suivent la spécification d'allauth, préfixés par `/api/auth/browser/v1/` : `auth/signup`, `auth/login`, `auth/session` (`GET` pour lire la session, `DELETE` pour se déconnecter), `auth/email/verify`, `auth/password/request`, `auth/password/reset`, `auth/provider/redirect`, `account/password/change`, `account/email`, `config`. Ils sont tous décrits dans `openapi.yaml`.

Ces endpoints ne sont pas des vues DRF : `DEFAULT_PERMISSION_CLASSES` ne s'y applique pas, et l'inscription comme la connexion répondent donc à un appelant anonyme sans réglage particulier. C'est vérifié par les tests plutôt que supposé, un endpoint d'inscription fermé par héritage se remarquant très tard.

Le code de statut suit lui aussi la convention d'allauth et non le tableau ci-dessus : `401` signifie « la session n'est pas authentifiée », y compris quand l'appel a réussi. Une inscription en attente de vérification d'email et une réinitialisation de mot de passe réussie répondent `401` avec l'état du flux dans le corps. Le `403` que Django renvoie sur un jeton CSRF manquant échappe de même à la règle « jamais de 403 » : il est émis par le middleware, avant toute logique de domaine.

L'identifiant de connexion est l'email (`ACCOUNT_LOGIN_METHODS = {"email"}`), unique côté application (`ACCOUNT_UNIQUE_EMAIL`) comme en base depuis la contrainte portée par le modèle `User`. `USERNAME_FIELD` reste `username` : allauth le remplit à partir de l'email, il n'est jamais demandé ni exposé.

La vérification d'email est obligatoire : tant qu'elle n'est pas faite, la session reste non authentifiée. Confirmer depuis le navigateur qui a lancé l'inscription ouvre la session directement (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION`) ; allauth n'ouvre cette session que si l'inscription en cours est présente dans la session, un lien intercepté ailleurs ne connecte donc personne.

Les liens envoyés par email pointent vers le front, pas vers l'API : `HEADLESS_FRONTEND_URLS` compose les URL de vérification et de réinitialisation à partir de `FRONTEND_URL`, et le front repasse la clé à l'endpoint correspondant.

Un fournisseur externe est branché, Google, configuré depuis l'environnement (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_SECRET`) et non en base : aucun secret n'est versionné et il n'y a pas de `SocialApp` à créer dans l'admin. Le front poste sur `auth/provider/redirect`, l'utilisateur revient sur `/accounts/google/login/callback/`, et allauth ouvre la session. Une connexion par fournisseur ne se rattache pas d'elle-même à un compte local existant qui porterait la même adresse : `SOCIALACCOUNT_EMAIL_AUTHENTICATION` reste désactivé, sans quoi un fournisseur qui affirme une adresse suffirait à prendre le compte.

Les limitations de débit d'allauth (`ACCOUNT_RATE_LIMITS`) sont laissées à leurs valeurs par défaut et s'appuient sur le cache Django. Le cache par défaut étant local au processus, les compteurs sont par worker : un cache partagé sera nécessaire le jour où l'API tournera sur plusieurs processus.

Le socle précédent était écrit à la main sur PyJWT et pwdlib, avec ses propres tables d'identités et de jetons de rafraîchissement. Il a été abandonné avec la migration vers Django : allauth couvre l'inscription, la connexion, la vérification d'email, la réinitialisation de mot de passe et les fournisseurs externes, c'est-à-dire précisément ce qu'il aurait fallu continuer d'écrire et de faire relire.

### Les endpoints d'authentification dans la spécification

drf-spectacular ne décrit que les vues DRF ; les vues d'allauth lui sont invisibles. **Il y a donc deux spécifications, et c'est assumé** — leur absence de fusion n'est pas une régression.

`openapi.yaml`, committé à la racine et vérifié en CI, décrit l'API du domaine. allauth publie la sienne sur `/api/auth/openapi.yaml` et `/api/auth/openapi.json`, servies par l'application sans qu'on ait rien à câbler, dérivées de son code et élaguées selon la configuration réellement chargée : les endpoints non montés en sont retirés.

Les fusionner demanderait de sous-classer le générateur de drf-spectacular, soit de la glu maison à maintenir au rythme des deux bibliothèques, pour un bénéfice de confort. Un client qui a besoin des deux les lit à deux adresses.

## Pourquoi Django et DRF

L'API est prioritaire ici pour servir plusieurs clients sans dupliquer la logique, ce qui suppose une spécification OpenAPI dérivée du code. drf-spectacular la génère depuis les vues et les serializers, et la CI vérifie qu'elle ne dérive pas.

DRF est la couche API de référence de l'écosystème Django : c'est elle que les briques tierces intègrent d'origine, django-allauth en tête, et elle apporte montées les permissions, la limitation de débit et la négociation de contenu que la façade aurait dû assembler autrement.

Pydantic ne quitte pas le projet pour autant, et `drf-pydantic` est câblé : un modèle Pydantic expose son serializer DRF dérivé par `Model.drf_serializer`, ce qui permet à un même modèle d'être à la fois la cible d'un appel PydanticAI et le schéma d'une réponse. `/api/health/` en est l'exemple vivant plutôt qu'une promesse — la spécification générée est identique à celle qu'un serializer écrit à la main produisait.

Deux façons de déclarer un schéma coexistent donc, et le choix n'est pas laissé au goût : `ModelSerializer` pour ce qui est adossé à l'ORM, puisqu'il dérive les champs du modèle Django, et Pydantic pour ce qui n'a pas de table derrière lui — la sortie d'un modèle de langage, une réponse calculée. C'est la vraie contrepartie de DRF : l'uniformité de déclaration, pas Pydantic lui-même.

La spécification est émise en OpenAPI 3.0.3, défaut de drf-spectacular ; `OAS_VERSION` force 3.1.0 si un générateur de client le réclame.

Le raisonnement complet, les candidats écartés et la correspondance brique par brique sont dans l'issue de migration plutôt que répétés ici.
