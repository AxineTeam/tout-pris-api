# Conventions de l'API

L'API est servie par Django REST Framework sous le préfixe `/api/`, et sa spécification OpenAPI est **dérivée du code** par drf-spectacular — jamais écrite à la main. La CI échoue si `openapi.yaml` dérive des routes, pour que les clients ne divergent pas de l'implémentation.

## Codes HTTP

| Code | Quand |
| --- | --- |
| `200` | Lecture ou action réussie qui renvoie un corps |
| `201` | Création d'une ressource |
| `204` | Action réussie sans corps |
| `401` | Requête non authentifiée |
| `403` | Ressource de votre foyer que votre rôle n'autorise pas à toucher |
| `429` | Limite d'envoi ou de débit atteinte |
| `404` | Ressource inexistante **ou** appartenant à un autre foyer |
| `409` | Conflit avec une ressource existante |
| `422` | Corps invalide au sens des schémas |

Une session non authentifiée reçoit bien `401` et non le `403` que DRF renvoie par défaut : DRF ne choisit `401` que si une classe d'authentification annonce un en-tête `WWW-Authenticate`, et `SessionAuthentication` n'en annonce aucun. `tout_pris.authentication.SessionAuthentication` en annonce un, pour que « connecte-toi » se lise sur un seul code quel que soit l'endpoint — allauth répond déjà `401`. Le schéma annoncé est `Session` et non `Basic`, il ne déclenche donc aucune fenêtre d'authentification du navigateur, et une extension de drf-spectacular garde la description `cookieAuth` dans la spécification, que le renommage de la classe lui avait fait perdre.

Le `403` ne dit jamais qu'une ressource existe ailleurs. Une ressource qui existe mais que l'appelant n'a pas le droit de **voir** répond `404`, exactement comme si elle n'existait pas : distinguer les deux cas révélerait l'existence de foyers, de personnes ou de voyages à un tiers.

Cette règle vaut entre foyers, et seulement là. À l'intérieur d'un foyer dont on est membre, la situation est inverse : la ressource est la sienne, on la lit tous les jours, on n'a simplement pas le droit d'y toucher. Un `404` mentirait à un client légitime et rendrait l'interface inécrivable — impossible d'y distinguer « ce foyer n'existe pas » de « tu n'es pas propriétaire ». C'est donc `403`, et le `detail` dit lequel des deux refus s'applique : pas propriétaire, ou pas encore quelqu'un.

Les deux codes se lisent alors sans ambiguïté : `404` pour ce qui n'est pas à vous, `403` pour ce qui est à vous et que votre rôle n'autorise pas.

Le porteur de cette règle est `HouseholdScopedView`, dont dérivent les vues du domaine : elle résout le foyer du chemin **parmi ceux dont l'appelant est membre**, et répond `404` sinon. Le cloisonnement tient au type de la vue et non à la vigilance de chaque route — une route qui oublierait d'en hériter se remarquerait, alors qu'un filtre oublié dans un `get_queryset` ne se remarque pas.

Les routes du domaine sont donc portées par le chemin du foyer — `/api/households/{household_id}/persons`, `/api/households/{household_id}/trips` — et le cloisonnement est appliqué une fois pour toutes par la couche qui résout le foyer courant, jamais réécrit dans chaque route.

Les foyers eux-mêmes échappent à cette imbrication : `/api/households/` est la racine du domaine, et sa collection est cloisonnée par l'appartenance de l'appelant plutôt que par un foyer de chemin.

## État du service

`GET /api/health/` répond `200` sans authentification. C'est la sonde de santé, et c'est aussi le seul appel qu'un client fait au chargement pour savoir quel code lui répond.

```json
{"status": "ok", "version": "v1.2.0", "commit": "abc1234"}
```

`version` est le ref git de l'image — le tag sur une release, la branche sinon — et `commit` son SHA court. Les deux valent `null` pour un appelant qui n'est pas administrateur, y compris anonyme, la réponse gardant la même forme dans tous les cas : un client n'a qu'un chemin à écrire, et un champ nul se distingue d'un champ absent.

**Ce n'est pas un `403`, et c'est la seule exception à la règle des rôles.** Ailleurs, un droit refusé sur sa propre ressource répond `403`. Ici la ressource — l'état du service — reste lisible par tous, seuls deux champs de diagnostic sont tus : répondre `403` fermerait la sonde de santé, qui doit rester interrogeable sans session. Un refus ne porte que sur ce qu'il refuse.

**Le garde est `is_staff`, pas un rôle de foyer.** C'est l'accès à l'admin Django, un axe d'autorisation distinct de `owner`/`member`, et c'est le seul endroit de l'API où il décide de quelque chose. Le dépôt étant public, un commit publié dirait à n'importe qui de quels correctifs le déploiement est en retard ; réservé aux administrateurs, il n'apprend rien à personne qui ne puisse déjà tout lire.

Les deux valeurs sont posées au build de l'image et ne peuvent pas être devinées depuis l'intérieur : `.git` est exclu du contexte de build. Le [README](../../README.md) décrit les variables qui les portent.

## Les refus du domaine

Un refus décidé par le domaine — supprimer le dernier statut « pas préparé », rétrograder le dernier propriétaire — est levé comme une exception DRF, `tout_pris.exceptions.Conflict`, et c'est DRF qui la rend en `409` avec son `detail`. Aucune route n'a à l'attraper, et le message écrit dans le code métier est celui que le client lit.

L'exception vit au niveau du projet et non dans les vues d'une app, parce que la règle vaut **partout** : le catalogue refuse dans `catalog/statuses.py`, le foyer refuse dans `households/views.py`, et les deux doivent répondre pareil. Une exception rangée dans les vues d'une app obligerait la suivante à l'importer de là, ou à inventer la sienne.

Ce n'est pas un détail de rangement. Le gestionnaire d'exceptions par défaut de DRF ne convertit que trois choses : ses propres `APIException`, `Http404` et la `PermissionDenied` de Django. **Une `ValidationError` de `django.core.exceptions` levée dans le code métier n'est donc pas convertie** : elle remonte, Django répond `500`, et le message du refus n'arrive jamais au client — un refus prévu se lit alors comme une panne. C'est la raison d'être de cette règle, et elle s'applique à tout code de domaine à venir, pas seulement à celui qui l'a fait apparaître.

## Foyers

`GET /api/households/` liste les foyers dont l'appelant est membre : son foyer personnel et ceux qu'on lui a partagés. C'est l'écran de sélection décrit dans [`docs/model/household.md`](../model/household.md). Chaque entrée porte `personal`, un booléen, plutôt qu'un nom à afficher pour le foyer personnel : ce nom existe en base pour l'admin, et l'interface écrit « Personnel ».

`POST /api/households/` crée un foyer partagé et répond `201`. Le créateur y est inscrit comme membre `owner` et la `Person` qui le représente est créée dans la même transaction, exactement comme l'inscription le fait pour le foyer personnel : sans elle, il serait membre d'un foyer où il n'existe pour personne. Le corps ne porte que le nom — un foyer personnel ne se crée qu'à l'inscription, et aucun client ne désigne son `personal_of`.

C'est cette route qui débloque le partage : inviter exige un foyer partagé, et rien d'autre n'en produit.

`PATCH` et `DELETE /api/households/{household_id}/` renomment et suppriment un foyer partagé, et supprimer emporte ses membres, ses personnes et ses invitations. Le foyer personnel répond `404` sur les deux : son nom n'est jamais affiché, donc jamais renommé, et il ne disparaît qu'avec le compte dont il est l'espace privé.

## Personnes

CRUD complet sous le foyer : `GET` et `POST /api/households/{household_id}/persons/`, puis `GET`, `PATCH` et `DELETE /api/households/{household_id}/persons/{id}/`. Tous les foyers en ont, le foyer personnel compris.

Le corps ne porte que le nom. Le compte lié est en lecture seule dans le schéma : il est rempli par l'inscription ou par l'acceptation d'une invitation, jamais par un client qui désignerait un compte à rattacher.

Supprimer une personne dont le compte est encore membre du foyer répond `409` : ça retirerait sa représentation à quelqu'un qui a toujours accès, et chaque écran « pour qui » se retrouverait sans lui. Retirer le membre d'abord délie la personne et rend sa suppression possible.

`POST /api/households/{household_id}/persons/{id}/claim/` répond `204` et rattache la personne au compte appelant. C'est l'écran « qui êtes-vous ? » à l'arrivée dans un foyer : l'invité choisit la personne qui l'attendait — « Papa » créé par le foyer avant qu'il ne rejoigne — au lieu qu'une deuxième soit créée à côté d'elle. Rien dans le corps, l'identité vient du chemin et de la session.

Deux refus, tous deux en `409` : une personne qui a déjà un compte, et un appelant qui est déjà quelqu'un dans ce foyer. Le premier protège la représentation d'un autre membre, le second l'invariant « un compte, une personne par foyer » que la base porte déjà — répondre `409` plutôt que laisser passer une violation de contrainte donne à l'appelant une réponse qu'il peut lire.

Un membre peut donc exister sans personne, le temps de choisir : c'est l'état dans lequel l'acceptation d'une invitation le laisse quand elle n'en désigne aucune, et l'écran de choix est ce qui en sort.

Un arrivant que personne n'attendait se crée donc sa personne puis la revendique, en deux appels. Rattacher au passage à la création aurait fait un second chemin d'écriture vers `Person.user` pour épargner une requête, alors que la revendication est déjà la seule porte et qu'elle porte les deux refus.

## Rôles

`HouseholdMember.role` porte enfin quelque chose. Il n'a rien porté jusqu'ici parce que le report était sans conséquence : tant que rejoindre un foyer était impossible, tous ses membres étaient la même personne.

**`member`** — le quotidien : lire le foyer, créer, renommer et supprimer les personnes non rattachées, et tout ce qui viendra ensuite, catalogue, voyages, listes.

**`owner`** — en plus : inviter une adresse et annuler une invitation, retirer un autre membre, distribuer les rôles, renommer le foyer et le supprimer.

**Un membre sans personne** — le demi-niveau ouvert par l'écran « qui êtes-vous ? ». Il lit ce qu'il faut pour choisir, crée sa personne et la revendique, rien d'autre : aucune action de ce produit n'a de sens sans savoir *pour qui* on la fait.

Les lectures restent ouvertes à tous les membres — c'est l'écriture que le rôle gouverne. La règle est portée par deux permissions DRF posées sur le type de la vue, comme `HouseholdScopedView` porte le cloisonnement : `IsSomeoneInTheHousehold` sur toutes les vues du foyer, `IsHouseholdOwner` en plus sur celles que le propriétaire seul commande. Une route qui oublierait d'en hériter se remarquerait ; un contrôle oublié dans un `perform_destroy` ne se remarque pas.

Deux exceptions, et elles sont le demi-niveau lui-même : créer une personne et la revendiquer restent ouverts à un membre qui n'est encore personne, sans quoi il n'aurait aucun moyen de le devenir.

Quitter le foyer n'est pas un droit de propriétaire : retirer *quelqu'un d'autre* l'est, retirer sa propre appartenance reste ouvert à tout membre — c'est la même écriture, et personne n'est retenu dans un foyer.

Le dernier propriétaire ne peut ni se rétrograder ni partir, `409` dans les deux cas, pour la même raison que le dernier membre en #54 : un foyer partagé que plus personne ne peut administrer serait un foyer que plus personne ne peut ni partager ni supprimer. C'est ce qui rend `PATCH /api/households/{household_id}/members/{id}/` nécessaire plutôt que confortable : sans passation de rôle, ce refus enfermerait le créateur dans son propre foyer.

Le foyer personnel n'est pas concerné : son titulaire est seul, et sa collection de membres répond déjà `404`.

## Membres

`GET /api/households/{household_id}/members/` liste qui a accès au foyer, avec l'adresse et le rôle de chaque compte. `DELETE /api/households/{household_id}/members/{id}/` retire un membre ; se retirer soi-même, c'est quitter le foyer, il n'y a pas de route « quitter » distincte pour la même écriture.

`PATCH /api/households/{household_id}/members/{id}/` change le rôle d'un membre, propriétaire seul : c'est la passation de propriété, et la seule façon d'en obtenir une seconde. Elle refuse en `409` de promouvoir quelqu'un qui n'est encore personne dans le foyer — on ne confie pas un foyer à un compte qui n'y existe pour personne — et de rétrograder le dernier propriétaire.

Retirer un membre **conserve sa `Person` et vide son compte**, comme le fait déjà la suppression d'un compte. `Person.user` pointe vers un compte et non vers une appartenance : le laisser rempli rattacherait un non-membre à une personne du foyer. Les affaires de « Papa » restent dans les listes, seul le lien vers le compte disparaît.

Le dernier membre ne peut pas quitter un foyer partagé : la route répond `409`. Le laisser partir abandonnerait en base un foyer que plus personne ne peut ni lire ni supprimer, avec ses personnes et ses futures listes ; supprimer le foyer d'un `DELETE` explicite dit ce que ça détruit, et évite de le détruire par accident en quittant.

Comme pour les invitations, un foyer personnel répond `404` sur ces deux routes, y compris à son propriétaire : la collection n'existe pas, il n'a pas d'autre membre possible que lui.

## Invitations

Un membre invite une adresse dans un foyer partagé, l'invité suit le lien reçu et rejoint. Les routes sont `POST` et `GET /api/households/{household_id}/invitations/`, `DELETE /api/households/{household_id}/invitations/{id}/`, et `POST /api/invitations/accept/`.

Inviter répond `204` sans corps, **y compris quand rien n'est créé**. Une adresse déjà titulaire d'un compte, une adresse inconnue et une adresse déjà membre du foyer donnent la même réponse au bit près : distinguer les cas ferait de la route un oracle d'énumération d'adresses.

Un foyer personnel répond `404` sur ces trois routes, y compris à son propriétaire : la collection n'existe pas, il n'a pas d'autre membre possible que lui.

L'acceptation fait exception au chemin porté par le foyer, l'appelant n'étant justement pas encore membre. C'est le jeton qui porte l'autorisation, et il voyage dans le corps plutôt que dans l'URL — un secret dans un chemin se retrouve dans les journaux du serveur, l'historique du navigateur et l'en-tête `Referer`. allauth fait le même choix pour ses clés de vérification d'email et de réinitialisation.

Le raisonnement complet et les décisions du flux sont dans [`docs/model/invitation.md`](../model/invitation.md).

## Chemins

Les chemins portent une barre oblique finale, convention de Django et des routeurs DRF : `/api/health/`, `/api/households/{household_id}/persons/`.

## Corps et schémas

Toutes les entrées et sorties sont en JSON.

Un serializer par opération : `XCreate`, `XUpdate`, `XRead`. Jamais un schéma fourre-tout partagé entre l'entrée et la sortie — c'est ce qui laisse fuiter un jour un champ interne dans une réponse, ou accepter un identifiant fourni par le client.

Rien du corps ne porte d'identité : les identifiants de ressource viennent du chemin. Un `household_id` glissé dans le corps est ignoré.

## Écriture partielle

`PATCH`, pas `PUT`. Le client édite un champ à la fois ; un `PUT` l'obligerait à réémettre une représentation complète, donc à écraser des champs qu'il ne connaît pas. Un champ absent et un `null` explicite laissent tous deux la valeur inchangée, et un corps vide est une requête valide sans effet.

La règle est portée par `PartialWriteSerializer`, dont dérivent les serializers `XUpdate` : il retire du corps les champs à `null` avant la validation, plutôt que de laisser chaque route s'en souvenir.

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

Le chemin d'inscription par fournisseur externe est en place — le front poste sur `auth/provider/redirect`, l'utilisateur revient sur le callback du fournisseur, et allauth ouvre la session — mais **aucun fournisseur n'est configuré** : il n'y a ni identifiants dans l'environnement ni `SocialApp` en base. Brancher Google se réduira à fournir ses identifiants. Le chemin reste couvert par des tests qui simulent le fournisseur, parce qu'il est le seul à prouver que l'inscription par fournisseur crée le foyer comme celle par email.

Une connexion par fournisseur ne se rattachera pas d'elle-même à un compte local existant qui porterait la même adresse : `SOCIALACCOUNT_EMAIL_AUTHENTICATION` reste désactivé, sans quoi un fournisseur qui affirme une adresse suffirait à prendre le compte.

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
