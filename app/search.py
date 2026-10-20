from dataclasses import dataclass

from app.db import connect
from app.embeddings import embed_query

DEFAULT_TOP_K = 5

SEARCH_SQL = """
SELECT id, source, title, section, text, 1 - (embedding <=> %(q)s) AS score
FROM chunks
ORDER BY embedding <=> %(q)s
LIMIT %(k)s
"""


@dataclass(frozen=True)
class SearchResult:
    id: str
    source: str
    title: str
    section: str
    text: str
    score: float


def search(question: str, k: int = DEFAULT_TOP_K) -> list[SearchResult]:
    """Retourne les k passages les plus proches de la question, du meilleur au moins bon."""
    query_vector = embed_query(question)
    with connect() as conn:
        rows = conn.execute(SEARCH_SQL, {"q": query_vector, "k": k}).fetchall()
    return [SearchResult(*row) for row in rows]