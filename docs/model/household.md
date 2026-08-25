# Foyer, utilisateurs et personnes

## Le besoin

Un voyage se prépare à plusieurs : les deux parents cochent leurs affaires et voient l'avancement de l'autre en temps réel. Mais on prépare aussi les affaires de gens qui ne se connecteront jamais à l'application, à commencer par les enfants.

Ces deux constats séparent deux questions que l'on confond facilement : **pour qui** est un objet, et **qui a le droit** de modifier la liste. Ce sont deux notions distinctes dans le modèle.

## Le partage se fait au niveau du foyer

Partager voyage par voyage obligerait à réinviter son partenaire, et à ressaisir les personnes et le référentiel d'objets à chaque nouveau voyage. Le `Household` porte donc le partage une fois pour toutes : ses membres, ses personnes, son référentiel et ses voyages sont communs.

C'est aussi moins de tables qu'un partage par voyage, pas plus.

`HouseholdMember` étant une table de liaison, un utilisateur appartient à plusieurs foyers, et c'est le cas nominal et non une porte laissée ouverte : chacun a le sien et rejoint ceux qu'on lui partage.

Le champ `role` porte les droits depuis #59. `owner` invite, retire un membre, distribue les rôles, renomme et supprime le foyer ; `member` fait le reste, c'est-à-dire tout le quotidien. Un membre qui n'a pas encore de personne ne peut que créer la sienne et la revendiquer.

Il n'a rien porté pendant longtemps, et c'était un report assumé plutôt qu'un oubli : tant que rejoindre un foyer était impossible, ses membres étaient toujours le même compte, et des droits distincts n'auraient distingué personne. L'invitation puis les routes destructrices ont retiré cette excuse — laisser un invité de passage supprimer le foyer et ses listes n'était plus une abstraction.

Le refus est un `403` et non un `404` : la ressource est bien celle de son foyer, elle n'est pas cachée, elle est interdite. Le raisonnement complet est dans [`docs/api/README.md`](../api/README.md).

## Le foyer personnel

Tout compte a **toujours** un foyer à lui, créé à l'inscription et qu'il ne partage avec personne. Tout compte de l'application, s'entend : un compte d'administration créé par `createsuperuser` ne passe pas par l'inscription, donc pas par le signal qui crée le foyer, et n'en a aucun. Il ne se connecte pas au produit, seulement à l'admin. C'est là qu'on prépare le sac de piscine ou le bagage d'un déplacement professionnel : des affaires qui n'ont rien à faire dans la liste familiale, et qu'on ne veut pas voir passer sous les yeux des autres membres.

C'est l'organisation de Notion, de Slack et de la plupart des outils partagés : un espace à soi, et des espaces qu'on rejoint. L'invitation ne convertit donc pas un compte, elle lui ajoute un foyer.

Le foyer personnel n'est **pas un type différent** : c'est un `Household` comme les autres, avec ses personnes, son référentiel d'objets et ses voyages. Un seul type d'objet veut dire un seul jeu de routes, un seul cloisonnement à écrire et un seul chemin à tester, alors que deux tables auraient dupliqué tout le domaine pour la seule différence du nombre de membres.

Ce qui le distingue est `personal_of`, une clé étrangère vers le compte dont il est l'espace privé, vide sur un foyer partagé. Un `OneToOneField` plutôt qu'un booléen `is_personal` : l'invariant « au plus un foyer personnel par compte » est alors garanti par une contrainte d'unicité en base, sans code pour la maintenir à chaque création et chaque suppression — c'est le reproche fait au drapeau `is_default` des statuts de préparation, et il vaut ici aussi.

**Son nom en base ne remonte jamais à l'interface.** L'inscription le nomme d'après le compte, ce qui donne un intitulé lisible dans l'admin et dans les journaux, mais l'application affiche « Personnel » : personne n'a envie de lire son propre identifiant en tête d'un écran, ni de nommer un espace dont il est le seul habitant. L'API expose donc un booléen `personal` plutôt que le nom, et le libellé appartient au front.

## Le foyer est visible

Le foyer n'apparaissait dans aucun écran tant qu'un compte n'en avait qu'un. Dès qu'il y en a plusieurs, il faut choisir dans lequel on travaille, et `GET /api/households/` sert cet écran de sélection.

C'est un renversement assumé par rapport à la première version de ce document, qui promettait qu'il n'y aurait « jamais d'écran gérer mes foyers ». Cette promesse tenait tant que le foyer était une notion purement technique ; elle tombe avec le foyer personnel, qui est une notion produit.

Ce que ça coûte, et il vaut mieux le savoir en le décidant : le référentiel d'objets et les statuts de préparation appartiennent au foyer, donc deux foyers, ce sont deux catalogues à entretenir. Une « gourde thermos » ajoutée dans son espace personnel ne remontera pas dans le foyer familial. Le catalogue de base copié à la création amortit le démarrage, pas l'entretien.

## Person couvre les deux cas

`Person` désigne une personne pour qui on prépare des affaires, qu'elle ait un compte ou non. Un enfant est une `Person` sans `user_id`, un partenaire une `Person` dont le `user_id` pointe vers son compte.

L'alternative — deux colonnes exclusives sur chaque ligne de liste, l'une vers `User` et l'autre vers une table de personnes sans compte — aurait imposé de traiter deux cas partout où l'on demande « pour qui ». Avec `Person`, il n'y a qu'une clé étrangère et qu'un seul sélecteur.

Contrairement au foyer, `Person` est l'objet le plus visible de l'application : l'utilisateur crée « Enfant 1 », le nomme, et le retrouve dans chaque écran. Un unique écran « la famille » liste les personnes du foyer, certaines ayant un compte lié.

Un compte ne peut être rattaché qu'à une seule personne par foyer. La contrainte d'unicité porte sur `(household_id, user_id)` : `NULL` n'entrant pas en conflit avec lui-même en SQL, autant de personnes sans compte que voulu cohabitent dans le même foyer.

## User n'appartient pas au domaine

`User` est le modèle d'authentification de Django, custom depuis la première migration pour rester extensible. L'authentification elle-même n'est pas écrite ici : django-allauth apporte l'inscription, la connexion, la vérification d'email et les fournisseurs externes, avec les tables d'identités et de jetons qui vont avec.

Le domaine n'ajoute donc **aucune colonne d'authentification** à `User`. Il n'en attend qu'une chose : un `email` unique, qui est l'adresse de connexion et le point d'entrée d'une invitation dans un foyer.

## Cycle de vie d'un compte

Un compte n'existe jamais seul : à l'inscription, le foyer est créé, le compte y est inscrit comme membre, et la personne qui le représente est créée dans ce foyer. Les trois écritures sont faites dans la même transaction — un compte sans foyer serait inutilisable, puisque tout le domaine est porté par le foyer.

Il n'y a qu'un seul chemin d'inscription du point de vue du domaine, alors qu'il y en a deux du point de vue de l'authentification : par email et mot de passe, ou par un fournisseur externe. django-allauth fait converger les deux vers un signal unique, `user_signed_up`, émis au moment où le compte vient d'être créé et avant l'ouverture de la session ; c'est lui que le domaine écoute. Se connecter une seconde fois par un fournisseur, ou rattacher un fournisseur à un compte existant, n'est pas une inscription et ne crée donc pas de second foyer.

Le foyer créé à l'inscription est le foyer personnel du compte : `personal_of` pointe vers lui.

Le foyer et la personne prennent pour nom celui du compte : son nom complet quand le fournisseur l'a transmis, sinon la partie locale de son adresse email. Le nom du foyer personnel n'est jamais affiché, il ne sert qu'à l'admin ; la personne, elle, est immédiatement visible et reste renommable.

Le membre créé porte le rôle `owner` : l'inscription est le seul moment où l'on sait qui a ouvert le foyer.

La vérification de l'adresse email est obligatoire et intervient **après** cette création : le compte, son foyer et sa personne existent dès l'inscription, alors que la session ne s'ouvre qu'une fois l'adresse confirmée. Un compte jamais confirmé laisse donc un foyer vide en base, sans aucune conséquence fonctionnelle.

Le second membre d'un foyer partagé arrive par l'invitation. Un foyer personnel, lui, n'en a jamais qu'un.

Ce second membre n'est pas une personne pour autant : rejoindre un foyer n'y crée personne. Il choisit qui il est parmi les personnes déjà là, ou se crée la sienne — l'invitation ne le choisit pas pour lui. Une appartenance sans personne est donc un état normal et transitoire, et non un accident à réparer.

## Cycle de vie d'un foyer partagé

Un foyer partagé se crée à la demande, et son créateur y entre par le même chemin qu'un compte dans son foyer personnel : le foyer, l'appartenance `owner` et la personne qui le représente sont écrits dans la même transaction. C'est la seule création de foyer que l'API expose ; le foyer personnel, lui, n'est créé que par l'inscription.

On le quitte en retirant son appartenance, et retirer celle de quelqu'un d'autre est la même écriture — aucun droit ne les distingue tant que le rôle ne porte rien.

Le retrait **délie la personne sans la supprimer** : son `user` retombe à `NULL` et elle reste dans le foyer, exactement comme lors de la suppression d'un compte. La différence est que l'ORM ne peut rien en dire ici, il n'y a pas de ligne supprimée dont une clé étrangère dépendrait : c'est le code du retrait qui délie, et un test qui le garde.

Le dernier membre ne peut pas partir. Un foyer partagé sans membre ne serait plus lisible par personne, et ses personnes comme ses futures listes resteraient en base sans porte d'entrée ; supprimer le foyer reste possible et dit clairement ce qu'il emporte.

## Suppressions

Supprimer un foyer supprime ses membres et ses personnes : elles n'ont pas d'existence en dehors de lui.

Supprimer un utilisateur supprime ses appartenances, mais **conserve les personnes** qui lui étaient liées, dont le `user_id` retombe à `NULL`. Un compte fermé ne doit pas faire disparaître les affaires de quelqu'un d'une liste en cours.

Son foyer personnel part avec lui, en revanche : il n'a d'existence que pour ce compte, et personne d'autre ne peut y entrer. Les foyers partagés qu'il avait rejoints survivent, amputés de son appartenance.

Ces règles sont déclarées sur les clés étrangères (`on_delete=CASCADE` et `on_delete=SET_NULL`) et appliquées par l'ORM Django au moment de la suppression. Aucun pragma SQLite n'est à activer : Django active déjà les clés étrangères, et les tests vérifient le comportement en supprimant réellement les lignes plutôt qu'en relisant la déclaration.

La garantie est donc double, et il vaut mieux le savoir avant d'écrire du SQL à la main : la base refuse une suppression qui laisserait des lignes orphelines, et c'est l'ORM qui sait comment l'éviter en supprimant ou en détachant d'abord. Un `DELETE` brut sur un foyer est rejeté par la base plutôt que d'orpheliner ses personnes.

## Les invariants que le schéma ne porte pas

Trois règles de ce document ne sont pas exprimables en contrainte, et c'est une conséquence du modèle plutôt qu'un oubli.

**Un compte a exactement un foyer personnel.** C'est le foyer qui pointe vers le compte, et l'unicité de `personal_of` garantit qu'il n'y en a pas deux ; exiger qu'il y en ait au moins un demanderait au compte de pointer vers son foyer en retour, donc un cycle de clés étrangères qu'aucune des deux tables ne pourrait plus insérer en premier. L'invariant ne vaut que pour les comptes d'application : `check_integrity` écarte ceux qui portent `is_staff` ou `is_superuser`, faute de quoi le premier `createsuperuser` la rendrait rouge à demeure — et une alerte qui crie toujours finit éteinte, emportant le signalement qu'on attendait. Le filtre nomme les deux drapeaux plutôt que de deviner à l'absence de mot de passe utilisable, qui frapperait un compte de service ordinaire.

**Un foyer partagé a au moins un membre.** Aucune colonne ne porte un compte de lignes d'une autre table, et le foyer doit exister avant l'appartenance qui le référence.

**La personne d'un compte appartient à un foyer dont ce compte est membre.** `Person.user` et `HouseholdMember.user` désignent le même compte sans que rien ne les relie : c'est le retrait d'un membre qui délie la personne, en code.

Ces trois règles vivent donc dans le code applicatif, et un bug, une commande de migration de données ou un `shell_plus` un soir de fatigue peuvent les enfreindre sans que la base bronche. `uv run python manage.py check_integrity` est ce qui les relit : une section par invariant, rien à dire sur une base saine, et un code de sortie non nul quand elle trouve quelque chose.

Elle nomme et ne répare pas. Une réparation automatique sur un état qu'on ne s'explique pas encore ferait disparaître la trace du bug qui l'a produit ; le jour où le cas se présentera, elle aura sa place dans une commande séparée qu'on lance en connaissance de cause, et qui rejouera l'opération d'inscription plutôt que le signal `user_signed_up`, pour ne pas rejouer ce qu'un autre récepteur y aurait accroché.

Un membre sans personne n'en fait pas partie : c'est l'état normal d'un arrivant qui n'a pas encore choisi qui il est.
