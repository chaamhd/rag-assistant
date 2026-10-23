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

## Évaluation

Jeu de 43 questions (`eval/dataset.yaml`) dont la vérité terrain est validée
contre le corpus : 35 questions avec réponse (guides, détails, reformulations,
français) et 8 sans réponse (sujets voisins ou sans rapport). Chaque question
est posée 3 fois, car le modèle n'est pas déterministe.

```bash
python -m scripts.evaluate eval/dataset.yaml --runs 3 --output eval/results/baseline.json
python -m scripts.diagnose eval/results/baseline.json eval/dataset.yaml
```

Une réponse est « correcte » si le modèle ne refuse pas et si tous les termes
attendus (commandes, options) y figurent.

### Score de départ

Modèle qwen2.5:7b local, recherche vectorielle seule, 5 passages.

| Indicateur | Résultat |
|---|---|
| Bonne page dans les 5 premiers résultats | 83 % (29/35) |
| MRR | 0,64 |
| Réponses correctes | 67 % (70/105 essais) |
| Refus à tort | 14 % (15/105) |
| Refus corrects sur les questions sans réponse | 100 % (24/24) |
| Réponses avec du code absent des passages | 28 % (25/90) |
| Questions dont le résultat varie d'un essai à l'autre | 1 sur 43 |

| Catégorie | Questions | Page trouvée | Résultat correct |
|---|---|---|---|
| Guides (howto) | 9 | 100 % | 89 % |
| Détails | 10 | 100 % | 73 % |
| Reformulées | 8 | 50 % | 25 % |
| Français | 8 | 75 % | 75 % |
| Sujets voisins ou sans rapport | 8 | — | 100 % |

Avec 35 questions, une question vaut environ 3 points : un écart plus petit
n'est pas une amélioration démontrée.

### Diagnostic du score de départ

Les 35 échecs sur les questions avec réponse se répartissent en deux familles.

| Famille | Questions | Essais en échec | Ce qui se passe |
|---|---|---|---|
| Recherche | 6 (reformulées, français) | 18 | La réponse est absente des 5 passages : le modèle refuse (9 essais) ou répond faux avec assurance (9 essais) |
| Génération | 6 (guides, détails, reformulées) | 17 | La réponse est dans les passages : refus à tort (6), réponse à côté (11) |

Quand la réponse est dans les passages, le modèle réussit 80 % du temps (70/87).
Quand elle est absente, il ne réussit jamais (0/18).

Le critère « la bonne page est dans les 5 résultats » surestime la recherche,
car une page contient plusieurs passages. Le critère « les termes attendus
figurent dans les 5 passages » (`scripts/context_check.py`) est plus fiable,
même s'il reste indulgent.

## Limites connues

- La recherche échoue quand la question n'emploie pas le vocabulaire de la
  documentation (reformulations, français traduit) : pour 6 questions sur 35,
  la réponse n'est pas dans les 5 passages envoyés au modèle.
- Le petit modèle local refuse à tort (14 % des essais) ou répond à côté alors
  que la réponse est dans les passages. Il déforme parfois des noms de fichiers
  (`pyproject.toml`).
- Quand la réponse est absente des passages, il répond faux avec assurance dans
  la moitié des cas (9 essais sur 18).
- Deux appels identiques peuvent donner des textes différents, mais le résultat
  (réussite ou échec) varie peu : 1 question sur 43.

## Corpus

Documentation de [uv](https://github.com/astral-sh/uv), récupérée par script.
Le commit exact est dans `data/SOURCE.txt`. Le projet uv est distribué sous
licence Apache-2.0 ou MIT, au choix. Le corpus n'est pas redistribué dans ce
dépôt : chacun le télécharge depuis la source avec `scripts/fetch_corpus.sh`.

