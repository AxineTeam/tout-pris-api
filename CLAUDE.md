# tout-pris-back

Backend FastAPI du projet Tout Pris. Soit extrêmement concis.

## Langue

- Réponds en français sauf si le contexte est clairement anglophone
- Les messages de commit, noms de branches, code et commentaires dans le code restent en anglais

## Communication

- Soit brutalement honnête : si tu penses que j'ai tort dis-le moi !
- Pas de louanges inutiles ni de remplissage, réponses directes, pas de préambules
- Quand je pose une question réponds, ne fais pas de modifications, sauf si je l'ai explicitement demandé !
- Si tu rencontres une erreur que tu parviens à corriger sans comprendre pourquoi, documente-le !

## Stack

- Python 3.12 (épinglé dans `.python-version`), FastAPI, SQLAlchemy 2.0 (SQLite par défaut, `DATABASE_URL` pour changer)
- Alembic pour les migrations de schéma, exécutées automatiquement au démarrage de l'app (lifespan)
- Dépendances gérées par uv (`uv sync`, groupe `dev` dans `pyproject.toml`, lock dans `uv.lock`)
- pytest + httpx pour les tests, ruff pour lint et format
- polyfactory sur les schémas Pydantic pour les factories (seed et tests) — choix aligné avec l'arrivée prévue de PydanticAI, pas de factory_boy
- Docker + docker compose, devcontainer basé sur le service `api`
- Deux Dockerfiles (pratiques uv officielles) : `Dockerfile` dev (uv, deps dev, reload, monté sur `/app`), `Dockerfile.prod` multistage (image finale sans uv ni pip, non-root, base dans le volume `/data`)

## Structure

- `app/main.py` : création de l'app, lifespan (migrations Alembic), routes
- `app/database.py` : engine, session, `Base`, dépendance `get_db`
- `app/models.py` : modèles SQLAlchemy (table `stufflist`)
- `app/schemas.py` : schémas Pydantic
- `app/factories.py` : factories polyfactory construites sur les schémas Pydantic
- `app/seed.py` : seed reproductible de la base de dev via les factories
- `app/routers/` : un fichier par ressource
- `tests/` : fixtures dans `conftest.py` (client avec SQLite in-memory)
- `alembic/` : migrations (`env.py`, `versions/`), config dans `alembic.ini`

## Commandes

- `make up` / `make down` : démarre/arrête le serveur (docker compose, port 8000)
- `make build` : build l'image Docker
- `make test` : pytest
- `make lint` / `make fmt` : ruff check+format (vérification / correction)
- `make openapi` : régénère `openapi.json` (obligatoire après tout changement de routes ou de schémas, la CI vérifie qu'il est à jour)
- `make erd` : régénère le diagramme ER du README (obligatoire après tout changement de modèle, la CI vérifie qu'il est à jour)
- `make migration m="description"` : génère une migration Alembic (autogenerate), relis toujours le fichier généré
- `make migrate` : applique les migrations sans démarrer le serveur
- `make db-init` / `make db-seed` / `make db-reset` / `make db-drop` : cycle de vie de la base de dev (équivalents `rails db:*`)
- La base n'est jamais versionnée dans git (`*.db` et sidecars WAL `*.db-*` ignorés) : une base de dev se reconstruit avec `make db-reset`

## Sans Docker (fallback)

- Si et seulement si tu ne peux pas démarrer de conteneur (déjà dans un conteneur, Docker indisponible), ignore les cibles Docker du Makefile et installe un environnement local
- Utilise uv, c'est uv ou rien : `uv sync`, puis `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`, `uv run uvicorn app.main:app --reload`
- Dans tous les autres cas, passe par le Makefile

## Documentation du schéma

- Le diagramme ER du README est généré par paracelsus depuis les métadonnées SQLAlchemy : régénère-le avec `make erd` après tout changement de modèle, la CI échoue s'il dérive
- Toute colonne doit porter son `comment=` dans `mapped_column` : c'est la source unique des descriptions, reprise telle quelle dans le diagramme
- Une relation n'a pas de commentaire propre : documente-la sur la colonne de clé étrangère (paracelsus étiquette la flèche avec le nom de la FK)
- Un `__table_args__ = {"comment": ...}` documente la table dans les métadonnées, mais paracelsus ne l'affiche pas dans le diagramme
- Sur SQLite les commentaires ne sont pas persistés : `alembic check` ne les voit pas et un changement de `comment` seul ne génère donc pas de migration (ce serait le cas sur Postgres)
- La prose qui dépasse le schéma (sémantique métier des relations) va dans le README autour du diagramme, jamais dans la zone générée entre les marqueurs

## Migrations

- Tout changement de modèle SQLAlchemy exige une migration Alembic dans la même PR (`make migration` puis relecture du fichier)
- Ne modifie jamais une migration déjà mergée : crée-en une nouvelle
- Chaque migration doit avoir un `downgrade` fonctionnel

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

## Tests

- Lance uniquement les tests pertinents, pas toute la suite
- Lance toute la suite (`make test`) une fois que tu penses avoir fini
- Utilise la TDD quand c'est pertinent, demande si nécessaire
- Les tests utilisent une SQLite in-memory via l'override de `get_db` : ne touche jamais à la vraie base dans les tests
- Couverture de 100 % exigée sur `app/` (pytest-cov, seuil dans `pyproject.toml`) : `make test` échoue en dessous, en local comme en CI

## Sécurité

- Ne committe jamais de secrets, tokens, ou mots de passe
- Vérifie les fichiers .env, credentials, clés privées avant tout staging

## Workflow

- Quand je te demande de traiter une issue ou une PR, souscris par défaut aux notifications de la PR concernée (`subscribe_pr_activity`) et suis-la jusqu'au merge
- Avant de démarrer le traitement d'une issue, si tu as des objections sur ce qui est demandé, commente-les sur l'issue et attends une réponse avant de commencer
- Lis toujours le code existant avant de proposer des modifications
- Utilise les outils dédiés (Read, Edit, Grep, Glob) plutôt que bash quand possible
- Après tout changement de code : `make lint` puis `make test`
