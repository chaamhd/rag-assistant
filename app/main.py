import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import settings
from app.embeddings import warm_up as warm_up_embeddings
from app.logging_config import request_id_var, setup_logging
from app.prompts import PROMPT_ID
from app.rag import Event, answer_events
from app.ratelimit import RateLimiter
from app.rerank import warm_up as warm_up_rerank
from app.schemas import AskRequest
from app.search import search

setup_logging()

logger = logging.getLogger(__name__)

rate_limiter = RateLimiter(
    settings.rate_limit_requests, settings.rate_limit_window_seconds
)


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


def warm_up_models() -> None:
    """Charge les modèles au démarrage plutôt qu'à la première question."""
    started = time.perf_counter()
    try:
        warm_up_embeddings()
        if settings.rerank_enabled:
            warm_up_rerank()
    except Exception:
        logger.exception("Model warm-up failed; they will load on the first question")
        return
    logger.info("Models loaded", extra={"duration_ms": _ms(started)})


@asynccontextmanager
async def lifespan(app: FastAPI):
    warm_up_models()
    logger.info("API started")
    yield


app = FastAPI(title="RAG Assistant", lifespan=lifespan)


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
def ask(request: AskRequest, http_request: Request) -> StreamingResponse:
    request_id = uuid.uuid4().hex[:12]
    request_id_var.set(request_id)
    client = http_request.client.host if http_request.client else "unknown"
    if not rate_limiter.allow(client):
        logger.warning("Rate limit exceeded", extra={"client": client})
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(int(settings.rate_limit_window_seconds))},
        )
    started = time.perf_counter()
    try:
        results = search(request.question)
    except Exception:
        logger.exception("Search failed (database, embeddings or reranking)")
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