# Foyer, utilisateurs et personnes

## Le besoin

Un voyage se prépare à plusieurs : les deux parents cochent leurs affaires et voient l'avancement de l'autre en temps réel. Mais on prépare aussi les affaires de gens qui ne se connecteront jamais à l'application, à commencer par les enfants.

Ces deux constats séparent deux questions que l'on confond facilement : **pour qui** est un objet, et **qui a le droit** de modifier la liste. Ce sont deux notions distinctes dans le modèle.

## Le partage se fait au niveau du foyer

Partager voyage par voyage obligerait à réinviter son partenaire, et à ressaisir les personnes et le référentiel d'objets à chaque nouveau voyage. Le `Household` porte donc le partage une fois pour toutes : ses membres, ses personnes, son référentiel et ses voyages sont communs.

C'est aussi moins de tables qu'un partage par voyage, pas plus.

Le foyer et l'appartenance à un foyer sont **invisibles dans l'interface**. Le foyer est créé implicitement à l'inscription, et `HouseholdMember` ne se manifeste que par l'action « inviter mon partenaire ». Il n'y a jamais d'écran « gérer mes foyers ».

`HouseholdMember` étant une table de liaison, un utilisateur peut appartenir à plusieurs foyers. Rien ne l'expose au départ, mais le schéma ne ferme pas la porte aux familles recomposées ni au groupe d'amis qui part ensemble.

Le champ `role` existe pour ne pas avoir à migrer le jour où les droits se différencient. Aucun système de permissions n'est construit pour l'instant : tous les membres peuvent tout faire.

## Person couvre les deux cas

`Person` désigne une personne pour qui on prépare des affaires, qu'elle ait un compte ou non. Un enfant est une `Person` sans `user_id`, un partenaire une `Person` dont le `user_id` pointe vers son compte.

L'alternative — deux colonnes exclusives sur chaque ligne de liste, l'une vers `User` et l'autre vers une table de personnes sans compte — aurait imposé de traiter deux cas partout où l'on demande « pour qui ». Avec `Person`, il n'y a qu'une clé étrangère et qu'un seul sélecteur.

Contrairement au foyer, `Person` est l'objet le plus visible de l'application : l'utilisateur crée « Enfant 1 », le nomme, et le retrouve dans chaque écran. Un unique écran « la famille » liste les personnes du foyer, certaines ayant un compte lié.

Un compte ne peut être rattaché qu'à une seule personne par foyer. La contrainte d'unicité porte sur `(household_id, user_id)` : `NULL` n'entrant pas en conflit avec lui-même en SQL, autant de personnes sans compte que voulu cohabitent dans le même foyer.

## User n'appartient pas au domaine

`User` est le modèle d'authentification de Django, custom depuis la première migration pour rester extensible. L'authentification elle-même n'est pas écrite ici : django-allauth apporte l'inscription, la connexion, la vérification d'email et les fournisseurs externes, avec les tables d'identités et de jetons qui vont avec.

Le domaine n'ajoute donc **aucune colonne d'authentification** à `User`. Il n'en attend qu'une chose : un `email` unique, qui est l'adresse de connexion et le point d'entrée d'une invitation dans un foyer.

## Suppressions

Supprimer un foyer supprime ses membres et ses personnes : elles n'ont pas d'existence en dehors de lui.

Supprimer un utilisateur supprime ses appartenances, mais **conserve les personnes** qui lui étaient liées, dont le `user_id` retombe à `NULL`. Un compte fermé ne doit pas faire disparaître les affaires de quelqu'un d'une liste en cours.

Ces règles sont déclarées sur les clés étrangères (`on_delete=CASCADE` et `on_delete=SET_NULL`) et appliquées par l'ORM Django au moment de la suppression. Aucun pragma SQLite n'est à activer : Django active déjà les clés étrangères, et les tests vérifient le comportement en supprimant réellement les lignes plutôt qu'en relisant la déclaration.

La garantie est donc double, et il vaut mieux le savoir avant d'écrire du SQL à la main : la base refuse une suppression qui laisserait des lignes orphelines, et c'est l'ORM qui sait comment l'éviter en supprimant ou en détachant d'abord. Un `DELETE` brut sur un foyer est rejeté par la base plutôt que d'orpheliner ses personnes.
