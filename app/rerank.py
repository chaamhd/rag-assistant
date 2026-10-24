from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import settings
from app.embeddings import document_text

if TYPE_CHECKING:
    from app.search import SearchResult


@lru_cache(maxsize=1)
def _model() -> TextCrossEncoder:
    """Modèle de reranking, chargé une seule fois."""
    return TextCrossEncoder(model_name=settings.rerank_model)


def rerank(question: str, candidates: list[SearchResult]) -> list[SearchResult]:
    """Remet les candidats dans l'ordre de pertinence donné par le cross-encoder."""
    if not candidates:
        return []
    documents = [document_text(c.title, c.section, c.text) for c in candidates]
    scores = list(_model().rerank(question, documents))
    order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
    return [candidates[i] for i in order]