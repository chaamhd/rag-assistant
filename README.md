# Assistant RAG sur la documentation de uv

Assistant de questions-réponses qui répond à partir de la documentation de
[uv](https://github.com/astral-sh/uv), en citant ses sources. Il fonctionne
entièrement en local et gratuitement (embeddings et modèle de langage locaux).

> Statut : en cours de développement .

## Fonctionnalités

- Recherche sémantique dans 634 passages (PostgreSQL + pgvector)
- Réponses en streaming (SSE) ; les passages consultés et leurs scores sont
  envoyés séparément de la réponse
- Refus de répondre quand la documentation ne contient pas l'information
- Erreurs propres quand la base ou le modèle est indisponible

## Lancer le projet

Prérequis : Docker Desktop, Ollama, Python 3.9 ou plus.

```bash
cp .env.example .env            # puis changer POSTGRES_PASSWORD
ollama pull qwen2.5:7b
ollama create qwen2.5-rag -f ollama/Modelfile
docker compose up -d --build

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

./scripts/fetch_corpus.sh       # récupère la documentation de uv
python -m scripts.build_chunks  # nettoie et découpe en passages
python -m scripts.ingest        # calcule les embeddings et remplit la base
```

Poser une question :

```bash
curl -N -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How can I pin the Python version of a project?"}'
```

## Fonctionnement

Question → embedding → recherche des 5 passages les plus proches (pgvector)
→ prompt avec passages numérotés → modèle de langage (Ollama) → réponse en
streaming. Le schéma d'architecture sera ajouté à la fin du projet.

Les choix techniques et leurs compromis sont dans [docs/decisions.md](docs/decisions.md).

## Limites connues

- La recherche en français est fragile : le modèle d'embeddings est anglais.
- Le petit modèle local invente parfois des exemples, groupe ses citations en
  fin de réponse, et a refusé à tort 1 question sur 10 lors d'un premier essai
  manuel. Deux appels identiques peuvent donner des réponses différentes.

## Corpus

Documentation de [uv](https://github.com/astral-sh/uv), récupérée par script.
Le commit exact est dans `data/SOURCE.txt`. Le projet uv est distribué sous
licence Apache-2.0 ou MIT, au choix. Le corpus n'est pas redistribué dans ce
dépôt : chacun le télécharge depuis la source avec `scripts/fetch_corpus.sh`.