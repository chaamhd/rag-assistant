# Décisions d'architecture

| Décision | Pourquoi | Compromis |
|---|---|---|
| PostgreSQL + pgvector | Une seule base pour les passages, les métadonnées et, plus tard, la recherche plein texte ; un service de moins à déployer | Moins de fonctions qu'une base vectorielle dédiée, pour de très gros volumes |
| Embeddings locaux (fastembed, bge-small-en-v1.5) | Gratuit, sans clé d'API, léger (ONNX) | Modèle anglais : la recherche en français est fragile |
| Découpage par sections Markdown (environ 1 500 caractères, chevauchement de 200) | Un passage garde son sens et sa section ; les blocs de code ne sont jamais coupés | La taille est en caractères, une approximation des tokens |
| Modèle local via Ollama (qwen2.5:7b), API compatible OpenAI | Coût nul ; changer de fournisseur ne demande que trois variables d'environnement | Moins fidèle qu'un gros modèle en ligne |
| Aucune valeur par défaut dans la configuration | Une seule source de vérité (`.env`) ; démarrage refusé si une variable manque | Chaque variable doit être déclarée, y compris en intégration continue |
| Passages envoyés séparément de la réponse (SSE) | Le client décide de les afficher ; pas de « sources » sous un refus | Quatre types d'événements à gérer côté client |
| Prompt strict : passages seulement, citations, refus | Mesurer le RAG et non la mémoire du modèle | Un petit modèle refuse parfois à tort |
| Prompt non modifié avant l'évaluation | Corriger avec des mesures avant/après, pas au ressenti | Défauts connus conservés quelques jours |
| Mesurer la recherche séparément de la génération (`scripts/retrieval_eval.py`, sans modèle de langage) | Une mesure prend quelques secondes au lieu de 30 minutes : chaque levier de recherche (hybride, reranking, taille des passages) se teste isolément | Elle vérifie la présence des termes attendus dans les passages, pas la qualité de la réponse finale : l'évaluation complète reste nécessaire pour conclure |