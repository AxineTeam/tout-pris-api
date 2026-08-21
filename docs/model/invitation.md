# Inviter quelqu'un dans un foyer

## Le besoin

C'est le seul moment où un foyer **partagé** se peuple. Chaque compte a le sien depuis #52, mais un foyer à soi ne tient aucune des promesses du produit : préparer à plusieurs commence par inviter quelqu'un.

Un membre saisit une adresse, l'invité reçoit un lien, il le suit et rejoint le foyer. S'il a déjà un compte il rejoint directement, sinon il s'inscrit et rejoint dans la foulée : l'invitation n'est jamais un cul-de-sac pour quelqu'un qui n'a pas encore de compte.

## La table

`Invitation` porte le foyer partagé, l'adresse invitée, l'empreinte d'un jeton, l'auteur de l'invitation, une date d'expiration, et — une fois l'invitation acceptée — la date et le compte qui l'ont acceptée. Elle porte aussi une `Person` optionnelle, expliquée plus bas.

Le jeton est un secret opaque tiré par `secrets.token_urlsafe`, pas un identifiant devinable : quiconque le détient rejoint le foyer, il vaut donc un mot de passe à usage unique. `accepted_at` le neutralise après usage.

**Il n'est jamais stocké.** La base ne garde que son empreinte SHA-256, unique et indexée, et le secret ne vit qu'en mémoire le temps de construire l'URL du message. Le laisser en clair suffirait à n'importe quel compte d'administration ouvrant une invitation en attente pour rejoindre un foyer dont il n'est pas membre — un mot de passe à usage unique ne se stocke pas plus en clair que les autres.

C'est aussi pour cela que le jeton n'est pas produit par un `default` sur le modèle : le faire tirer par Django au moment d'écrire, c'est exactement ce qui force sa persistance. Il est tiré par le code qui invite, qui range l'empreinte et transmet la valeur claire à l'envoi.

SHA-256 sans sel ni étirement suffit, contrairement à un mot de passe : 256 bits tirés au hasard ne s'attaquent ni par dictionnaire ni par force brute, et argon2 est fait pour les secrets à faible entropie. La recherche à l'acceptation reste une égalité exacte sur une colonne indexée.

L'expiration est d'une semaine. Une invitation qui traîne dans une boîte pendant des mois est une porte ouverte que personne ne surveille.

## Accepter n'enlève rien

L'invité garde son foyer personnel et gagne un foyer partagé, comme on rejoint une organisation sans perdre son espace à soi. Il n'y a donc aucun nettoyage à faire après une acceptation, et surtout aucune suppression automatique déclenchée sur la foi d'une heuristique.

Ça n'a pas toujours été le plan. Tant que le foyer créé à l'inscription n'avait pas de sens produit, celui de l'invité passait pour un déchet, et l'acceptation était censée le supprimer en le reconnaissant à sa date de création et à sa solitude. #52 a tranché l'inverse et a rendu ce code sans objet : ce qu'on prenait pour un accident est l'espace privé de l'invité.

## On n'invite pas dans un foyer personnel

Il est personnel par définition, et son propriétaire en est le seul membre possible. Les routes d'invitation ne résolvent donc que les foyers partagés, et un foyer personnel répond `404` sur toutes, y compris à son propre propriétaire.

C'est `404` et non une erreur de validation parce que la collection n'existe pas : un foyer personnel n'a pas de sous-ressource « invitations », pas plus qu'il n'a d'invitations à lister ou à annuler. Répondre `422` sur la seule création laisserait entendre que le reste de la collection, lui, existe.

## La personne est désignée en invitant, pas en acceptant

Le foyer partagé contient déjà des `Person` sans compte, et l'invité correspond souvent à l'une d'elles, déjà créée sous le nom « Papa ». L'invitation peut donc désigner cette personne, et l'acceptation y inscrit le compte au lieu d'en créer une deuxième.

C'est l'inviteur qui choisit, parce que c'est lui qui sait que l'adresse correspond à « Papa » : l'invité, lui, ne connaît pas les personnes du foyer avant d'y entrer, et lui demander de se reconnaître dans une liste lui montrerait la composition d'un foyer qu'il n'a pas encore rejoint.

La personne désignée est cherchée **parmi celles du foyer**, et non validée après coup : une personne d'un autre foyer est alors refusée dans les mêmes termes qu'une personne inexistante. Distinguer les deux permettrait d'énumérer les identifiants des personnes des foyers d'autrui, ce que la règle « `404` et jamais `403` » interdit partout ailleurs.

Le rattachement est vérifié au moment d'accepter, pas seulement au moment d'inviter : entre les deux, la personne a pu être supprimée, changer de foyer ou recevoir un compte. Si l'une de ces conditions n'est plus remplie, l'acceptation ne rattache rien, plutôt que d'échouer sur un détail que l'invité ne peut pas corriger.

**Accepter ne crée aucune `Person`.** Sans personne désignée — ou avec une désignation devenue caduque — l'invité entre dans le foyer sans y être encore quelqu'un, et c'est l'écran « qui êtes-vous ? » qui tranche, en rattachant une personne existante par `POST /api/households/{household_id}/persons/{id}/claim/`.

Créer d'office une personne à l'arrivée revenait à répondre à sa place. Le cas se voit sur un ex-membre qui revient : son retrait avait vidé le compte de sa personne sans la supprimer, et l'acceptation lui en fabriquait une seconde à côté, l'ancienne restant orpheline. L'unicité `(household, user)` ne l'attrapait pas, celle qu'il avait quittée portant `user = NULL`.

La `Person` que l'inscription crée pour tout nouveau compte n'entre pas en concurrence avec celle-ci : elle vit dans le foyer personnel de l'invité, pas dans le foyer qu'il rejoint.

## La réponse ne dit jamais qui a un compte

Inviter répond `204`, sans corps, quel que soit le cas. Une adresse qui a déjà un compte, une adresse inconnue, une adresse qui est déjà membre du foyer : les trois réponses sont identiques au bit près.

C'est la seule façon de fermer l'oracle d'énumération. Une route qui répondrait `201` avec l'invitation créée dans un cas et `409` dans l'autre dirait à n'importe quel membre d'un foyer quelles adresses ont un compte sur le service, et il suffit d'un foyer pour devenir membre d'un foyer.

Le contenu de l'email, lui, diffère : « connecte-toi pour rejoindre » ou « crée ton compte ». Cette distinction-là n'est lisible que par le titulaire de l'adresse.

Ré-inviter quelqu'un qui est déjà membre ne crée donc rien et n'envoie rien, sans que l'appelant puisse le déduire de la réponse.

## Ré-inviter invalide l'invitation précédente

Ré-inviter la même adresse supprime l'invitation en attente avant d'en créer une nouvelle. Accumuler des jetons valides en parallèle multiplierait les portes d'entrée sans que personne ne le voie, et annuler une invitation n'aurait plus de sens si l'annulation laissait ses sœurs ouvertes.

Annuler, c'est supprimer la ligne. Il n'y a pas de champ `revoked_at` : une invitation annulée ne raconte rien qu'on ait besoin de relire.

## Les emails

Ils partent par `django.core.mail`, comme ceux d'allauth, et le choix du transport est une règle de `settings.py` documentée dans le README. Il n'y a pas d'abstraction d'envoi propre aux invitations, et les tests n'ont aucun double à installer : Django impose son mailer mémoire.

Les gabarits sont des templates Django versionnés dans le dépôt, pas des templates hébergés chez Brevo. Un template distant se modifie sans redéploiement, mais sort le contenu du versioning et surtout crée un second mécanisme d'email à côté de celui qui existe déjà pour la vérification d'adresse.

Un échec d'envoi ne fait pas échouer la requête. L'invitation est créée puis l'email part, et l'envoi est déclenché après la validation de la transaction : englober un appel réseau dans la transaction la tiendrait ouverte pendant tout l'appel, et répondre en erreur après avoir écrit laisserait l'appelant croire que rien n'existe. Le rattrapage est de ré-inviter, ce qui remplace le jeton et renvoie l'email.

## La limite d'envoi

Une route qui déclenche un email vers une adresse arbitraire est une machine à spam. La création est donc limitée par `ScopedRateThrottle`, à vingt invitations par jour et par compte.

La limite est par compte et non par foyer : c'est plus strict, puisqu'un membre de deux foyers partage son compteur, et il faut de toute façon être membre d'un foyer pour y inviter quelqu'un. Comme pour les limites d'allauth, les compteurs vivent dans le cache Django, local au processus tant qu'aucun cache partagé n'est configuré.
