# Voyages et lignes de préparation

## Le besoin

Un voyage est une liste. Il n'y a **aucun niveau intermédiaire** entre le voyage et ses lignes : ni rubrique, ni sous-liste, ni sac, ni section. Ce que l'utilisateur voit à côté d'une ligne est un **tag** — les kits auxquels l'objet appartient — et ce tag se lit dans le catalogue au moment de l'affichage : rien n'a à être stocké sur la ligne pour le produire.

Un voyage appartient au foyer, comme le référentiel d'objets et les kits. Il porte un nom et une date, et tous les membres du foyer préparent la même liste en parallèle, chacun voyant l'avancement de l'autre.

La ligne — `TripItem` — est l'unité de suivi, et c'est la table la plus manipulée de l'application : faire avancer le statut d'une ligne est le geste que l'on répète des dizaines de fois par voyage. Tout le reste du modèle existe pour qu'il y ait le moins de lignes possible à saisir à la main.

## Les participants

Un voyage désigne les personnes du foyer qui partent. Ce n'est pas une décoration : la liste sert à **filtrer l'instanciation des kits** — « affaires enfants » n'injecte pas les lignes d'un enfant resté chez ses grands-parents — et à alimenter les sélecteurs « pour qui » du voyage.

`TripParticipant` est une table de liaison sans donnée propre, avec une unicité sur `(trip, person)`. Elle ne porte ni rôle ni ordre : participer est un fait binaire.

Une personne qui participe n'a pas forcément de ligne, et une ligne peut viser une personne qui ne participe plus — retirer quelqu'un d'un voyage en cours ne doit pas effacer ce que les membres ont déjà préparé pour lui. Ce n'est donc pas un état interdit, et rien ne le signale : c'est à l'interface de montrer ces lignes et de proposer de les retirer, jamais au retrait de le décider tout seul.

## L'initialisation d'un voyage

L'utilisateur coche des kits. C'est le cœur de la valeur du produit : 95 % des affaires d'un voyage sont celles du précédent, et un voyage doit se remplir en quelques clics.

Il complète ensuite par des **ajouts libres** : des objets qui n'appartiennent à aucun kit, voire des objets absents du référentiel du foyer et créés à la volée — c'est d'ailleurs le principal chemin d'enrichissement du référentiel. Ces lignes ne se distinguent en rien des autres : elles s'affichent simplement sans tag, leur objet n'étant dans aucun kit.

Une ligne ne dit donc pas d'où elle vient, et c'est le choix retenu : le tag qu'elle affiche qualifie l'**objet** — « 5 t-shirts » porte « affaires de rando » parce que le kit contient l'objet, pas parce que la ligne en serait issue. Le raisonnement complet, et l'argument contraire qu'il remplace, sont dans [`catalog.md`](catalog.md).

`TripItem` n'a donc plus qu'une seule relation facultative, et elle se lit sans ambiguïté : `person` vide signifie **objet commun au voyage** — la trousse à pharmacie — avec un statut unique, et non objet orphelin ; la suppression d'une personne y ramène aussi ses lignes, comme le dit « Les suppressions ».

### Instancier un kit

L'instanciation est une **copie, jamais une référence** : sans elle, éditer un kit réécrirait les voyages passés, et retirer une ligne d'un voyage la retirerait du kit. Ce qui est copié, ce sont les valeurs de la ligne de kit ; rien ne relie ensuite la ligne du voyage au kit qui l'a produite.

Pour chaque `KitItem` du kit, dans l'ordre de ses positions :

- la ligne est **ignorée** si elle vise une personne qui ne participe pas au voyage ;
- sinon un `TripItem` est créé, avec l'objet, la personne et la quantité copiés depuis la ligne de kit ;
- `status` reçoit le statut par défaut du foyer, celui que porte le drapeau `is_default` — la règle est décrite dans [`catalog.md`](catalog.md) ;
- `position` vient de l'ordre du kit : les lignes sont créées dans cet ordre et s'ajoutent à la fin du voyage, si bien que l'ordre relatif du kit est conservé sans avoir à le recalculer.

Un foyer sans aucun statut ne peut donc rien instancier, `status` n'étant pas nullable : `default_status` renvoie `None` dans ce cas et la route refusera en `409` plutôt que de créer une ligne sans statut. Dès qu'un foyer a un statut il en a un par défaut, le premier créé prenant le rôle d'office, et `check_integrity` signale un foyer qui aurait des statuts sans défaut : c'est un état anormal, pas un cas à contourner par une colonne facultative.

Cocher un kit dont **toutes** les lignes visent des non-participants ne produit rien et ne laisse aucune trace : il n'existe pas de table de liaison entre le voyage et le kit, et c'est un choix assumé, expliqué dans [`catalog.md`](catalog.md). L'interface doit donc le dire au moment du clic, la base ne s'en souviendra pas.

### Recocher un kit est idempotent

Recocher un kit déjà appliqué n'ajoute que **les lignes absentes**. C'est ce qui permet d'ajouter « affaires de rando » en cours de préparation, et de rattraper un kit enrichi entre-temps, sans produire de doublons.

Une ligne du kit est considérée comme déjà présente quand le voyage porte une ligne de **même objet et même personne**. Ces deux colonnes sont la clé, et rien d'autre.

C'est cette clé qui porte la règle **un objet n'entre dans un voyage qu'une seule fois**. Cocher « sac à langer » puis « affaires de rando » quand les deux contiennent « crème solaire » produit une ligne, pas deux, et cette ligne porte les deux tags. Un ajout libre compte de la même façon : l'objet est déjà là, la ligne du kit ne s'ajoute pas par-dessus. Qui veut deux lignes distinctes crée deux objets ou passe la quantité à deux — on tranchera à l'usage.

La quantité n'en fait pas partie, et n'est **pas réécrite** : l'utilisateur a pu passer de cinq à trois t-shirts pour ce voyage-là, et un recochage qui rétablirait la valeur du kit annulerait sa décision sans le prévenir.

**Une ligne de voyage packe au moins un exemplaire**, comme une ligne de kit ([`catalog.md`](catalog.md)) : une `CheckConstraint` sur `quantity` le tient de chaque côté, si bien que l'instanciation, qui recopie la quantité par `objects.create`, ne peut pas propager une ligne à zéro.

Conséquence à connaître : une ligne que l'utilisateur a supprimée du voyage **revient** s'il recoche le kit. Aucune pierre tombale n'est stockée pour s'en souvenir, et c'est le bon compromis — le recochage est un geste explicite, alors qu'une mémoire des suppressions serait invisible et impossible à corriger.

Cette clé est portée par la base, et il faut **deux contraintes** pour la dire en entier. Une unicité sur `(trip, item_type, person)` seule laisserait passer le doublon qu'on veut le plus éviter : deux `NULL` ne s'opposent pas en SQL, si bien que deux lignes du même objet sans personne — deux fois la trousse à pharmacie — la traverseraient sans rien violer. Une seconde contrainte, partielle, ferme ce trou : unique sur `(trip, item_type)` sous la condition `person IS NULL`, ce que le SQL rend en index unique avec un `WHERE`. Le dépôt emploie déjà une partielle de la même famille pour le statut par défaut d'un foyer, décrite dans [`catalog.md`](catalog.md).

Les contraintes ne remplacent pas le garde-fou applicatif, elles le **doublent**. Le recochage reste ce qui rend l'opération idempotente : il doit ignorer les lignes déjà présentes, sinon il échouerait en `IntegrityError` au lieu de ne rien faire, et lui seul sait laisser tranquille la quantité. Ce que la base apporte est la garantie que la règle tient même quand un chemin l'oublie.

## Le suivi

Chaque ligne porte un statut, une ligne du référentiel du foyer décrite dans [`catalog.md`](catalog.md). La progression du voyage se calcule à partir de la catégorie de ces statuts (`not_started`, `in_progress`, `done`), jamais à partir de leur ordre d'affichage.

Le statut est obligatoire : une ligne sans statut ne serait ni affichable ni comptable dans la barre d'avancement, et « pas encore préparé » est déjà un statut.

## La promotion vers un kit

Un objet ajouté librement et qui se révèle récurrent doit pouvoir rejoindre un kit en un geste.

L'opération est une **seule écriture** : elle crée le `KitItem` — copie de l'objet, de la personne et de la quantité, ajouté à la fin du kit. La ligne du voyage n'est pas touchée et affiche pourtant le tag aussitôt, puisque le tag se lit dans le catalogue et n'a jamais été stocké sur elle.

C'est aussi ici que vit le garde-fou annoncé par [`catalog.md`](catalog.md) à la place d'une contrainte d'unicité sur `KitItem` : promouvoir un objet que le kit contient déjà pour la même personne ne doit pas créer une seconde ligne de kit, l'opération est alors sans effet.

La promotion se voit ailleurs que sur la ligne cliquée : **toute** ligne packant cet objet, dans n'importe quel voyage, y compris un voyage passé, affiche désormais le tag. C'est la contrepartie du tag dérivé, et elle est assumée — au même titre que le passé qui change quand on supprime un objet du référentiel. Ce qui reste figé est ce qui a été copié : la quantité, la personne, le statut. Le tag n'a jamais été de la copie, et la description de l'objet non plus : le texte libre du domaine est porté par le référentiel, si bien que la retoucher change ce qu'affichent toutes les lignes packant cet objet, dans les voyages passés comme dans ceux à venir. Une ligne ne porte plus de texte à elle, et il n'y a donc plus de rappel propre à une personne ou à un voyage.

## La duplication d'un voyage

Un voyage se duplique : la copie reprend les participants et les lignes de la source, sous un nouveau nom et à une nouvelle date, tous ses statuts remis au statut par défaut du foyer.

Un voyage **neuf** se compose de kits et ne se duplique pas : une copie hériterait du cadeau d'anniversaire et du maillot d'un séjour à la mer, et l'utilisateur nettoierait au lieu de préparer. La duplication sert le voyage **récurrent** — le week-end chez les grands-parents, tous les mois — dont l'utilisateur désigne la sortie précédente parce qu'il sait qu'elle est la bonne.

La copie est complète et sans filtre : chaque participant, chaque ligne avec son objet, sa personne, sa quantité et sa position. Rien n'est écarté, et il n'y a rien à écarter — « Les suppressions » interdit qu'un voyage porte une ligne ou une participation visant quelqu'un qui n'est plus du foyer.

Les statuts sont la seule chose qui ne se copie pas : la copie est un voyage à préparer, et reprendre l'avancement de la source l'afficherait déjà faite. Chaque ligne reçoit le statut par défaut du foyer, comme à l'instanciation d'un kit, et un foyer sans aucun statut ne peut donc pas plus dupliquer qu'instancier.

La copie n'est jamais archivée, même prise sur une archive : c'est le voyage que l'on part préparer.

La promotion d'un objet vers un kit reste le **seul** mécanisme d'enrichissement des kits depuis un voyage. Dupliquer ne crée aucun bloc réutilisable, et vingt duplications d'un même voyage laissent les kits exactement là où ils étaient.

## L'ordre

Les lignes d'un voyage sont ordonnées à l'échelle du voyage entier : `position` est numérotée avec `order_with_respect_to = "trip"`. Il n'y a rien de plus fin à ordonner, le voyage n'ayant aucun niveau intermédiaire, et les tags ne regroupent rien — ils qualifient une ligne, ils ne la contiennent pas.

L'ordre est initialisé depuis celui des lignes du kit à l'instanciation, puis retouchable dans le voyage sans que le kit en sache rien.

Les comportements de `django-ordered-model` — attribution à la création, fermeture du trou à la suppression, `up()`/`down()`/`to()` en plusieurs écritures, et le piège de `model_bakery` qui remplit `position` au hasard — sont décrits dans [`catalog.md`](catalog.md) et valent ici à l'identique.

## La date

`date` est obligatoire, et c'est la seule que porte un voyage : le jour du départ, que le client préremplit avec celui du jour.

C'est une date et non un horodatage : personne ne prépare un sac à l'heure près, et une date évite d'avoir à choisir un fuseau pour une notion qui n'en a pas.

Les voyages sont listés du départ le plus récent au plus ancien, ce que porte l'`ordering` du modèle : c'est le voyage en préparation que l'on ouvre, pas celui de l'an dernier. Deux voyages du même jour sont départagés par le `pk` décroissant, le dernier créé d'abord. Le départage n'est pas décoratif : avec une seule date, l'égalité devient probable, et un ordre indéterminé ferait sauter les lignes d'une lecture à l'autre.

## L'archivage

Un voyage passé quitte la liste sans être supprimé : `archived_at` porte le moment où il l'a quittée, et reste vide tant qu'il y figure.

Un horodatage plutôt qu'un booléen, parce qu'il date le geste et donne aux archives leur propre ordre — du dernier archivé au premier — là où la liste courante est ordonnée par date de départ. Désarchiver ramène `archived_at` à vide, et le voyage reprend sa place dans la liste courante.

Rien ne s'archive tout seul. Un voyage dont la date est passée reste dans la liste courante : la préparation continue souvent après le départ, et le retour a ses propres lignes.

L'archivage ne verrouille rien. Un voyage archivé se modifie exactement comme un autre, et c'est une décision d'API décrite dans [`docs/api/`](../api/README.md), pas une propriété du modèle.

## Les suppressions

Trois clés étrangères partent d'une ligne de voyage, et elles ne se comportent pas de la même façon. Ce n'est pas une incohérence : une ligne de voyage porte un état que des gens ont fait avancer, alors qu'une ligne de kit est un modèle que l'on réédite quand on veut.

**Le voyage et le foyer emportent tout.** Supprimer un voyage supprime ses lignes et ses participants, supprimer un foyer supprime ses voyages ; rien de tout cela n'a d'existence en dehors d'eux.

**Supprimer un kit n'atteint aucune ligne de voyage** : aucune ne le référence. Le tag disparaît des lignes dont il était le seul kit, et c'est tout ce qui se passe — un voyage en cours ne perd pas la moitié de sa liste parce qu'on a fait le ménage dans les blocs.

**Supprimer un objet du référentiel emporte les lignes qui le packent**, comme il emporte déjà les lignes de kit. Le refuser gèlerait le catalogue : un objet utilisé une seule fois, dans un voyage d'il y a trois ans, deviendrait indéboulonnable, et le nettoyage du référentiel — qui est un besoin réel, décrit dans [`catalog.md`](catalog.md) — serait impossible. Le chemin fréquent, lui, ne détruit presque rien : renommer un objet vers un nom déjà pris **fusionne**, et la fusion réaffecte les lignes de voyage au survivant — sauf celles qui feraient doublon avec une ligne déjà présente, qu'elle supprime pour ne pas violer l'unicité, en y laissant leur quantité. Le détail et la divergence avec les lignes de kit sont dans [`catalog.md`](catalog.md).

**Supprimer une personne rend communes les lignes qui la visaient.** `person` retombe à `NULL` et la ligne survit : la liste de ce qui a été préparé reste entière, et c'est ce qui compte pour un voyage passé, dont elle est la seule trace. Les deux autres options ont été écartées — effacer ses lignes viderait de ses affaires chaque voyage déjà fait, et refuser la suppression rendrait indéboulonnable une personne qu'un voyage d'il y a trois ans mentionne encore.

La contrepartie est réelle : « 5 t-shirts pour Enfant 2 » devient « 5 t-shirts » sans que personne l'ait demandé, la ligne se lit désormais comme un objet commun au voyage, et plus rien ne dit à qui elle était destinée. Elle est assumée : une ligne devenue commune se corrige ou se supprime en un geste, une ligne effacée ne revient pas.

**C'est l'inverse de ce que fait `KitItem`**, en `CASCADE` : la même suppression emporte les lignes de kit de la personne et rend communes ses lignes de voyage. Les deux tables divergent, et c'est la distinction posée en tête de section. Une ligne de kit est réappliquée à chaque voyage : la garder sans personne ferait demander ses t-shirts à tout le monde, indéfiniment, et [`catalog.md`](catalog.md) écarte le `SET_NULL` sur cet argument. Une ligne de voyage n'est réappliquée nulle part, sa personne n'était qu'une étiquette, et l'effacer ne coûte que de l'information.

**Supprimer un statut encore porté par des lignes est refusé**, et c'est la seule clé étrangère de la table à refuser quoi que ce soit. Le refus est porté en `RESTRICT` et non en `PROTECT`. La différence compte ici : `PROTECT` refuse la suppression même quand le statut part dans la même opération qu'un ancêtre commun, si bien que supprimer un foyer — ou un compte, qui emporte son foyer personnel — échouerait alors que toutes les lignes concernées étaient de toute façon en train de disparaître. `RESTRICT` lève exactement ce cas : la ligne référence son voyage en `CASCADE`, elle est déjà dans l'ensemble à supprimer, et le refus tombe. Le foyer reste supprimable d'un bloc, le statut seul ne l'est pas.

La suppression normale passe par `delete_status`, qui **réaffecte les lignes avant de supprimer** : d'abord vers un statut de même catégorie de progression quand il en existe un, sinon vers le statut par défaut. Sans ce premier choix, retirer un « commandé en ligne » ferait régresser jusqu'à « pas préparé » des objets que quelqu'un avait avancés. Le repli ne peut pas manquer : le foyer a toujours un statut par défaut dès qu'il a un statut, et ce n'est jamais celui que l'on supprime, puisque `delete_status` refuse d'entrée la suppression du défaut.

Deux conséquences à connaître, et elles sont le prix de ce choix :

**L'admin ne peut plus supprimer un statut porté par des lignes.** C'est le modèle qui refuse ce que seul `delete_status` sait faire proprement, et c'est délibéré : la porte de service reste ouverte sur ce que l'application interdit, pas sur ce qu'elle sait réparer.

**Un statut supprimé hors de `delete_status` échoue en `500`.** Le refus arrive sous la forme d'un `RestrictedError` de l'ORM, que DRF ne convertit pas : c'est le piège décrit dans [`docs/api/`](../api/README.md). Le `DELETE /api/households/{id}/item-statuses/{id}/` y échappe parce qu'il passe par `delete_status`, seul chemin qui réaffecte d'abord et qui refuse proprement en `Conflict`, rendu en `409`, quand le statut visé est le défaut. Toute autre suppression — une route à venir, un script — doit emprunter le même chemin.

## Ce que le schéma ne porte pas

**Tout ce qu'une ligne référence doit appartenir au foyer de son voyage.** Quatre clés étrangères mènent au foyer par quatre chemins — le voyage, l'objet, la personne, le statut — et rien ne les oblige à converger, les clés ne portant pas le foyer. C'est à l'application de valider chaque clé reçue contre le foyer courant, comme le rappellent les conventions d'API dans [`docs/api/`](../api/README.md), et c'est la même règle que le cloisonnement de sécurité.

**Un participant appartient au foyer du voyage.** Même raisonnement, et même absence de garant en base.

`check_integrity` liste ces deux états interdits, comme il liste déjà ceux du foyer et ceux du catalogue : c'est le seul moyen de s'apercevoir qu'ils se sont produits sans les chercher un par un.

**Une ligne visant un non-participant n'y figure pas**, et ce n'est pas un oubli : c'est un état normal après le retrait d'un participant, décrit plus haut. Une commande qui crierait dessus finirait éteinte.
