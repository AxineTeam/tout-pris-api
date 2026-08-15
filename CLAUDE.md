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

- Python 3.12, FastAPI, SQLAlchemy 2.0 (SQLite par défaut, `DATABASE_URL` pour changer)
- pytest + httpx pour les tests, ruff pour lint et format
- Docker + docker compose, devcontainer basé sur le service `api`

## Structure

- `app/main.py` : création de l'app, lifespan (création des tables), routes
- `app/database.py` : engine, session, `Base`, dépendance `get_db`
- `app/models.py` : modèles SQLAlchemy (table `stufflist`)
- `app/schemas.py` : schémas Pydantic
- `app/routers/` : un fichier par ressource
- `tests/` : fixtures dans `conftest.py` (client avec SQLite in-memory)

## Commandes

- `make up` / `make down` : démarre/arrête le serveur (docker compose, port 8000)
- `make build` : build l'image Docker
- `make test` : pytest
- `make lint` / `make fmt` : ruff check+format (vérification / correction)
- `make install` : installe les dépendances en local (`pip install -e ".[dev]"`)

## Sans Docker (fallback)

- Si et seulement si tu ne peux pas démarrer de conteneur (déjà dans un conteneur, Docker indisponible), ignore les cibles Docker du Makefile et installe un environnement local
- Utilise uv autant que possible : `uv venv --python 3.12 && uv pip install -e ".[dev]"`, puis `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`, `uv run uvicorn app.main:app --reload`
- Sans uv, replie-toi sur : `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`, puis les binaires du venv (`.venv/bin/pytest`, etc.)
- Dans tous les autres cas, passe par le Makefile

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

## Tests

- Lance uniquement les tests pertinents, pas toute la suite
- Lance toute la suite (`make test`) une fois que tu penses avoir fini
- Utilise la TDD quand c'est pertinent, demande si nécessaire
- Les tests utilisent une SQLite in-memory via l'override de `get_db` : ne touche jamais à la vraie base dans les tests

## Sécurité

- Ne committe jamais de secrets, tokens, ou mots de passe
- Vérifie les fichiers .env, credentials, clés privées avant tout staging

## Workflow

- Lis toujours le code existant avant de proposer des modifications
- Utilise les outils dédiés (Read, Edit, Grep, Glob) plutôt que bash quand possible
- Après tout changement de code : `make lint` puis `make test`
