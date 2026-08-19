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

- Python 3.12 (épinglé dans `.python-version`), Django 6.1, django-ninja pour l'API (Pydantic, OpenAPI générée)
- ORM et migrations Django (SQLite par défaut, `DATABASE_URL` lu par dj-database-url), migrations appliquées par l'entrypoint Docker, jamais par le code applicatif
- django-extensions pour `shell_plus`, `runserver_plus` et `reset_db`
- Dépendances gérées par uv (`uv sync`, groupe `dev` dans `pyproject.toml`, lock dans `uv.lock`)
- pytest-django pour les tests, ruff pour lint et format
- Docker + docker compose, devcontainer basé sur le service `api`
- Deux Dockerfiles (pratiques uv officielles) : `Dockerfile` dev (uv, deps dev, `runserver`, monté sur `/app`), `Dockerfile.prod` multistage (image finale sans uv ni pip, non-root, gunicorn, base dans le volume `/data`)

## Structure

- `manage.py` : point d'entrée Django, équivalent de `rails`/`rake`
- `tout_pris/settings.py` : configuration, lue depuis l'environnement
- `tout_pris/urls.py` : URLconf racine, admin sur `/admin/` et API ninja sur `/api/`
- `tout_pris/api.py` : instance `NinjaAPI` et endpoint `/health`
- `tout_pris/mail.py` : envoi transactionnel via Brevo
- `accounts/` : app du `User` custom, référencé par `AUTH_USER_MODEL` dès la migration initiale
- `tests/` : suite pytest-django, une base de test isolée fournie par Django
- `docs/api/` : conventions de l'API — codes de retour, cloisonnement par foyer, schémas, collections
- `docs/model/` : besoin fonctionnel derrière le modèle de données, indépendant du framework
- Une app Django par domaine, comme des engines Rails

## Commandes

- Pas de Makefile ni de remplaçant : le README liste toutes les commandes, c'est la référence unique
- `docker compose build` / `up -d` / `down` / `logs -f api` : cycle de vie du serveur (port 8000)
- `docker compose exec api <commande>` : même commande dans le conteneur
- `uv run python manage.py runserver 0.0.0.0:8000` : serveur de dev
- `uv run python manage.py migrate` / `makemigrations` / `showmigrations` / `sqlmigrate` : migrations
- `uv run python manage.py reset_db` puis `migrate` : reconstruit la base de dev (jamais versionnée, `*.db` ignoré)
- `uv run python manage.py shell_plus` / `createsuperuser` / `check`
- `uv run pytest` : tests, échec sous 100 % de couverture
- `uv run ruff check .` / `ruff check --fix .` / `ruff format .` / `ruff format --check .`
- `uv run python manage.py export_openapi_schema --api tout_pris.api.api --output openapi.json --indent 2` : régénère `openapi.json` (obligatoire après tout changement de routes ou de schémas, la CI vérifie qu'il est à jour)
- `npx markdownlint-cli2 "**/*.md"` : lint markdown, comme la CI
- `docker compose -f docker-compose.prod.yml up -d` : image de production

## Sans Docker (fallback)

- Si et seulement si tu ne peux pas démarrer de conteneur (déjà dans un conteneur, Docker indisponible), ignore les commandes Docker et installe un environnement local
- Utilise uv, c'est uv ou rien : `uv sync`, puis les commandes `uv run` ci-dessus
- Dans tous les autres cas, passe par docker compose

## Migrations

- Tout changement de modèle Django exige une migration dans la même PR (`makemigrations` puis relecture du fichier, `sqlmigrate` pour lire le SQL) ; la CI échoue sur un modèle sans migration
- Reformate les migrations générées avec `uv run ruff format .` : Django les écrit avec son propre style
- Ne modifie jamais une migration déjà mergée : crée-en une nouvelle
- Le `User` custom est lié au schéma dès la migration initiale : changer `AUTH_USER_MODEL` après coup impose de repartir de zéro

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
- Ouvre toujours une PR une fois le code terminé, sans attendre qu'on te le demande ; elle référence l'issue traitée

## Tests

- Lance uniquement les tests pertinents, pas toute la suite
- Lance toute la suite (`uv run pytest`) une fois que tu penses avoir fini
- Utilise la TDD quand c'est pertinent, demande si nécessaire
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
