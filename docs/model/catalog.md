# Référentiel d'objets, statuts de préparation et kits

## Le besoin

Préparer un voyage, c'est cocher des affaires : « bavoir », « t-shirt », « sandales ». Ces noms reviennent d'un voyage à l'autre, et les ressaisir à chaque fois serait le premier abandon de l'application.

Chaque foyer constitue donc son propre référentiel d'objets. Il démarre avec un catalogue de base copié à la création du foyer, puis s'enrichit au fil de la saisie : quand l'utilisateur ajoute un objet à un voyage et qu'aucun objet existant ne correspond, il en crée un nouveau à la volée.

Le référentiel appartient au foyer et n'est jamais partagé entre foyers. Un catalogue global éditable obligerait à copier la ligne dès qu'un foyer veut la renommer, avec la question de savoir qui en est alors propriétaire ; une copie du catalogue de base à la création donne le même confort de démarrage sans cette ambiguïté. Le prix est connu et assumé, il est écrit dans [`household.md`](household.md) : deux foyers, ce sont deux catalogues à entretenir.

## Les doublons sont assumés, le nettoyage doit être facile

La saisie libre produira « chapeau », « Chapeau » et « chapeaux ». Ce n'est pas grave, et surtout ce n'est pas évitable : refuser un nom proche à la saisie ferait perdre plus de temps qu'il n'en ferait gagner. L'utilisateur verra le problème de lui-même, parce que ses regroupements cesseront de fonctionner — quatre t-shirts affichés en deux lignes de deux.

Ce qui compte est donc le nettoyage, et il tient en un geste : **renommer un objet vers un nom déjà pris déclenche une fusion**. Les lignes de kit de l'objet absorbé sont réaffectées au survivant, puis l'objet absorbé est supprimé. Il n'y a pas d'écran « fusionner deux objets » à trouver, seulement le renommage que l'utilisateur allait faire de toute façon.

C'est la contrepartie de la contrainte d'unicité, qui porte sur le **nom normalisé** — minuscules, espaces de bord retirés — et non sur le nom brut. Sans normalisation, « chapeau » et « Chapeau » cohabiteraient et la fusion n'aurait plus de déclencheur : le renommage réussirait sans rien nettoyer. En Django, cela s'exprime par une `UniqueConstraint` sur des expressions (`Lower`, `Trim`), qui fonctionne sur SQLite comme sur PostgreSQL.

La recherche du survivant utilise les mêmes expressions SQL que la contrainte, plutôt qu'un `lower()` Python. Les deux ne s'accordent pas sur les accents — `LOWER` de SQLite ne touche pas les caractères non ASCII, `str.lower` si — et un désaccord donnerait le pire des deux : la fusion croirait avoir trouvé un survivant que la base considère comme un nom libre, ou l'inverse.

`rename_item_type` est donc la seule bonne façon de renommer un objet. Écrire `item_type.name = ...` puis `save()` lève une `IntegrityError` quand le nom est pris, au lieu de fusionner.

## Les statuts de préparation

Le suivi par défaut est « pas préparé » → « sorti du placard » → « dans les sacs », mais chaque foyer doit pouvoir créer les siens : « commandé en ligne », « à acheter sur place ». Ce n'est donc pas une énumération figée dans le code mais une table, avec un ordre d'affichage et une couleur propres au foyer.

Un statut porte en plus une **catégorie de progression** — `not_started`, `in_progress`, `done` — qui alimente la barre d'avancement du voyage. Sans elle, il faudrait deviner quel statut compte comme terminé, et « le dernier dans l'ordre d'affichage » casse dès qu'un foyer ajoute un statut personnalisé en fin de liste.

Effet de bord utile : un foyer qui crée « pas besoin cette fois » le classera en `done`, et la ligne cesse de bloquer la progression sans qu'on ait eu à modéliser le cas.

### Le statut par défaut est déduit, pas marqué

Le statut d'une ligne nouvellement créée est **le premier `not_started` dans l'ordre d'affichage**. Aucune colonne ne le désigne.

Un drapeau `is_default` obligerait à garantir « exactement un par foyer » à chaque création, chaque suppression, chaque réordonnancement et chaque import — le même reproche que celui adressé à un booléen `is_personal` sur le foyer, sauf qu'ici aucune contrainte d'unicité ne peut le porter, puisque la règle est « exactement un », pas « au plus un ». La déduction n'a rien à maintenir.

### Supprimer un statut

Les lignes portant le statut supprimé sont réaffectées au statut par défaut. Le défaut lui-même est supprimable tant qu'il reste un autre `not_started` : le suivant devient alors le défaut et sert de cible.

Seule la suppression du **dernier `not_started`** est refusée : sans lui, plus de cible de réaffectation ni de statut à donner à une nouvelle ligne. Dans le cas normal — un seul `not_started` — le défaut est donc indéboulonnable, sans drapeau à maintenir pour autant.

Le refus est un `Conflict`, l'exception de refus du domaine que DRF rend en `409` sur n'importe quelle route ; le raisonnement est dans [`docs/api/`](../api/README.md). Il vit dans `delete_status`, pas dans `ItemStatus.delete()`. L'admin peut donc encore supprimer le dernier `not_started`, et c'est cohérent avec ce qu'est l'admin ici : la porte de service qu'on ouvre en connaissance de cause pour réparer un état que l'application ne sait pas produire.

La réaffectation des lignes, elle, n'est pas encore écrite : rien ne référence `ItemStatus` tant que `TripItem` n'existe pas. Elle arrive avec lui. Le raffinement à prévoir alors est de réaffecter d'abord vers un statut de même catégorie de progression quand il en existe un, pour qu'un « commandé en ligne » supprimé ne fasse pas régresser les objets jusqu'à « pas préparé ».

## Les kits

Un kit est un bloc réutilisable et nommé : « sac à langer », « affaires enfants », « affaires de rando ». C'est la brique qui rend l'initialisation d'un voyage rapide — on coche trois kits et l'essentiel de la liste est là.

Il joue aussi le rôle de section d'affichage dans le voyage, et ces deux rôles sont volontairement portés par la même notion.

C'est ce qui écarte le tag. Un tag posé sur l'objet qualifie l'objet partout à la fois : « bavoir » taggé « sac à langer » taggerait aussi bien les deux bavoirs du sac à langer que les six bavoirs du séjour. Le kit, lui, est le **bloc d'origine de la ligne** : la même chose peut entrer deux fois dans un voyage, par deux blocs différents, et rester distinguable. C'est précisément ce que l'utilisateur veut voir, et c'est ce qu'un tag ne sait pas dire.

Une ligne de kit peut désigner une personne : « affaires enfants » contient « 5 t-shirts pour Enfant 1 » et « 5 t-shirts pour Enfant 2 ». À l'instanciation dans un voyage, les lignes visant une personne qui n'y participe pas sont ignorées.

Supprimer une personne emporte donc ses lignes de kit. Les rendre génériques en remettant la personne à vide serait pire : « 5 t-shirts pour Enfant 1 » deviendrait « 5 t-shirts » pour tout le monde, et le kit se mettrait à demander des affaires que personne n'a demandées.

**Pas de contrainte d'unicité sur `KitItem`.** La personne étant facultative, une unicité SQL serait faussée — `NULL` n'entre pas en conflit avec lui-même — et il existe des doublons légitimes. Le garde-fou est applicatif, au moment où l'on promeut un objet dans un kit.

**Pas de table de liaison entre le voyage et le kit** non plus : `TripItem.kit` suffira à regrouper les lignes d'un voyage par section, et une table de plus n'apporterait que la possibilité de cocher un kit sans en garder aucune ligne.

## L'ordre

Trois tables portent une `position` : les statuts et les kits dans leur foyer, les lignes dans leur kit. L'ordre des lignes est significatif, c'est l'ordre de préparation, et il se propage aux lignes du voyage.

`django-ordered-model` le tient, comme `acts_as_list` en Rails. `order_with_respect_to` limite la numérotation au foyer ou au kit, si bien que deux foyers ont chacun leurs positions à partir de zéro.

Le comportement à connaître avant d'écrire les routes de réordonnancement :

- la position est attribuée à la création, à la fin de son groupe, et le champ n'est pas modifiable dans un formulaire (`editable=False`) ;
- une suppression referme le trou : les positions suivantes descendent d'un cran, y compris quand la ligne part en cascade avec son foyer ou son kit, parce que l'app `ordered_model` branche un récepteur `post_delete` sur chaque modèle ordonné — d'où sa présence dans `INSTALLED_APPS`, qui ne sert pas qu'à l'admin ;
- `up()`, `down()`, `to()` et `swap()` déplacent une ligne, chacun en plusieurs écritures ; une route de réordonnancement les appelle dans une transaction ;
- `model_bakery` remplit `position` d'une valeur au hasard au lieu de laisser `save()` l'attribuer, malgré `editable=False` : les objets ordonnés se créent avec `objects.create`, comme le fait `seed`, sinon l'ordre est celui du tirage ;
- changer le foyer d'un statut ou le kit d'une ligne le renumérote dans son nouveau groupe et referme le trou laissé dans l'ancien, ce qui est le bon comportement mais reste une écriture large derrière un `save()` d'apparence anodine.

## Le catalogue de base

Un foyer vide n'est pas utilisable : il faudrait saisir « brosse à dents » avant de pouvoir la cocher. `install_base_catalog` copie donc dans un nouveau foyer une trentaine d'objets courants et les trois statuts par défaut — « pas préparé » (`not_started`), « sorti du placard » (`in_progress`), « dans les sacs » (`done`).

C'est une copie, pas une référence : le foyer peut renommer, supprimer et réordonner tout ce qu'il reçoit, et rien ne remonte à la source. La commande `seed` s'en sert pour que la base de développement ressemble à un foyer réel ; son déclenchement à l'inscription relève de #41.

Les noms sont en français, comme tout ce que l'utilisateur lit. Le code, lui, reste en anglais.

## Ce que le schéma ne porte pas

**Une ligne de kit référence un objet et une personne du même foyer que son kit.** Trois clés étrangères mènent au foyer par trois chemins différents, et aucune contrainte ne les oblige à converger. C'est à l'application de valider chaque clé étrangère reçue contre le foyer courant, comme le rappellent les conventions d'API dans [`docs/api/`](../api/README.md).

`check_integrity` les liste, comme il liste les invariants du foyer : une ligne dont l'objet **ou** la personne vient d'ailleurs est un état interdit, et le seul moyen de s'en apercevoir sans le chercher.

**Un foyer a au moins un statut `not_started`.** `install_base_catalog` en pose un et `delete_status` refuse de retirer le dernier, mais un foyer créé sans passer par le premier, ou une suppression par l'admin, laissent un foyer sans statut par défaut. `default_status` renvoie alors `None` plutôt que de lever : c'est un état anormal mais lisible, et l'appelant est mieux placé pour décider quoi en dire.

`check_integrity` le liste lui aussi, mais restreint à ce qui est vraiment interdit **aujourd'hui** : un foyer qui a des statuts et aucun `not_started`. Un foyer qui n'en a aucun n'est pas signalé, parce que c'est encore le cas normal — l'inscription crée un foyer sans catalogue, et c'est #41 qui y branchera `install_base_catalog`. Signaler ces foyers-là ferait crier la commande sur chaque inscription, et une alerte qui crie toujours finit éteinte. Le jour où #41 est livrée, la restriction tombe et « aucun statut » devient à son tour un état interdit.
