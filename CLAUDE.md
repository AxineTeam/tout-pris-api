# tout-pris-back

Backend Django du projet Tout Pris. Soit extrêmement concis.

## Langue

- Réponds en français sauf si le contexte est clairement anglophone
- Les messages de commit, noms de branches, code et commentaires dans le code restent en anglais

## Communication

- Soit brutalement honnête : si tu penses que j'ai tort dis-le moi !
- Pas de louanges inutiles ni de remplissage, réponses directes, pas de préambules
- Quand je pose une question réponds, ne fais pas de modifications, sauf si je l'ai explicitement demandé !
- Si tu rencontres une erreur que tu parviens à corriger sans comprendre pourquoi, documente-le !

## Stack

- Python 3.12 (épinglé dans `.python-version`), Django 6.1, Django REST Framework pour l'API, drf-spectacular pour l'OpenAPI générée, drf-pydantic pour dériver un serializer d'un modèle Pydantic, django-allauth en mode headless pour l'authentification
- Deux façons de déclarer un schéma : `ModelSerializer` quand il y a une table derrière, Pydantic via `drf-pydantic` quand il n'y en a pas (sortie d'un modèle de langage, réponse calculée)
- ORM et migrations Django (SQLite par défaut, `DATABASE_URL` lu par dj-database-url), migrations appliquées par l'entrypoint Docker, jamais par le code applicatif
- django-extensions pour `shell_plus`, `runserver_plus`, `reset_db` et `graph_models`
- model_bakery pour construire des objets depuis le modèle Django sans déclarer de factory, utilisé par la commande `seed`
- graphviz est une dépendance système : `graph_models` appelle le binaire `dot` via pydot, il est installé dans l'image de dev, donc dans le devcontainer
- Dépendances gérées par uv (`uv sync`, groupe `dev` dans `pyproject.toml`, lock dans `uv.lock`)
- pytest-django pour les tests, ruff pour lint et format
- Docker + docker compose, devcontainer basé sur le service `api`
- Le mailer est choisi dans `settings.py` : clé Brevo, Brevo ; hôte SMTP, ce serveur (Mailpit en dev) ; ni l'un ni l'autre, la console. La branche console garantit que le lien de vérification est lisible sans aucune configuration. Les variables s'appellent `EMAIL_HOST` et `EMAIL_PORT` mais sont stockées en minuscules : Django refuse de démarrer si ces deux *settings* existent à côté de `MAILERS`
- Deux Dockerfiles (pratiques uv officielles) : `Dockerfile` dev (uv, deps dev, `runserver`, monté sur `/app`), `Dockerfile.prod` multistage (image finale sans uv ni pip, non-root, gunicorn, base dans le volume `/data`)

## Structure

- `manage.py` : point d'entrée Django, équivalent de `rails`/`rake`
- `tout_pris/settings.py` : configuration, lue depuis l'environnement
- `tout_pris/urls.py` : URLconf racine, admin sur `/admin/`, API sur `/api/`, schéma et doc servis par drf-spectacular
- `tout_pris/views.py` : vues DRF du projet, dont `/api/health/`
- `tout_pris/mail.py` : envoi transactionnel via Brevo, exposé comme mailer Django
- `tout_pris/authentication.py` : `SessionAuthentication` de DRF annonçant un en-tête `WWW-Authenticate`, sans quoi une session non authentifiée reçoit `403` au lieu de `401`
- `.env.example` : toutes les variables d'environnement avec une valeur de développement
- `accounts/` : app du `User` custom, référencé par `AUTH_USER_MODEL` dès la migration initiale
- `households/` : app du domaine foyer — `Household`, `HouseholdMember`, `Person` — son admin, son API, le foyer personnel créé à l'inscription, et la commande `seed`
- `tests/` : suite pytest-django, une base de test isolée fournie par Django
- `docs/api/` : conventions de l'API — codes de retour, cloisonnement par foyer, schémas, collections
- `docs/model/` : besoin fonctionnel derrière le modèle de données, indépendant du framework, et `schema.png`, le diagramme ER généré
- Une app Django par domaine, comme des engines Rails

## Commandes

- Pas de Makefile ni de remplaçant : le README liste toutes les commandes, c'est la référence unique
- `docker compose build` / `up -d` / `down` / `logs -f api` : cycle de vie du serveur (port 8000)
- `docker compose exec api <commande>` : même commande dans le conteneur
- `uv run python manage.py runserver 0.0.0.0:8000` : serveur de dev
- `uv run python manage.py migrate` / `makemigrations` / `showmigrations` / `sqlmigrate` : migrations
- `uv run python manage.py reset_db --noinput` puis `migrate` puis `seed` : reconstruit la base de dev (jamais versionnée, `*.db` ignoré) et la remplit d'un foyer réaliste
- `seed` attend une base vide : rejoué par-dessus lui-même il échoue sur l'unicité de l'email, et sa transaction n'écrit rien
- `uv run python manage.py shell_plus` / `createsuperuser` / `changepassword` / `check`
- `uv run python manage.py graph_models accounts households --no-inheritance --exclude-models "Abstract*" | grep -v '// Created:' > docs/model/schema.dot` puis `uv run python manage.py graph_models accounts households --no-inheritance --exclude-models "Abstract*" --output docs/model/schema.png` : régénèrent le `.dot` vérifié en CI et l'image affichée dans le README
- `uv run pytest` : tests, échec sous 100 % de couverture
- `uv run ruff check .` / `ruff check --fix .` / `ruff format .` / `ruff format --check .`
- `uv run python manage.py spectacular --file openapi.yaml` : régénère `openapi.yaml` (obligatoire après tout changement de routes ou de schémas, la CI vérifie qu'il est à jour)
- `npx markdownlint-cli2 "**/*.md"` : lint markdown, comme la CI
- `docker compose -f docker-compose.prod.yml up -d` : image de production
- Mailpit est démarré par `docker compose up` : les emails de dev se lisent sur <http://localhost:8025>, c'est là qu'on clique le lien de vérification

## Sans Docker (fallback)

- Si et seulement si tu ne peux pas démarrer de conteneur (déjà dans un conteneur, Docker indisponible), ignore les commandes Docker et installe un environnement local
- Utilise uv, c'est uv ou rien : `uv sync`, puis les commandes `uv run` ci-dessus
- Dans tous les autres cas, passe par docker compose

## Migrations

- Tout changement de modèle Django exige une migration dans la même PR (`makemigrations` puis relecture du fichier, `sqlmigrate` pour lire le SQL) ; la CI échoue sur un modèle sans migration
- Reformate les migrations générées avec `uv run ruff format .` : Django les écrit avec son propre style
- Ne modifie jamais une migration déjà mergée : crée-en une nouvelle
- Le `User` custom est lié au schéma dès la migration initiale : changer `AUTH_USER_MODEL` après coup impose de repartir de zéro

## Documentation du schéma

- Le diagramme ER est une image générée par `graph_models` et committée (`docs/model/schema.png`), affichée dans le README
- La CI vérifie la non-dérive sur le `.dot` committé à côté (`docs/model/schema.dot`), pas sur l'image : deux versions de graphviz rendent le même schéma différemment, alors que le `.dot` est du texte stable. Une seule ligne de son en-tête varie d'une génération à l'autre, `// Created:`, et elle est retirée à la génération — le fichier committé n'en porte pas
- Régénère **les deux** après tout changement de modèle, dans la PR qui porte la migration : la CI échoue sur le `.dot`, mais rien ne surveille l'image, qui peut donc rester en retard sur lui
- La vérification CI d'`openapi.yaml` n'est pas concernée : ce fichier est déterministe et reste vérifié
- Les `help_text` ne sont **pas** affichés par `graph_models` : les descriptions de colonnes servent encore l'admin et l'OpenAPI générée, mais elles n'ont plus de garant visuel dans le schéma. Continue à en écrire une par colonne, en sachant que rien ne le rappellera
- Les descriptions peuvent contenir des virgules : la contrainte venait de paracelsus, elle est tombée

## Style de code

- Privilégie la simplicité et la lisibilité
- Pas de sur-ingénierie : résous le problème actuel, pas les problèmes hypothétiques
- Préfère les modifications minimales et ciblées
- Pas de commentaires : utilise des noms de variables/méthodes explicites et des messages de commit clairs à la place
- Ces principes s'appliquent à tout code produit : applicatif, scripts, configuration, infrastructure
- En markdown, pas de retour à la ligne dur — une ligne par paragraphe

## Git

- Ne committe jamais sans demande explicite
- Ne committe jamais des fichiers que tu n'as ni écrits ni modifiés : c'est peut-être le travail d'un autre agent
- Titre de commit en anglais, au présent impératif ; le corps doit être assez explicite et détaillé pour comprendre le changement sans contexte
- Préfère les commits atomiques (un changement logique = un commit)
- Résous les conflits de PR par rebase sur `main`, jamais en mergeant `main` dans la branche : le repo merge en rebase-merge, qui jette les commits de merge et leurs résolutions (« Unable to merge » sinon)
- Quand le dev est fini, `git fetch origin main` et vérifie que la branche est rebasable sans conflit sur `main` ; si `main` a avancé, rebase et re-pousse avant de considérer la PR prête
- Ouvre toujours une PR une fois le code terminé, sans attendre qu'on te le demande
- La description commence par `Closes #N` : mentionner l'issue autrement la référence sans la fermer, et il reste alors un ticket ouvert sur du travail livré
- PR empilées : avant de merger celle qui sert de base à une autre, rebascule d'abord l'enfant sur `main`. GitHub refuse de supprimer une branche qui est la base d'une PR ouverte, et tant qu'il ne la supprime pas il ne rebascule pas l'enfant non plus — qui se retrouve avec une base morte. Le rebase-merge aggrave le tout en réécrivant les SHA : le diff de l'enfant devient alors l'inverse du travail déjà mergé
- Rebasculer l'enfant ne suffit pas : une fois le parent mergé, **rebase aussi la branche enfant sur `main`**. Elle porte encore les commits du parent d'avant la réécriture des SHA, que `main` ne reconnaît plus, et la PR reste `dirty` avec un diff fantôme même si sa base est correcte

## Tests

- Lance uniquement les tests pertinents, pas toute la suite
- Lance toute la suite (`uv run pytest`) une fois que tu penses avoir fini
- Utilise la TDD quand c'est pertinent, demande si nécessaire
- Tout bug que tu parviens à reproduire devient un cas de test **avant** d'être corrigé : le test doit d'abord échouer sur le bug, puis passer avec le correctif, et il reste dans la suite. C'est à la fois le garde-fou anti-régression et la documentation du bug — une reproduction dans un script jetable ne laisse aucune trace
- Le nom du test décrit le comportement attendu, pas le numéro de l'issue : c'est lui qu'on lira le jour où il repassera au rouge
- Django crée une base de test isolée : ne touche jamais à la base de dev dans les tests
- Couverture de 100 % exigée sur le code applicatif (pytest-cov, seuil dans `pyproject.toml`) : `uv run pytest` échoue en dessous, en local comme en CI

## Sécurité

- Ne committe jamais de secrets, tokens, ou mots de passe
- Vérifie les fichiers .env, credentials, clés privées avant tout staging

## Workflow

- Quand je te demande de traiter une issue ou une PR, souscris par défaut aux notifications de la PR concernée (`subscribe_pr_activity`) et suis-la jusqu'au merge
- Avant de démarrer le traitement d'une issue, si tu as des objections sur ce qui est demandé, commente-les sur l'issue et attends une réponse avant de commencer
- Lis toujours le code existant avant de proposer des modifications
- Utilise les outils dédiés (Read, Edit, Grep, Glob) plutôt que bash quand possible
- Après tout changement de code : `uv run ruff check .`, `uv run ruff format .` puis `uv run pytest`
