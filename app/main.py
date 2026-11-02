import json
import logging
import time
import uuid
from collections.abc import Iterator

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.logging_config import request_id_var, setup_logging
from app.prompts import PROMPT_ID
from app.rag import Event, answer_events
from app.schemas import AskRequest
from app.search import search

setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Assistant")
logger.info("API started")


def _ms(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


def _config() -> dict:
    """Réglages qui influencent la qualité et la durée d'une réponse."""
    return {
        "search_mode": settings.search_mode,
        "search_top_k": settings.search_top_k,
        "rerank_enabled": settings.rerank_enabled,
        "rerank_candidates": settings.rerank_candidates,
        "embedding_model": settings.embedding_model,
        "rerank_model": settings.rerank_model,
        "llm_model": settings.llm_model,
        "prompt_id": PROMPT_ID,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


def to_sse(events: Iterator[Event]) -> Iterator[str]:
    """Met chaque événement au format SSE. Le JSON tient sur une seule ligne."""
    for name, data in events:
        yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def traced(
    events: Iterator[Event],
    request_id: str,
    started: float,
    search_ms: int,
    question_chars: int,
    sources: list[str],
) -> Iterator[Event]:
    """Laisse passer les événements, puis écrit une ligne de bilan."""
    llm_started = time.perf_counter()
    first_token_ms = None
    chunks = 0
    chars = 0
    status = "interrupted"  # reste ainsi si le client coupe avant la fin
    try:
        for name, data in events:
            if name == "token":
                if first_token_ms is None:
                    first_token_ms = _ms(llm_started)
                chunks += 1
                chars += len(data["text"])
            elif name == "done":
                status = "ok"
            elif name == "error":
                status = "llm_error"
            yield name, data
    finally:
        logger.info(
            "question answered",
            extra={
                "request_id": request_id,
                "question_chars": question_chars,
                "search_ms": search_ms,
                "passages": len(sources),
                "sources": sources,
                "first_token_ms": first_token_ms,
                "llm_ms": _ms(llm_started),
                "total_ms": _ms(started),
                "stream_chunks": chunks,
                "answer_chars": chars,
                "status": status,
                "config": _config(),
            },
        )


@app.post("/ask")
def ask(request: AskRequest) -> StreamingResponse:
    request_id = uuid.uuid4().hex[:12]
    request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        results = search(request.question)
    except psycopg.Error:
        logger.exception("Recherche impossible : la base de données ne répond pas")
        raise HTTPException(
            status_code=503, detail="The search service is unavailable."
        )
    events = traced(
        answer_events(request.question, results),
        request_id=request_id,
        started=started,
        search_ms=_ms(started),
        question_chars=len(request.question),
        sources=[r.id for r in results],
    )
    return StreamingResponse(
        to_sse(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )