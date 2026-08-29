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

Une session non authentifiée reçoit bien `401` et non le `403` que DRF renvoie par défaut : DRF ne choisit `401` que si une classe d'authentification annonce un en-tête `WWW-Authenticate`, et `SessionAuthentication` n'en annonce aucun. `tout_pris.authentication.SessionAuthentication` en annonce un, pour que « connecte-toi » se lise sur un seul code quel que soit l'endpoint — allauth répond déjà `401`. Le schéma annoncé est `Session` et non `Basic`, il ne déclenche donc aucune fenêtre d'authentification du navigateur, et une extension de drf-spectacular garde la description `cookieAuth` dans la spécification.

Le `403` ne dit jamais qu'une ressource existe ailleurs. Une ressource qui existe mais que l'appelant n'a pas le droit de **voir** répond `404`, exactement comme si elle n'existait pas : distinguer les deux cas révélerait l'existence de foyers, de personnes ou de voyages à un tiers.

Cette règle vaut entre foyers, et seulement là. À l'intérieur d'un foyer dont on est membre, la situation est inverse : la ressource est la sienne, on la lit tous les jours, on n'a simplement pas le droit d'y toucher. Un `404` mentirait à un client légitime et rendrait l'interface inécrivable — impossible d'y distinguer « ce foyer n'existe pas » de « tu n'es pas propriétaire ». C'est donc `403`, et le `detail` dit lequel des deux refus s'applique : pas propriétaire, ou pas encore quelqu'un.

Le porteur de cette règle est `HouseholdScopedView`, dont dérivent les vues du domaine : elle résout le foyer du chemin **parmi ceux dont l'appelant est membre**, et répond `404` sinon. Le cloisonnement tient au type de la vue et non à la vigilance de chaque route — une route qui oublierait d'en hériter se remarquerait, alors qu'un filtre oublié dans un `get_queryset` ne se remarque pas.

Les routes du domaine sont donc portées par le chemin du foyer — `/api/households/{household_id}/persons`, `/api/households/{household_id}/trips` — et le cloisonnement est appliqué une fois pour toutes par la couche qui résout le foyer courant, jamais réécrit dans chaque route.

Les foyers eux-mêmes échappent à cette imbrication : `/api/households/` est la racine du domaine, et sa collection est cloisonnée par l'appartenance de l'appelant plutôt que par un foyer de chemin.

## État du service

`GET /api/health/` répond `200` sans authentification. C'est la sonde de santé, et c'est aussi le seul appel qu'un client fait au chargement pour savoir quel code lui répond.

```json
{"status": "ok", "version": "v1.2.0", "commit": "abc1234"}
```

**`version` est public, `commit` ne l'est pas.** Le ref git de l'image — le tag sur une release, la branche sinon — est renvoyé à tout le monde, y compris à un appelant anonyme. Le SHA court n'est renvoyé qu'à un administrateur, et vaut `null` pour les autres ; la réponse garde la même forme dans tous les cas, un client n'a qu'un chemin à écrire et un champ nul se distingue d'un champ absent.

Le partage tombe là parce que les deux valeurs ne disent pas la même chose. Un tag existe déjà publiquement dans le dépôt, et sur l'image `dev` le ref vaut `main` : le publier n'apprend rien à personne. Le SHA court, lui, désigne le build exact, et le dépôt étant public il dit de quels correctifs le déploiement est en retard. C'est lui, et lui seul, qu'il y a lieu de protéger.

Un utilisateur qui signale un bug peut donc joindre la version sans que l'endpoint devienne un inventaire de ce qui manque au déploiement.

**Ce n'est pas un `403`, et c'est la seule exception à la règle des rôles.** Ailleurs, un droit refusé sur sa propre ressource répond `403`. Ici la ressource — l'état du service — reste lisible par tous, et un seul champ de diagnostic est tu : répondre `403` fermerait la sonde de santé, qui doit rester interrogeable sans session. Un refus ne porte que sur ce qu'il refuse.

**Le garde est `is_staff`, pas un rôle de foyer.** C'est l'accès à l'admin Django, un axe d'autorisation distinct de `owner`/`member`, et c'est le seul endroit de l'API où il décide de quelque chose.

Un angle mort à connaître : sur l'image `dev`, `version` vaut `main` pour tout le monde, ce qui ne distingue pas deux builds de pré-production l'un de l'autre. Un rapport venu de la pré-prod dira donc « main » et rien de plus, et c'est le `commit` — réservé — qui reste le seul moyen d'y voir clair.

Les deux valeurs sont posées au build de l'image et ne peuvent pas être devinées depuis l'intérieur : `.git` est exclu du contexte de build. Le [README](../../README.md) décrit les variables qui les portent.

## Les refus du domaine

Un refus décidé par le domaine — supprimer le statut par défaut d'un foyer, rétrograder le dernier propriétaire — est levé comme une exception DRF, `tout_pris.exceptions.Conflict`, et c'est DRF qui la rend en `409` avec son `detail`. Aucune route n'a à l'attraper, et le message écrit dans le code métier est celui que le client lit.

L'exception vit au niveau du projet et non dans les vues d'une app, parce que la règle vaut **partout** : le catalogue refuse dans `catalog/statuses.py`, le foyer refuse dans `households/views.py`, et les deux doivent répondre pareil. Une exception rangée dans les vues d'une app obligerait la suivante à l'importer de là, ou à inventer la sienne.

Le gestionnaire d'exceptions par défaut de DRF ne convertit que trois choses : ses propres `APIException`, `Http404` et la `PermissionDenied` de Django. **Une `ValidationError` de `django.core.exceptions` levée dans le code métier n'est donc pas convertie** : elle remonte, Django répond `500`, et le message du refus n'arrive jamais au client — un refus prévu se lit alors comme une panne. C'est la raison d'être de cette règle, et elle s'applique à tout code de domaine.

## Foyers

`GET /api/households/` liste les foyers dont l'appelant est membre : son foyer personnel et ceux qu'on lui a partagés. C'est l'écran de sélection décrit dans [`docs/model/household.md`](../model/household.md). Chaque entrée porte `personal`, un booléen, plutôt qu'un nom à afficher pour le foyer personnel : ce nom existe en base pour l'admin, et l'interface écrit « Personnel ».

`POST /api/households/` crée un foyer partagé et répond `201`. Le créateur y est inscrit comme membre `owner` et la `Person` qui le représente est créée dans la même transaction, exactement comme l'inscription le fait pour le foyer personnel : sans elle, il serait membre d'un foyer où il n'existe pour personne. Le corps ne porte que le nom — un foyer personnel ne se crée qu'à l'inscription, et aucun client ne désigne son `personal_of`.

C'est cette route qui débloque le partage : inviter exige un foyer partagé, et rien d'autre n'en produit.

`PATCH` et `DELETE /api/households/{household_id}/` renomment et suppriment un foyer partagé, et supprimer emporte ses membres, ses personnes et ses invitations. Le foyer personnel répond `404` sur les deux : son nom n'est jamais affiché, donc jamais renommé, et il ne disparaît qu'avec le compte dont il est l'espace privé.

## Personnes

CRUD complet sous le foyer : `GET` et `POST /api/households/{household_id}/persons/`, puis `GET`, `PATCH` et `DELETE /api/households/{household_id}/persons/{id}/`. Tous les foyers en ont, le foyer personnel compris.

Le corps ne porte que le nom. Le compte lié est en lecture seule dans le schéma : il est rempli par l'inscription ou par la revendication, jamais par un client qui désignerait un compte à rattacher.

Supprimer une personne dont le compte est encore membre du foyer répond `409` : ça retirerait sa représentation à quelqu'un qui a toujours accès, et chaque écran « pour qui » se retrouverait sans lui. Retirer le membre d'abord délie la personne et rend sa suppression possible.

`POST /api/households/{household_id}/persons/{id}/claim/` répond `204` et rattache la personne au compte appelant. C'est l'écran « qui êtes-vous ? » à l'arrivée dans un foyer, et c'est **le seul** chemin : l'invité choisit la personne qui l'attendait — « Papa » créé par le foyer avant qu'il ne rejoigne — au lieu qu'une deuxième soit créée à côté d'elle. Rien dans le corps, l'identité vient du chemin et de la session.

Deux refus, tous deux en `409` : une personne qui a déjà un compte, et un appelant qui est déjà quelqu'un dans ce foyer. Le premier protège la représentation d'un autre membre, le second l'invariant « un compte, une personne par foyer » que la base porte déjà — répondre `409` plutôt que laisser passer une violation de contrainte donne à l'appelant une réponse qu'il peut lire.

Un membre peut donc exister sans personne, le temps de choisir : c'est l'état dans lequel l'acceptation d'une invitation le laisse **toujours**, et l'écran de choix est ce qui en sort.

Un arrivant que personne n'attendait se crée donc sa personne puis la revendique, en deux appels.

## Rôles

**`member`** — le quotidien : lire le foyer, créer, renommer et supprimer les personnes non rattachées, et tout ce qui viendra ensuite, catalogue, voyages, listes.

**`owner`** — en plus : inviter une adresse et annuler une invitation, retirer un autre membre, distribuer les rôles, renommer le foyer et le supprimer.

**Un membre sans personne** — le demi-niveau ouvert par l'écran « qui êtes-vous ? ». Il lit ce qu'il faut pour choisir, crée sa personne et la revendique, rien d'autre : aucune action de ce produit n'a de sens sans savoir *pour qui* on la fait.

Les lectures restent ouvertes à tous les membres — c'est l'écriture que le rôle gouverne. La règle est portée par deux permissions DRF posées sur le type de la vue, comme `HouseholdScopedView` porte le cloisonnement : `IsSomeoneInTheHousehold` sur toutes les vues du foyer, `IsHouseholdOwner` en plus sur celles que le propriétaire seul commande. Une route qui oublierait d'en hériter se remarquerait ; un contrôle oublié dans un `perform_destroy` ne se remarque pas.

Deux exceptions, et elles sont le demi-niveau lui-même : créer une personne et la revendiquer restent ouverts à un membre qui n'est encore personne, sans quoi il n'aurait aucun moyen de le devenir.

Quitter le foyer n'est pas un droit de propriétaire : retirer *quelqu'un d'autre* l'est, retirer sa propre appartenance reste ouvert à tout membre — c'est la même écriture, et personne n'est retenu dans un foyer.

Le dernier propriétaire ne peut ni se rétrograder ni partir, `409` dans les deux cas, pour la même raison que le dernier membre d'un foyer : un foyer partagé que plus personne ne peut administrer serait un foyer que plus personne ne peut ni partager ni supprimer. C'est ce qui rend `PATCH /api/households/{household_id}/members/{id}/` nécessaire plutôt que confortable : sans passation de rôle, ce refus enfermerait le créateur dans son propre foyer.

Le foyer personnel n'est pas concerné : son titulaire est seul, et sa collection de membres répond déjà `404`.

## Membres

`GET /api/households/{household_id}/members/` liste qui a accès au foyer, avec l'adresse et le rôle de chaque compte. `DELETE /api/households/{household_id}/members/{id}/` retire un membre ; se retirer soi-même, c'est quitter le foyer, il n'y a pas de route « quitter » distincte pour la même écriture.

`PATCH /api/households/{household_id}/members/{id}/` change le rôle d'un membre, propriétaire seul : c'est la passation de propriété, et la seule façon d'en obtenir une seconde. Elle refuse en `409` de promouvoir quelqu'un qui n'est encore personne dans le foyer — on ne confie pas un foyer à un compte qui n'y existe pour personne — et de rétrograder le dernier propriétaire.

Retirer un membre **conserve sa `Person` et vide son compte**, comme le fait déjà la suppression d'un compte. `Person.user` pointe vers un compte et non vers une appartenance : le laisser rempli rattacherait un non-membre à une personne du foyer. Les affaires de « Papa » restent dans les listes, seul le lien vers le compte disparaît.

Le dernier membre ne peut pas quitter un foyer partagé : la route répond `409`. Le laisser partir abandonnerait en base un foyer que plus personne ne peut ni lire ni supprimer, avec ses personnes et ses futures listes ; supprimer le foyer d'un `DELETE` explicite dit ce que ça détruit, et évite de le détruire par accident en quittant.

Comme pour les invitations, un foyer personnel répond `404` sur ces deux routes, y compris à son propriétaire : la collection n'existe pas, il n'a pas d'autre membre possible que lui.

## Invitations

Un membre invite une adresse dans un foyer partagé, l'invité suit le lien reçu et rejoint. Les routes sont `POST` et `GET /api/households/{household_id}/invitations/`, `DELETE /api/households/{household_id}/invitations/{id}/`, et `POST /api/invitations/accept/`.

Le corps de la création ne porte que l'adresse : qui l'invité sera dans le foyer se décide après, et par lui. Le raisonnement est dans [`docs/model/invitation.md`](../model/invitation.md).

Inviter répond `204` sans corps, **y compris quand rien n'est créé**. Une adresse déjà titulaire d'un compte, une adresse inconnue et une adresse déjà membre du foyer donnent la même réponse au bit près : distinguer les cas ferait de la route un oracle d'énumération d'adresses.

Un foyer personnel répond `404` sur ces trois routes, y compris à son propriétaire : la collection n'existe pas, il n'a pas d'autre membre possible que lui.

L'acceptation fait exception au chemin porté par le foyer, l'appelant n'étant justement pas encore membre. C'est le jeton qui porte l'autorisation, et il voyage dans le corps plutôt que dans l'URL — un secret dans un chemin se retrouve dans les journaux du serveur, l'historique du navigateur et l'en-tête `Referer`. allauth fait le même choix pour ses clés de vérification d'email et de réinitialisation.

Le raisonnement complet et les décisions du flux sont dans [`docs/model/invitation.md`](../model/invitation.md).

## Objets et statuts

Le référentiel du foyer est exposé sous son chemin, comme les personnes : `GET` et `POST /api/households/{household_id}/item-types/`, puis `GET`, `PATCH` et `DELETE /api/households/{household_id}/item-types/{id}/`, et les mêmes quatre routes sur `item-statuses/`. Les objets sont listés par nom, les statuts dans leur ordre d'affichage. C'est le quotidien du foyer et non son administration : un `member` en fait autant qu'un `owner`, et seule `IsSomeoneInTheHousehold` s'applique. Le besoin derrière le référentiel est dans [`docs/model/catalog.md`](../model/catalog.md).

**Renommer un objet vers un nom déjà pris fusionne, et la réponse porte alors un `id` différent de celui de l'URL.** Le `PATCH` appelle `rename_item_type` : les lignes de l'objet absorbé passent au survivant, l'absorbé est supprimé, et c'est le survivant qui est renvoyé en `200`, **tel quel**. Les autres champs du corps sont ignorés quand la fusion a lieu, pour la même raison que la création tolérante renvoie l'existant sans le toucher : un formulaire d'édition renvoie l'objet entier, et sa description écraserait celle que le foyer avait écrite sur l'objet survivant, qu'il ne visait pas. Ce n'est pas un `409` : la fusion est le nettoyage que l'utilisateur cherchait, pas un accident. **Un client qui garde l'ancien `id` en mémoire pointe alors sur une ligne supprimée** — il doit relire l'`id` de la réponse après chaque renommage, exactement comme il en relit le nom.

**Créer un objet dont le nom est déjà pris renvoie l'existant en `200`**, sans rien créer ni rien modifier. Deux créations simultanées du même nom donnent la même réponse : la seconde voit la contrainte d'unicité lui refuser l'insertion, relit l'objet que la première vient de créer et le renvoie, plutôt que de laisser fuiter une `IntegrityError` en `500`. La saisie d'un voyage crée un objet à la volée quand aucun ne correspond, et c'est ce `POST` qu'elle appelle : répondre `409` obligerait chaque client à chercher d'abord, donc à réimplémenter une comparaison de noms qui porte sur le nom normalisé et ne se devine pas. `201` reste la réponse d'une vraie création, et c'est le code de statut qui distingue les deux cas. L'existant est renvoyé tel quel : ce `POST` demande « donne-moi l'objet appelé X », il n'écrase pas la description que le foyer avait donnée à celui qui existait déjà.

La comparaison emploie les mêmes expressions SQL que la contrainte d'unicité, `Lower` et `Trim`, et non un `lower()` Python : les deux ne s'accordent pas sur les accents, et le désaccord ferait renvoyer un objet existant là où la base voit un nom libre, ou l'inverse.

**Supprimer le statut par défaut répond `409`** avec le message de `delete_status` : sans lui, une nouvelle ligne n'aurait plus aucun statut à recevoir. Tous les autres se suppriment, et le refus est explicable au client qui le reçoit — désigner un autre défaut débloque la suppression.

**Le statut par défaut se désigne par `is_default: true` sur le `PATCH`**, et le drapeau est retiré au précédent dans la même transaction. Sans cette route, le premier statut d'un foyer serait indéboulonnable : c'est lui que l'API marque comme défaut à la création, un foyer démarrant à zéro statut tant que l'inscription n'installe pas le catalogue de base.

**`is_default: false` est refusé comme un corps invalide**, au même titre qu'une couleur qui n'est pas hexadécimale, et non comme un conflit : un foyer sans statut par défaut est précisément l'état interdit, et aucun état du foyer ne rendrait la demande acceptable — il n'y a rien à changer ailleurs pour qu'elle passe, seulement un autre statut à désigner. Un champ absent laisse le drapeau tel quel ; `null` est refusé, la colonne n'étant pas nullable.

**La catégorie de progression se change librement**, celle du statut par défaut comprise : elle alimente la barre d'avancement du voyage, elle ne décide plus quel statut une nouvelle ligne reçoit. Un statut se renomme, se repeint et se reclasse sans condition ; seul son drapeau de défaut protège quelque chose.

**La couleur d'un statut est facultative à la création** et vaut `#7b8189`, un gris neutre, quand le client n'en donne pas. Imposer un hexadécimal pour créer « à acheter sur place » alourdirait la saisie fluide que la création tolérante cherche justement à obtenir, et une couleur est ce qu'on ajuste ensuite, jamais ce qui manque pour reconnaître un statut. Le modèle, lui, garde le champ obligatoire : le défaut est une commodité d'API, l'admin et le catalogue de base continuent de choisir explicitement.

## Kits

Un kit est le bloc réutilisable décrit dans [`docs/model/catalog.md`](../model/catalog.md), et ses lignes sont exposées **sous lui** : `GET` et `POST /api/households/{household_id}/kits/`, `GET`, `PATCH` et `DELETE /api/households/{household_id}/kits/{id}/`, puis les mêmes quatre routes sur `kits/{kit_id}/items/`. Comme le reste du référentiel, c'est le quotidien du foyer : seule `IsSomeoneInTheHousehold` s'applique, un `member` en fait autant qu'un `owner`.

**Les lignes sont imbriquées plutôt qu'à plat.** Une ligne n'a aucune existence hors de son bloc et sa `position` ne veut rien dire ailleurs ; une collection `/api/households/{household_id}/kit-items/` obligerait à porter le kit dans chaque corps, et le cloisonnement du kit — la vérification que ce kit-là est bien du foyer — serait à réécrire dans chaque route au lieu d'être porté par le chemin.

Le chemin étant l'appartenance, **une ligne ne change pas de kit** : le corps ne porte pas de `kit`, et déplacer une ligne d'un bloc à l'autre se fait en la supprimant et en la recréant. Accepter un `kit` en écriture ferait du `PATCH` un déménagement silencieux qui renumérote deux blocs d'un coup, pour un geste que personne n'a demandé. Supprimer un kit emporte ses lignes, c'est la cascade du modèle : le bloc est ce qui leur donne un sens.

**La collection des kits ne porte pas les lignes, le kit à l'unité les porte.** Un foyer accumule ses kits et chacun porte des dizaines de lignes : les embarquer dans la collection ferait payer le contenu de tous les blocs à chaque écran qui n'affiche que des noms. L'écran de sélection montre de quoi choisir — un nom, une description — et charge le kit retenu quand il s'ouvre : un appel de plus sur un geste, contre une réponse plus lourde à chaque affichage. C'est la même règle que la collection des voyages.

**Le kit à l'unité renvoie ses lignes, l'objet et la personne développés.** Un client qui recevrait des identifiants nus devrait recharger le catalogue et les personnes pour afficher « 5 t-shirts pour Louis », dans chaque écran qui montre un kit, et deux clients le feraient différemment. L'objet et la personne développés portent exactement la représentation que servent `item-types/` et `persons/` — une forme par ressource, pas une par contexte.

**Chaque clé étrangère reçue est validée contre le foyer du chemin.** `KitItem` mène au foyer par trois chemins — son kit, son `item_type`, sa `person` — et aucune contrainte de base ne les oblige à converger : c'est un invariant que le schéma ne porte pas, et l'API en est le seul garant. Un `item_type` ou une `person` d'un autre foyer répond donc `404`, comme s'il n'existait pas, sans jamais dire qu'il existe ailleurs.

C'est `404` et non `400` parce qu'un identifiant désigne une ressource, et que la réponse à « tu désignes une ressource que tu n'as pas le droit de voir » est la même partout dans cette API, qu'elle vienne du chemin ou du corps. Un `400` en ferait un problème de forme du corps, alors que le corps est parfaitement formé — et il rangerait dans la même case l'objet d'un autre foyer et un identifiant qui n'est pas un nombre, qui reste, lui, un `400`. La règle est portée par le type du champ, `HouseholdScopedRelation`, et non par une vérification réécrite dans chaque route.

**Deux lignes du même objet dans le même kit sont légitimes**, et rien ne les refuse : « 2 chapeaux, le bob » et « 3 chapeaux pour Jeanne » sont deux demandes différentes, et c'est ce que la fusion des objets produit délibérément. Le raisonnement est dans [`docs/model/catalog.md`](../model/catalog.md).

La personne est facultative — une ligne sans personne est pour tout le foyer — et `person: null` la vide, ce qui rend commune une ligne qui visait quelqu'un.

**`quantity` va de 1 à 32767.** Une ligne à zéro n'existe pas : un client qui décrémente jusqu'à zéro envoie un `DELETE`, et demander confirmation avant est son affaire. Les bornes sont posées sur la colonne et non sur le serializer, elles valent donc aussi pour l'admin et pour tout code qui écrira une ligne ; la haute est celle du `smallint`, que PostgreSQL rendrait en `500` sans elle.

## L'ordre

Un statut, un kit et une ligne de kit portent une `position` dans leur groupe — le foyer pour les deux premiers, le kit pour la troisième. Elle est attribuée à la fin du groupe à la création, et **l'envoyer dans le `PATCH` de la ressource la déplace à ce rang**, les autres se décalant pour lui faire la place. C'est le glisser-déposer du front, transcrit tel quel : il relâche une entrée à un rang, il envoie ce rang.

**Il n'y a pas de route de réordonnancement séparée.** Déplacer une entrée est une modification comme une autre, et une route dédiée ferait un second chemin d'écriture sur la même ressource, avec son cloisonnement et sa résolution de foyer à réécrire.

**La position va de 0 au dernier rang du groupe**, et hors de ces bornes c'est un `400` : le corps est invalide, et aucun état du foyer ne rendrait la demande acceptable. Les bornes se comptent dans le groupe de l'entrée déplacée et nulle part ailleurs : un kit de trois lignes refuse la position 3, même si le kit d'à côté en a dix.

**Deux membres qui déplacent une entrée du même groupe en même temps obtiennent un ordre qu'aucun des deux n'a demandé** : chacun désigne un rang dans la liste qu'il avait sous les yeux, et rien ne dit au second que la première a bougé. Le déplacement par index achète à ce prix un corps de requête qui ne porte que le rang, là où un `PUT` de la liste entière obligerait le client à renvoyer tous les identifiants pour bouger une ligne.

## Voyages

Un voyage est la liste que le foyer prépare, décrite dans [`docs/model/trips.md`](../model/trips.md). Ses participants et ses lignes sont exposés **sous lui**, comme les lignes d'un kit sous leur kit : `GET` et `POST /api/households/{household_id}/trips/`, `GET`, `PATCH` et `DELETE /api/households/{household_id}/trips/{id}/`, puis `GET` et `POST` sur `trips/{trip_id}/participants/` et `DELETE` sur `trips/{trip_id}/participants/{id}/`, et les quatre routes habituelles sur `trips/{trip_id}/items/`. Préparer un voyage est le quotidien du foyer et non son administration : seule `IsSomeoneInTheHousehold` s'applique, un `member` en fait autant qu'un `owner`.

Un participant ne se modifie pas — participer est un fait binaire — d'où l'absence de `PATCH` sur lui. Ajouter deux fois la même personne répond `409` : le client a la liste des participants sous les yeux, et un second `POST` est une erreur, pas un geste à absorber en silence.

**La collection des voyages ne porte ni les participants ni les lignes, le voyage à l'unité les porte**, comme la collection des kits ne porte pas les leurs. Un foyer accumule ses voyages sans jamais en supprimer, et chacun porte des dizaines de lignes : les embarquer dans la collection ferait de l'écran d'accueil la plus grosse réponse du produit, pour des lignes que personne n'y lit.

Le voyage à l'unité, lui, renvoie ses lignes ordonnées, l'objet, la personne et le statut développés. Un client qui recevrait des identifiants nus rechargerait le catalogue, les statuts et les personnes pour afficher « 5 t-shirts pour Léo », dans chaque écran qui montre un voyage.

**Une ligne porte le tag que le front affiche à côté d'elle : les kits du foyer qui contiennent son objet.** Il est calculé en lecture, jamais stocké — le raisonnement est dans [`docs/model/trips.md`](../model/trips.md) — et il est donc en lecture seule : ajouter un objet à un kit se fait sur le kit, par `POST /api/households/{household_id}/kits/{kit_id}/items/`, et le tag apparaît aussitôt sur toutes les lignes qui packent cet objet.

Le tag porte le kit sous la forme que sert sa collection : son `id`, son nom, sa description et sa position, sans ses lignes. C'est la représentation habituelle de la ressource, une forme par ressource et pas une par contexte, et elle tient sur une étiquette parce que ce qu'un kit a de volumineux — ses lignes — n'y est pas.

La lecture d'une ligne coûte donc le même nombre de requêtes quel qu'en soit le nombre : les vues préchargent `item_type__kit_items__kit`. `TripItem` est la table la plus lue de l'application, et un tag calculé ligne par ligne y produirait le N+1 le plus coûteux du produit.

**`POST /api/households/{household_id}/trips/{trip_id}/kits/` instancie un kit dans le voyage et renvoie les lignes créées**, `201` quand il en a créé, `200` quand il n'en a créé aucune. Le tableau vide est le seul signal dont le front dispose pour dire « ce kit n'a rien ajouté » au moment du clic : aucune table ne garde trace d'un kit choisi, et recharger le voyage ne le distinguerait pas d'un kit qui n'aurait ajouté que des lignes déjà présentes. Les règles de la copie — ligne ignorée si elle vise un non-participant, ligne considérée présente au même objet et à la même personne, quantité et note jamais réécrites — sont dans [`docs/model/trips.md`](../model/trips.md), et elles vivent dans `trips/preparation.py` plutôt que dans la vue, comme `catalog/statuses.py` porte les règles de statut : la vue reçoit, valide, délègue.

**Le statut est facultatif à la création d'une ligne** et vaut celui que le foyer a marqué par défaut. C'est celui que reçoit déjà une ligne instanciée depuis un kit, et l'imposer au client obligerait chaque écran d'ajout libre à relire les statuts pour retrouver une règle que le serveur applique de toute façon. Un foyer qui n'a aucun statut ne peut rien préparer : la ligne n'a pas de statut à recevoir, et les deux routes répondent `409` plutôt que d'en créer une sans.

**Un objet n'entre dans un voyage qu'une seule fois pour une même personne**, et la seconde ligne répond `409`, à la création comme au `PATCH` qui l'y ramènerait. C'est la règle décrite dans [`docs/model/trips.md`](../model/trips.md), portée par deux contraintes d'unicité : le `409` est ce qui les rend lisibles au client, une violation laissée passer répondant `500`. L'instanciation d'un kit, elle, ne la rencontre jamais — elle ignore ce qui est déjà là.

**Chaque clé étrangère reçue est validée contre le foyer du chemin.** Quatre chemins mènent d'une ligne au foyer — son voyage, son objet, sa personne, son statut — et aucune contrainte de base ne les oblige à converger ; un participant appartient de même au foyer de son voyage. Un identifiant venu d'ailleurs répond `404`, comme s'il n'existait pas, par le même `HouseholdScopedRelation` que les lignes de kit.

**`quantity` va de 1 à 32767**, sur une ligne de voyage comme sur une ligne de kit et pour les mêmes raisons.

Retirer un participant ne touche pas les lignes préparées pour lui : elles restent, et c'est à l'interface de les montrer. `position` est en lecture seule, attribuée à la fin du voyage à la création et reprise de l'ordre du kit à l'instanciation.

## Chemins

Les chemins portent une barre oblique finale, convention de Django et des routeurs DRF : `/api/health/`, `/api/households/{household_id}/persons/`.

## Corps et schémas

Toutes les entrées et sorties sont en JSON.

Un serializer par opération : `XCreate`, `XUpdate`, `XRead`. Jamais un schéma fourre-tout partagé entre l'entrée et la sortie — c'est ce qui laisse fuiter un jour un champ interne dans une réponse, ou accepter un identifiant fourni par le client.

Rien du corps ne porte d'identité : les identifiants de ressource viennent du chemin. Un `household_id` glissé dans le corps est ignoré.

## Écriture partielle

`PATCH`, pas `PUT`. Le client édite un champ à la fois ; un `PUT` l'obligerait à réémettre une représentation complète, donc à écraser des champs qu'il ne connaît pas.

**Un champ absent laisse la valeur inchangée, un champ à `null` la vide.** Un corps vide est donc une requête valide sans effet, et `null` sur une colonne qui ne l'accepte pas répond `400` plutôt que de laisser croire que la demande a été appliquée. C'est la sémantique du JSON Merge Patch ([RFC 7386](https://www.rfc-editor.org/rfc/rfc7386)), et DRF la porte seul : `partial=True` sur le serializer, `allow_null` sur les champs nullables.

**Vider n'est pas un geste unique, c'est la colonne qui décide.** `person` sur une ligne de kit est nullable et se vide avec `null` ; `note` et `description` sont des chaînes facultatives et se vident avec `""`, un `null` y répondant `400`. `openapi.yaml` le dit champ par champ avec `nullable`.

## Collections

Les collections sont renvoyées comme des tableaux JSON nus, sans enveloppe ni pagination. C'est volontairement provisoire : aucune collection actuelle ne peut croître sans borne — les personnes d'un foyer, ses voyages. La pagination sera ajoutée quand une collection le justifiera, vraisemblablement les objets d'une liste, et pas avant, pour ne pas imposer dès maintenant une enveloppe à tous les appelants.

Une collection vide renvoie `[]` et non `404` : la collection existe, elle est vide.

## Langue

La langue d'une réponse est celle que le compte a choisie, et `Accept-Language` ne fait foi que là où personne n'est connecté — écrans de connexion, d'inscription, de demande de réinitialisation et d'acceptation d'invitation. C'est l'exigence qui commande : un choix qui vivrait dans le navigateur — cookie `django_language`, `localStorage` — serait perdu au premier changement de navigateur ou de machine, alors que le choix doit suivre la personne. Il est donc porté par le compte, et l'en-tête ne sert qu'à l'amorcer à l'inscription.

Ce n'est pas en tension avec les standards : `Accept-Language` annonce une préférence par défaut du client, qu'un choix explicite a vocation à supplanter.

Les langues servies sont celles de `LANGUAGES`, dans les codes que Django écrit — `en-us`, `fr` —, et une langue demandée hors de cette liste retombe sur `en-us`. Les catalogues de Django, de DRF et d'allauth fournissent l'essentiel des messages ; ceux que l'API écrit elle-même, à commencer par les refus du domaine, ont le leur dans `locale/`.

`tout_pris.middleware.LocaleMiddleware` porte la règle. Il dérive de celui de Django, à qui il laisse la négociation par en-tête, et il est déclaré **après `AuthenticationMiddleware`** et non à la place que documente Django : il lit `request.user`, qui n'existe pas avant. La position documentée sert à donner une langue active à `CommonMiddleware`, ce dont seul `i18n_patterns` a besoin — l'API ne préfixe aucune URL par la langue.

**Toute réponse annonce `Vary: Accept-Language, Cookie`.** Les deux entrées décident réellement de la langue : le cookie de session quand il y en a un, l'en-tête sinon. N'annoncer que la branche qui s'est appliquée laisserait un cache resservir à un utilisateur connecté la réponse stockée pour un visiteur anonyme au même `Accept-Language`. `Content-Language` dit la langue effectivement servie.

## Authentification

Assurée par django-allauth en mode headless (`HEADLESS_ONLY`), monté sur `/api/auth/`, sans qu'aucun template ne soit rendu : les vues d'allauth qui rendaient des pages ne sont même pas déclarées dans l'URLconf, seuls subsistent les endpoints JSON et les callbacks des fournisseurs sur `/accounts/`.

Un seul client allauth est activé, le client `browser` : la session est portée par le cookie `sessionid`, `httpOnly` et marqué `Secure` en production. Le front étant servi sur le même domaine, ce cookie bat le jeton sur la révocation immédiate et sur l'exposition aux XSS, et évite une danse de refresh côté client. Le client `app` d'allauth, qui authentifie par jeton `X-Session-Token`, reste désactivé : l'activer ouvrirait un second chemin d'authentification à côté de la session. `SessionAuthentication` de DRF lit cette même session, sans classe d'authentification supplémentaire.

Les endpoints suivent la spécification d'allauth, préfixés par `/api/auth/browser/v1/` : `auth/signup`, `auth/login`, `auth/session` (`GET` pour lire la session, `DELETE` pour se déconnecter), `auth/email/verify`, `auth/password/request`, `auth/password/reset`, `auth/provider/redirect`, `account/password/change`, `account/email`, `config`. Ils sont tous décrits dans `openapi.yaml`.

Ces endpoints ne sont pas des vues DRF : `DEFAULT_PERMISSION_CLASSES` ne s'y applique pas, et l'inscription comme la connexion répondent donc à un appelant anonyme sans réglage particulier. C'est vérifié par les tests plutôt que supposé, un endpoint d'inscription fermé par héritage se remarquant très tard.

Le code de statut suit lui aussi la convention d'allauth et non le tableau ci-dessus : `401` signifie « la session n'est pas authentifiée », y compris quand l'appel a réussi. Une inscription en attente de vérification d'email et une réinitialisation de mot de passe réussie répondent `401` avec l'état du flux dans le corps. Le `403` que Django renvoie sur un jeton CSRF manquant échappe de même à la règle « jamais de 403 » : il est émis par le middleware, avant toute logique de domaine.

L'identifiant de connexion est l'email (`ACCOUNT_LOGIN_METHODS = {"email"}`), unique côté application (`ACCOUNT_UNIQUE_EMAIL`) comme en base depuis la contrainte portée par le modèle `User`. `USERNAME_FIELD` reste `username` : allauth le remplit à partir de l'email, il n'est jamais demandé ni exposé.

La vérification d'email est obligatoire : tant qu'elle n'est pas faite, la session reste non authentifiée. Confirmer depuis le navigateur qui a lancé l'inscription ouvre la session directement (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION`) ; allauth n'ouvre cette session que si l'inscription en cours est présente dans la session, un lien intercepté ailleurs ne connecte donc personne.

Les liens envoyés par email pointent vers le front, pas vers l'API : `HEADLESS_FRONTEND_URLS` compose les URL de vérification et de réinitialisation à partir de `FRONTEND_URL`, et le front repasse la clé à l'endpoint correspondant.

Le chemin d'inscription par fournisseur externe est en place — le front poste sur `auth/provider/redirect`, l'utilisateur revient sur le callback du fournisseur, et allauth ouvre la session — mais **aucun fournisseur n'est configuré** : il n'y a ni identifiants dans l'environnement ni `SocialApp` en base. Brancher Google se réduira à fournir ses identifiants. Le chemin reste couvert par des tests qui simulent le fournisseur, parce qu'il est le seul à prouver que l'inscription par fournisseur crée le foyer comme celle par email.

Une connexion par fournisseur ne se rattachera pas d'elle-même à un compte local existant qui porterait la même adresse : `SOCIALACCOUNT_EMAIL_AUTHENTICATION` reste désactivé, sans quoi un fournisseur qui affirme une adresse suffirait à prendre le compte.

Les limitations de débit d'allauth (`ACCOUNT_RATE_LIMITS`) sont laissées à leurs valeurs par défaut et s'appuient sur le cache Django. Le cache par défaut étant local au processus, les compteurs sont par worker : un cache partagé sera nécessaire le jour où l'API tournera sur plusieurs processus.

### Les endpoints d'authentification dans la spécification

drf-spectacular ne décrit que les vues DRF ; les vues d'allauth lui sont invisibles. **Il y a donc deux spécifications, et c'est assumé.**

`openapi.yaml`, committé à la racine et vérifié en CI, décrit l'API du domaine. allauth publie la sienne sur `/api/auth/openapi.yaml` et `/api/auth/openapi.json`, servies par l'application sans qu'on ait rien à câbler, dérivées de son code et élaguées selon la configuration réellement chargée : les endpoints non montés en sont retirés.

Les fusionner demanderait de sous-classer le générateur de drf-spectacular, soit de la glu maison à maintenir au rythme des deux bibliothèques, pour un bénéfice de confort. Un client qui a besoin des deux les lit à deux adresses.

## Pourquoi Django et DRF

L'API est prioritaire ici pour servir plusieurs clients sans dupliquer la logique, ce qui suppose une spécification OpenAPI dérivée du code. drf-spectacular la génère depuis les vues et les serializers, et la CI vérifie qu'elle ne dérive pas.

DRF est la couche API de référence de l'écosystème Django : c'est elle que les briques tierces intègrent d'origine, django-allauth en tête, et elle apporte montées les permissions, la limitation de débit et la négociation de contenu que la façade aurait dû assembler autrement.

Pydantic ne quitte pas le projet pour autant, et `drf-pydantic` est câblé : un modèle Pydantic expose son serializer DRF dérivé par `Model.drf_serializer`, ce qui permet à un même modèle d'être à la fois la cible d'un appel PydanticAI et le schéma d'une réponse. `/api/health/` en est l'exemple vivant plutôt qu'une promesse — la spécification générée est identique à celle qu'un serializer écrit à la main produisait.

Deux façons de déclarer un schéma coexistent donc, et le choix n'est pas laissé au goût : `ModelSerializer` pour ce qui est adossé à l'ORM, puisqu'il dérive les champs du modèle Django, et Pydantic pour ce qui n'a pas de table derrière lui — la sortie d'un modèle de langage, une réponse calculée. C'est la vraie contrepartie de DRF : l'uniformité de déclaration, pas Pydantic lui-même.

La spécification est émise en OpenAPI 3.0.3, défaut de drf-spectacular ; `OAS_VERSION` force 3.1.0 si un générateur de client le réclame.
