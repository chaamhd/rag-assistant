from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import psycopg

from app.config import settings
from app.db import connect
from app.embeddings import embed_query
from app.rerank import rerank

COLUMNS = "id, source, title, section, text, 1 - (embedding <=> %(q)s) AS score"

VECTOR_SQL = f"""
SELECT {COLUMNS}
FROM chunks
ORDER BY embedding <=> %(q)s
LIMIT %(n)s
"""

TEXT_SQL = f"""
SELECT {COLUMNS}
FROM chunks, websearch_to_tsquery(%(cfg)s::regconfig, %(t)s) AS tsq
WHERE tsv @@ tsq
ORDER BY ts_rank_cd(tsv, tsq) DESC
LIMIT %(n)s
"""

WORD = re.compile(r"\w+")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    id: str
    source: str
    title: str
    section: str
    text: str
    score: float  # similarité cosinus, même en mode hybride


def to_or_query(question: str) -> str:
    """Mots de la question reliés par « or » (syntaxe de websearch_to_tsquery).

    Un seul mot en commun suffit à remonter un passage ; le classement
    (ts_rank_cd) favorise ensuite ceux qui en contiennent le plus.
    """
    words = [w for w in WORD.findall(question) if w.lower() != "or"]
    return " or ".join(words)


def rrf_fuse(rankings: list[list[SearchResult]], rrf_k: int) -> list[SearchResult]:
    """Fusionne plusieurs classements (Reciprocal Rank Fusion)."""
    scores: dict[str, float] = {}
    by_id: dict[str, SearchResult] = {}
    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            by_id.setdefault(result.id, result)
            scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (rrf_k + rank)
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [by_id[i] for i in ordered]


def _fetch(conn: psycopg.Connection, sql: str, params: dict) -> list[SearchResult]:
    return [SearchResult(*row) for row in conn.execute(sql, params).fetchall()]


def retrieve(question: str, pool: int) -> list[SearchResult]:
    """Au plus `pool` passages classés (vectoriel seul ou hybride)."""
    query_vector = embed_query(question)
    n = max(pool, settings.search_candidates)
    with connect() as conn:
        vector_hits = _fetch(conn, VECTOR_SQL, {"q": query_vector, "n": n})
        if settings.search_mode == "vector":
            return vector_hits[:pool]
        text_query = to_or_query(question)
        text_hits = (
            _fetch(conn, TEXT_SQL, {
                "q": query_vector, "t": text_query,
                "cfg": settings.fts_language, "n": n,
            })
            if text_query else []
        )
    return rrf_fuse([vector_hits, text_hits], settings.rrf_k)[:pool]


def _ms(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


def search(question: str, k: int | None = None) -> list[SearchResult]:
    """Retourne les k meilleurs passages (k = config par défaut)."""
    limit = settings.search_top_k if k is None else k
    started = time.perf_counter()
    if not settings.rerank_enabled:
        results = retrieve(question, pool=limit)
        logger.info("search done", extra={
            "retrieve_ms": _ms(started), "rerank_ms": 0, "passages": len(results),
        })
        return results
    pool = max(limit, settings.rerank_candidates)
    candidates = retrieve(question, pool=pool)
    reranking_started = time.perf_counter()
    results = rerank(question, candidates)[:limit]
    logger.info("search done", extra={
        "retrieve_ms": round((reranking_started - started) * 1000),
        "rerank_ms": _ms(reranking_started),
        "candidates": len(candidates),
        "passages": len(results),
    })
    return results