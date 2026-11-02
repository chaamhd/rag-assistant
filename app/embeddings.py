from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from app.config import settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(settings.embedding_model)


def document_text(title: str, section: str, text: str) -> str:
    """Texte réellement vectorisé : le contexte (titre > section) précède le passage."""
    header = " > ".join(part for part in (title, section) if part)
    return f"{header}\n\n{text}"


def embed_documents(texts: list[str], batch_size: int = 64) -> list[np.ndarray]:
    return list(_model().embed(texts, batch_size=batch_size))


def embed_query(question: str) -> np.ndarray:
    return next(iter(_model().query_embed(question)))


def warm_up() -> None:
    """Charge le modèle d'embeddings maintenant plutôt qu'à la première question."""
    _model()