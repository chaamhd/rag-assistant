# Assistant RAG sur la documentation de uv

Assistant de questions-réponses qui répond à partir de la documentation de
[uv](https://github.com/astral-sh/uv), en citant ses sources. Il fonctionne
entièrement en local et gratuitement (embeddings et modèle de langage locaux).

> Statut : en cours de développement .

## Fonctionnalités

- Recherche sémantique dans 634 passages (PostgreSQL + pgvector), avec reranking des meilleurs candidats
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

Question → embedding → recherche des 20 passages les plus proches (pgvector)
→ reranking (les 6 meilleurs passages sont gardés) → prompt avec passages
numérotés → modèle de langage (Ollama) → réponse en streaming. Le schéma
d'architecture sera ajouté à la fin du projet.

Les choix techniques et leurs compromis sont dans [docs/decisions.md](docs/decisions.md).

## Tests

```bash
pip install pytest
python -m pytest -q
```

Les tests tournent sans base de données ni Ollama : la recherche et le modèle de langage
sont remplacés par de faux composants. Ils couvrent le découpage des passages, le prompt,
les métriques d'évaluation, la fusion des classements, le reranking, les événements de
réponse et l'API HTTP (flux SSE, validation de la question, erreur 503 et événement
d'erreur sans détail technique).

## Journalisation

L'API écrit ses logs sur la sortie standard, **une ligne JSON par message**, ce qui permet de les filtrer et de les analyser avec des outils comme `jq`. Le format est défini dans `app/logging_config.py` (bibliothèque standard uniquement, aucune dépendance en plus).

Le niveau de détail se règle dans `.env` :

```
LOG_LEVEL=INFO
```

Valeurs possibles : `DEBUG`, `INFO`, `WARNING`, `ERROR`. Pour lire les logs de l'API dans Docker :

```bash
docker compose logs api
```

Exemple de ligne :

```json
{"time": "2026-10-30T10:30:12.456+00:00", "level": "INFO", "logger": "app.main", "message": "API started"}
```

Les erreurs ajoutent un champ `exception` avec le détail technique, qui reste dans les logs et n'est jamais renvoyé au client. Les lignes du serveur `uvicorn` (démarrage, requêtes) gardent leur format

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

### Rejouer une partie des questions et comparer

Pour vérifier un changement sans attendre l'évaluation complète, on peut ne rejouer
que certaines questions :

```bash
python -m scripts.evaluate eval/dataset.yaml --runs 3 --category reformulated --output eval/results/reformulated.json
python -m scripts.evaluate eval/dataset.yaml --runs 3 --ids lockfile-reformulated pin-python-fr --output eval/results/test.json
```

Le résumé indique l'origine des échecs : la page attendue est absente des passages ou
n'a pas les termes attendus (problème de recherche), ou elle est présente avec les
termes (problème de génération), ainsi que les réponses à côté (le modèle répond sans
refuser, mais il manque des termes attendus). Chaque fichier de résultats enregistre
la configuration utilisée : mode de recherche, nombre de passages, reranking.

Deux fichiers de résultats se comparent avec :

```bash
python -m scripts.compare_results eval/results/baseline.json eval/results/rerank-k6.json
```

Le script affiche les écarts par indicateur et par catégorie, les questions améliorées
ou dégradées, et signale tout recul. Seules les questions présentes dans les deux
fichiers sont comparées.

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

### Mesure rapide de la recherche

Pour tester la recherche sans attendre l'évaluation complète (environ 30 minutes),
un script mesure seulement la recherche, sans modèle de langage : quelques secondes.

```bash
python -m scripts.retrieval_eval eval/dataset.yaml --ks 5 10 20
```

Pour chaque question avec réponse, il indique si tous les termes attendus figurent
dans les k premiers passages. À k = 5, il retrouve le résultat de
`scripts/context_check.py`.

| k | Termes attendus trouvés | Bonne page trouvée |
|---|---|---|
| 5 | 83 % (29/35) | 83 % (29/35) |
| 10 | 89 % (31/35) | 94 % (33/35) |
| 20 | 97 % (34/35) | 97 % (34/35) |

Pour 34 questions sur 35, la réponse figure dans les 20 premiers passages : la marge
d'amélioration est surtout dans le classement. Les 6 échecs à k = 5 sont des questions
reformulées (4 sur 8) et en français (2 sur 8) ; les guides et les détails sont à 100 %
dès k = 5. À k = 10, l'écart entre les deux colonnes confirme que « bonne page trouvée »
est un critère indulgent.

Détail : `eval/results/retrieval_depart.txt`.

#### Recherche hybride (testée, non retenue)

Test : recherche plein texte PostgreSQL combinée à la recherche vectorielle
(fusion RRF), activable avec `SEARCH_MODE=hybrid`.

| k | Vectoriel seul | Hybride |
|---|---|---|
| 5 | 29/35 | 29/35 |
| 10 | 31/35 | 32/35 |
| 20 | 34/35 | 34/35 |

À k = 5, le score est identique : 3 questions gagnées (reformulées et françaises)
mais 3 perdues, dont une question de détail. Le gain minimal de 3 questions n'est pas
atteint, donc le mode reste `vector`. Détail : `eval/results/retrieval_hybride.txt`.

#### Reranking (retenu)

Test : un modèle de reranking (`Xenova/ms-marco-MiniLM-L-6-v2`) relit 20 candidats
et garde les k meilleurs (`RERANK_ENABLED=true`, `RERANK_CANDIDATES=20`).

| k | Sans reranking | Avec reranking |
|---|---|---|
| 5 | 29/35 | 30/35 |
| 6 | 30/35 | 33/35 |
| 7 | 31/35 | 33/35 |
| 8 | 31/35 | 34/35 |
| 10 | 31/35 | 34/35 |
| 20 | 34/35 | 34/35 |

Le gain n'est que de 1 question à k = 5, mais de 3 à k = 6 : le reranker place les
bons passages juste après la 5e position. Aucune perte sur les guides et les détails.
La recherche prend environ 1 seconde par question. Configuration adoptée : reranking
activé et 6 passages (`SEARCH_TOP_K=6`), validée par l'évaluation complète ci-dessous.
Détail : `eval/results/retrieval_k5-8_vector.txt` et `eval/results/retrieval_k5-8_rerank.txt`.

### Résultats après reranking

Configuration : recherche vectorielle, 20 candidats réordonnés par un cross-encoder,
6 passages envoyés au modèle (`RERANK_ENABLED=true`, `SEARCH_TOP_K=6`). Même jeu de
43 questions, 3 essais chacune. Durée : 13,5 minutes.
Détail : `eval/results/rerank-k6.json`.

| Indicateur | Départ | Reranking + 6 passages |
|---|---|---|
| Réponses correctes | 67 % (70/105) | 86 % (90/105) |
| Refus à tort | 14 % (15/105) | 11 % (12/105) |
| Refus corrects sur les questions sans réponse | 100 % (24/24) | 100 % (24/24) |
| Réponses avec du code absent des passages | 28 % (25/90) | 12 % (11/93) |
| Questions dont le résultat varie d'un essai à l'autre | 1 sur 43 | 0 sur 43 |

| Catégorie (résultat correct) | Départ | Maintenant |
|---|---|---|
| Guides (howto) | 89 % | 89 % |
| Détails | 73 % | 100 % |
| Reformulées | 25 % | 50 % |
| Français | 75 % | 100 % |
| Sujets voisins ou sans rapport | 100 % | 100 % |

Le reranking et le passage de 5 à 6 passages ont été mesurés ensemble : la part de
chacun n'est pas séparée pour la génération. Pour la recherche seule, à 6 passages, les
termes attendus sont présents pour 33 questions sur 35 avec reranking contre 30 sans.
Il reste 15 essais en échec sur 105, surtout sur des questions reformulées (50 %) :
9 viennent de la recherche (la page attendue n'est pas dans les 6 passages, ou sans
les termes attendus) et 6 de la génération (la page est présente, mais le modèle
refuse à tort). Une règle de refus plus attentive dans le prompt n'a rien amélioré :
elle n'est pas retenue.
Demander au modèle de recopier les commandes à l'identique a augmenté le code absent des
passages (12 % → 18 %) et baissé les citations valides (86 % → 69 %) : non retenu.

## Limites connues

- Les questions reformulées restent le point faible (50 % de réponses correctes) : quand
  la question n'emploie pas le vocabulaire de la documentation, la page attendue n'est
  parfois pas dans les 6 passages envoyés au modèle. C'est l'origine de 9 des 15 essais
  en échec sur 105. Dans ce cas le modèle refuse (6 essais) ou répond à côté (3 essais).
- Le petit modèle local refuse encore à tort dans 11 % des essais (12/105). Dans 6 de ces
  échecs, la page attendue était pourtant dans les passages. Deux essais de prompt (règle de
  refus plus attentive, recopie exacte des commandes) n'ont rien amélioré : ils ne sont pas
  retenus.
- 12 % des réponses non refusées contiennent du code absent des passages (11/93). Ces
  extraits sont signalés par l'évaluation et se classent à la main.
- Le reranking et le sixième passage ont été mesurés ensemble : la part de chacun n'est pas
  séparée pour la génération.
- Les réglages ont été choisis et mesurés sur le même jeu de 43 questions : les gains sont à
  confirmer sur de nouvelles questions. Avec 35 questions, une question vaut environ 3 points.
- Pas testés : un autre modèle d'embeddings, la réécriture de la question par le modèle, un
  autre modèle de langage local. Le découpage des passages n'a pas été modifié, les scores ne
  le suggérant pas.
- Le temps de réponse complet n'est pas mesuré : seule la recherche l'est (environ 1 seconde
  par question avec le reranking). Le modèle de reranking se télécharge au premier appel.
- Deux appels identiques peuvent donner des textes différents, mais le résultat (réussite ou
  échec) ne varie pas : 0 question sur 43 dans la dernière évaluation complète.

## Corpus

Documentation de [uv](https://github.com/astral-sh/uv), récupérée par script.
Le commit exact est dans `data/SOURCE.txt`. Le projet uv est distribué sous
licence Apache-2.0 ou MIT, au choix. Le corpus n'est pas redistribué dans ce
dépôt : chacun le télécharge depuis la source avec `scripts/fetch_corpus.sh`.

