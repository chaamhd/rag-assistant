from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

from app.llm import LLMError, stream_answer
from app.prompts import build_messages

if TYPE_CHECKING:
    from app.search import SearchResult

logger = logging.getLogger(__name__)

Event = tuple[str, dict]  # (nom de l'événement, données)


def sources_payload(results: list[SearchResult]) -> dict:
    # "number" correspond aux citations [1], [2]... écrites par le modèle
    return {
        "sources": [
            {
                "number": number,
                "id": r.id,
                "source": r.source,
                "section": r.section,
                "score": round(r.score, 4),
            }
            for number, r in enumerate(results, start=1)
        ]
    }


def answer_events(question: str, results: list[SearchResult]) -> Iterator[Event]:
    """Les événements d'une réponse : sources, morceaux de texte, puis fin ou erreur."""
    yield "sources", sources_payload(results)
    try:
        for piece in stream_answer(build_messages(question, results)):
            yield "token", {"text": piece}
    except LLMError:
        # Le détail technique reste dans les logs : il n'est pas renvoyé au client
        logger.exception("Échec de l'appel au modèle de langage")
        yield "error", {"message": "The language model is unavailable."}
        return
    yield "done", {}