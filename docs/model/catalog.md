# Référentiel d'objets, statuts de préparation et kits

## Le besoin

Préparer un voyage, c'est cocher des affaires : « bavoir », « t-shirt », « sandales ». Ces noms reviennent d'un voyage à l'autre, et les ressaisir à chaque fois serait le premier abandon de l'application.

Chaque foyer constitue donc son propre référentiel d'objets. Il démarre avec un catalogue de base copié à la création du foyer, puis s'enrichit au fil de la saisie : quand l'utilisateur ajoute un objet à un voyage et qu'aucun objet existant ne correspond, il en crée un nouveau à la volée.

Le référentiel appartient au foyer et n'est jamais partagé entre foyers. Un catalogue global éditable obligerait à copier la ligne dès qu'un foyer veut la renommer, avec la question de savoir qui en est alors propriétaire ; une copie du catalogue de base à la création donne le même confort de démarrage sans cette ambiguïté. Le prix est connu et assumé, il est écrit dans [`household.md`](household.md) : deux foyers, ce sont deux catalogues à entretenir.

## Les doublons sont assumés, le nettoyage doit être facile

La saisie libre produira « chapeau », « Chapeau » et « chapeaux ». Ce n'est pas grave, et surtout ce n'est pas évitable : refuser un nom proche à la saisie ferait perdre plus de temps qu'il n'en ferait gagner. L'utilisateur verra le problème de lui-même, parce que ses regroupements cesseront de fonctionner — quatre t-shirts affichés en deux lignes de deux.

Ce qui compte est donc le nettoyage, et il tient en un geste : **renommer un objet vers un nom déjà pris déclenche une fusion**. Les lignes de kit de l'objet absorbé sont réaffectées au survivant ; ses lignes de voyage le sont aussi, **sauf celles qui feraient doublon avec une ligne déjà présente**, qui sont supprimées. L'objet absorbé disparaît ensuite. Il n'y a pas d'écran « fusionner deux objets » à trouver, seulement le renommage que l'utilisateur allait faire de toute façon.

**Unifier le type est la réparation ; le regroupement en découle.** Un kit qui contenait « 2 Chapeau » et « 3 chapeaux » contient ensuite deux lignes du même objet, et ce n'est pas un résidu : avant, les deux lignes ne partageaient rien et rien ne pouvait les rapprocher — c'est exactement le symptôme décrit plus haut. Après, elles partagent un `item_type_id`, et toute vue qui lit des lignes peut les présenter ensemble. Le regroupement se fait donc là où les lignes sont lues, dans le kit et dans le voyage, pas au renommage.

Additionner les quantités en base serait résoudre au mauvais endroit. « 2 Chapeau » pour Jeanne et « 3 chapeaux » pour Louis deviendraient « 5 » pour personne, et deux affaires que rien n'a jamais confondues n'en feraient plus qu'une. La `person` distincte n'est pas une limite de la fusion, elle est ce qu'il faut garder : un regroupement à l'affichage rend les deux lignes correctement, une somme les efface.

**Les deux tables ne se comportent pas pareil, et c'est voulu.** `KitItem` garde le droit au doublon : aucune contrainte ne l'interdit, la fusion y réaffecte tout, et deux lignes du même objet dans un kit sont l'état de sortie décrit juste au-dessus. `TripItem` ne l'a pas : deux contraintes d'unicité y interdisent qu'un objet entre deux fois dans le même voyage pour la même personne, et le raisonnement est dans [`trips.md`](trips.md). La fusion ne peut donc pas y produire le même résultat, et elle supprime la ligne en trop au lieu de la créer.

Ce qui se perd alors est **la quantité de la ligne supprimée**. Un voyage qui contenait « 2 Chapeau » et « 3 chapeaux » garde « 2 Chapeau » : la survivante est celle qui portait déjà le nom retenu, et l'utilisateur ajuste s'il le veut. C'est le comportement demandé, préféré ici encore à une addition qui inventerait un nombre que personne n'a saisi. La divergence joue aussi en retour : un kit contenant deux fois le même objet n'instancie qu'une seule ligne de voyage, la seconde étant vue comme déjà présente. L'objet absorbé emporte enfin **sa description**, le seul texte libre du domaine puisque les lignes n'en portent pas : c'est celle du survivant que toutes les lignes réaffectées affichent ensuite.

C'est la contrepartie de la contrainte d'unicité, qui porte sur le **nom normalisé** — minuscules, espaces de bord retirés — et non sur le nom brut. Sans normalisation, « chapeau » et « Chapeau » cohabiteraient et la fusion n'aurait plus de déclencheur : le renommage réussirait sans rien nettoyer. En Django, cela s'exprime par une `UniqueConstraint` sur des expressions (`Lower`, `Trim`), qui fonctionne sur SQLite comme sur PostgreSQL.

La recherche du survivant utilise les mêmes expressions SQL que la contrainte, plutôt qu'un `lower()` Python. Les deux ne s'accordent pas sur les accents — `LOWER` de SQLite ne touche pas les caractères non ASCII, `str.lower` si — et un désaccord donnerait le pire des deux : la fusion croirait avoir trouvé un survivant que la base considère comme un nom libre, ou l'inverse.

`rename_item_type` est donc la seule bonne façon de renommer un objet. Écrire `item_type.name = ...` puis `save()` lève une `IntegrityError` quand le nom est pris, au lieu de fusionner.

## Les statuts de préparation

Le suivi par défaut est « pas préparé » → « sorti du placard » → « dans les sacs », mais chaque foyer doit pouvoir créer les siens : « commandé en ligne », « à acheter sur place ». Ce n'est donc pas une énumération figée dans le code mais une table, avec un ordre d'affichage et une couleur propres au foyer.

Un statut porte en plus une **catégorie de progression** — `not_started`, `in_progress`, `done` — qui alimente la barre d'avancement du voyage. Sans elle, il faudrait deviner quel statut compte comme terminé, et « le dernier dans l'ordre d'affichage » casse dès qu'un foyer ajoute un statut personnalisé en fin de liste.

Effet de bord utile : un foyer qui crée « pas besoin cette fois » le classera en `done`, et la ligne cesse de bloquer la progression sans qu'on ait eu à modéliser le cas.

### Le statut par défaut est marqué, pas déduit

Le statut d'une ligne nouvellement créée est celui que porte le drapeau `is_default`, et il y en a un par foyer.

Une version précédente le déduisait — le premier `not_started` dans l'ordre d'affichage — pour n'avoir rien à maintenir, et reprochait au drapeau qu'aucune contrainte d'unicité ne puisse porter « exactement un ». L'objection tombe parce que la règle se coupe en deux moitiés qui ont chacune leur garant : une `UniqueConstraint` partielle par foyer, conditionnée à `is_default=True`, porte « au plus un » en base ; « au moins un » vient de ce que le premier statut d'un foyer devient son défaut d'office et que le défaut est indéboulonnable, sa suppression étant refusée tant qu'un autre statut n'a pas repris le rôle.

Surtout, la déduction protégeait la mauvaise chose : elle imposait au foyer de garder un statut `not_started`, alors que le besoin est qu'il reste **un statut, peu importe sa catégorie**, et que les catégories se changent librement. Elle rendait aussi le refus inexplicable — « le dernier `not_started` » ne veut rien dire pour qui utilise l'application, « désigne d'abord un autre statut par défaut » se comprend.

La promotion d'office vit dans `ItemStatus.save()` et non dans la vue. L'inscription ne pose pas encore de catalogue de base — c'est #41 — donc un foyer réel démarre à zéro statut et son premier statut arrive par l'API : un `is_default` laissé à `False` rouvrirait exactement le trou que le drapeau vient boucher, un foyer qui a des statuts et aucun défaut. Dans le modèle, la promotion vaut aussi pour l'admin, le `seed` et le catalogue de base.

### Supprimer un statut

Les lignes portant le statut supprimé sont réaffectées à un autre statut. Tout statut se supprime, **sauf le défaut** : sans lui, plus de cible de réaffectation ni de statut à donner à une nouvelle ligne, et le foyer se retrouverait sans aucun statut le jour où c'est le dernier.

Le défaut se libère en en désignant un autre — `is_default: true` sur un `PATCH`, qui retire le drapeau au précédent dans la même transaction — après quoi l'ancien se supprime comme n'importe quel autre. Sans cette désignation, le premier statut créé serait indéboulonnable sans recours.

La **catégorie de progression** se change librement, y compris celle du défaut : elle alimente la barre d'avancement, elle ne décide plus de rien. Un foyer qui ne veut qu'un statut « à faire » classé `done` est libre de l'avoir.

Le refus est un `Conflict`, l'exception de refus du domaine que DRF rend en `409` sur n'importe quelle route ; le raisonnement est dans [`docs/api/`](../api/README.md). Il vit dans `delete_status`, pas dans `ItemStatus.delete()`. L'admin peut donc encore supprimer le statut par défaut, et c'est cohérent avec ce qu'est l'admin ici : la porte de service qu'on ouvre en connaissance de cause pour réparer un état que l'application ne sait pas produire.

La réaffectation des lignes de voyage vit dans `delete_status` : les lignes rejoignent d'abord un statut de même catégorie de progression quand il en existe un, sinon le statut par défaut, pour qu'un « commandé en ligne » supprimé ne fasse pas régresser jusqu'à « pas préparé » des objets que quelqu'un avait avancés. La clé étrangère est en `RESTRICT`, si bien qu'un statut encore porté par des lignes ne se supprime que par ce chemin — le raisonnement complet est dans [`trips.md`](trips.md).

## Les kits

Un kit est un bloc réutilisable et nommé : « sac à langer », « affaires enfants », « affaires de rando ». C'est la brique qui rend l'initialisation d'un voyage rapide — on coche trois kits et l'essentiel de la liste est là.

Il sert aussi de **tag** : une ligne de voyage affiche les kits auxquels son objet appartient, ce qui donne de quoi s'y retrouver dans une longue liste sans qu'aucune section n'existe. Ces deux rôles sont volontairement portés par la même notion.

**Le tag est lu dans le catalogue, jamais stocké sur la ligne de voyage.** C'est la décision retenue, et elle renverse celle qui figurait ici. L'argument d'alors : un tag posé sur l'objet qualifie l'objet partout à la fois — « bavoir » taggé « sac à langer » taggerait aussi bien les deux bavoirs du sac à langer que les six bavoirs du séjour — alors qu'une colonne portée par la ligne de voyage en aurait fait le **bloc d'origine**, si bien que la même chose pouvait entrer deux fois dans un voyage, par deux blocs différents, et rester distinguable.

Ce que cet argument supposait est justement ce que le besoin a écarté : **un objet n'entre dans un voyage qu'une seule fois**, quel que soit le nombre de kits qui le contiennent. Il n'y a donc pas deux lignes à distinguer, et la seule question qui reste est ce que l'on affiche à côté d'une ligne — la liste des kits de son objet, que le catalogue donne à la lecture, sans rien copier. La colonne d'origine n'aurait plus servi qu'à répondre à une question que personne ne pose.

Ce que l'on perd est réel : plus rien ne dit par quel bloc une ligne est arrivée, si « crème solaire » vient de « sac à langer » ou de « plage ». C'est assumé, au même titre que le passé qui change quand on supprime un objet du référentiel — la même décision confirme ce `CASCADE`. La contrepartie joue d'ailleurs dans l'autre sens : ranger un objet dans un kit le tagge aussitôt partout, y compris sur les voyages déjà faits, là où une colonne d'origine aurait laissé ces lignes muettes pour toujours.

Une ligne de kit peut désigner une personne : « affaires enfants » contient « 5 t-shirts pour Enfant 1 » et « 5 t-shirts pour Enfant 2 ». À l'instanciation dans un voyage, les lignes visant une personne qui n'y participe pas sont ignorées.

Supprimer une personne emporte donc ses lignes de kit. Les rendre génériques en remettant la personne à vide serait pire : « 5 t-shirts pour Enfant 1 » deviendrait « 5 t-shirts » pour tout le monde, et le kit se mettrait à demander des affaires que personne n'a demandées.

**Pas de contrainte d'unicité sur `KitItem`.** La personne étant facultative, une unicité SQL serait faussée — `NULL` n'entre pas en conflit avec lui-même — et il existe des doublons légitimes. Le garde-fou est applicatif, au moment où l'on promeut un objet dans un kit.

**Une ligne de kit packe au moins un exemplaire.** Une ligne à zéro n'existe pas, on la supprime, et c'est une `CheckConstraint` sur `quantity` qui le tient : les validateurs de la colonne ne s'exécutent qu'à travers `full_clean()`, donc sur l'API et sur l'admin, jamais sur un `objects.create`.

**Pas de table de liaison entre le voyage et le kit** non plus, et le renversement du tag ne la ramène pas : le regroupement à l'affichage n'a besoin de rien, le tag se lisant des `KitItem` de l'objet. Ce qu'elle apporterait est la mémoire d'un kit coché — savoir qu'il a été appliqué même quand il n'en reste aucune ligne — et ça ne vaut pas une table : le recochage est idempotent et sans mémoire, ce que [`trips.md`](trips.md) assume ligne à ligne.

## L'ordre

Trois tables portent une `position` : les statuts et les kits dans leur foyer, les lignes dans leur kit. L'ordre des lignes est significatif, c'est l'ordre de préparation, et il se propage aux lignes du voyage.

`django-ordered-model` le tient, comme `acts_as_list` en Rails. `order_with_respect_to` limite la numérotation au foyer ou au kit, si bien que deux foyers ont chacun leurs positions à partir de zéro.

Le comportement à connaître de la bibliothèque :

- la position est attribuée à la création, à la fin de son groupe, et le champ n'est pas modifiable dans un formulaire (`editable=False`) ;
- une suppression referme le trou : les positions suivantes descendent d'un cran, y compris quand la ligne part en cascade avec son foyer ou son kit, parce que l'app `ordered_model` branche un récepteur `post_delete` sur chaque modèle ordonné — d'où sa présence dans `INSTALLED_APPS`, qui ne sert pas qu'à l'admin ;
- `up()`, `down()`, `to()` et `swap()` déplacent une ligne, chacun en plusieurs écritures ; le `PATCH` qui réordonne les appelle dans une transaction ;
- `model_bakery` remplit `position` d'une valeur au hasard au lieu de laisser `save()` l'attribuer, malgré `editable=False` : les objets ordonnés se créent avec `objects.create`, comme le fait `seed`, sinon l'ordre est celui du tirage ;
- changer le foyer d'un statut ou le kit d'une ligne le renumérote dans son nouveau groupe et referme le trou laissé dans l'ancien, ce qui est le bon comportement mais reste une écriture large derrière un `save()` d'apparence anodine.

## Le catalogue de base

Un foyer vide n'est pas utilisable : il faudrait saisir « brosse à dents » avant de pouvoir la cocher. `install_base_catalog` copie donc dans un nouveau foyer une trentaine d'objets courants et trois statuts — « pas préparé » (`not_started`), « sorti du placard » (`in_progress`), « dans les sacs » (`done`).

**L'ordre de `BASE_ITEM_STATUSES` désigne le statut par défaut du foyer** : aucune entrée ne porte de drapeau, c'est la promotion d'office de `ItemStatus.save()` qui marque le premier statut créé. Réordonner la liste déplace donc le défaut d'un nouveau foyer, silencieusement. Un drapeau dans les entrées ne rendrait pas la réorganisation plus sûre, il la ferait échouer : la promotion d'office marquerait quand même la nouvelle tête de liste, et l'entrée marquée arriverait ensuite sur une contrainte `unique_default_item_status_per_household` déjà satisfaite, donc une `IntegrityError` à la création du foyer.

C'est une copie, pas une référence : le foyer peut renommer, supprimer et réordonner tout ce qu'il reçoit, et rien ne remonte à la source. La commande `seed` s'en sert pour que la base de développement ressemble à un foyer réel ; son déclenchement à l'inscription relève de #41.

Les noms sont en français, comme tout ce que l'utilisateur lit. Le code, lui, reste en anglais.

## Ce que le schéma ne porte pas

**Une ligne de kit référence un objet et une personne du même foyer que son kit.** Trois clés étrangères mènent au foyer par trois chemins différents, et aucune contrainte ne les oblige à converger. C'est à l'application de valider chaque clé étrangère reçue contre le foyer courant, comme le rappellent les conventions d'API dans [`docs/api/`](../api/README.md).

`check_integrity` les liste, comme il liste les invariants du foyer : une ligne dont l'objet **ou** la personne vient d'ailleurs est un état interdit, et le seul moyen de s'en apercevoir sans le chercher.

**Un foyer qui a des statuts en a un par défaut.** La contrainte partielle porte « au plus un » ; elle ne sait pas exiger qu'il y en ait un, et une suppression par l'admin ou une écriture en masse peut retirer le dernier drapeau. `default_status` renvoie alors `None` plutôt que de lever : c'est un état anormal mais lisible, et l'appelant est mieux placé pour décider quoi en dire.

`check_integrity` le liste, restreint à ce qui est vraiment interdit **aujourd'hui** : un foyer qui a des statuts et aucun défaut. Un foyer qui n'a aucun statut n'est pas signalé, parce que c'est encore le cas normal — l'inscription crée un foyer sans catalogue, et c'est #41 qui y branchera `install_base_catalog`. Signaler ces foyers-là ferait crier la commande sur chaque inscription, et une alerte qui crie toujours finit éteinte. Le jour où #41 est livrée, la restriction tombe et « aucun statut » devient à son tour un état interdit.
