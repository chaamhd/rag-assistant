import json
import logging
from collections.abc import Iterator

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.logging_config import setup_logging
from app.rag import Event, answer_events
from app.schemas import AskRequest
from app.search import search

setup_logging()

logger = logging.getLogger(__name__)
app = FastAPI(title="RAG Assistant")
logger.info("API started")


@app.get("/health")
def health():
    return {"status": "ok"}

def to_sse(events: Iterator[Event]) -> Iterator[str]:
    """Met chaque événement au format SSE. Le JSON tient sur une seule ligne."""
    for name, data in events:
        yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/ask")
def ask(request: AskRequest) -> StreamingResponse:
    try:
        results = search(request.question)
    except psycopg.Error:
        logger.exception("Recherche impossible : la base de données ne répond pas")
        raise HTTPException(
            status_code=503, detail="The search service is unavailable."
        )
    return StreamingResponse(
        to_sse(answer_events(request.question, results)),
        media_type="text/event-stream",
        # no-cache et X-Accel-Buffering évitent qu'un proxy retienne le flux avant de l'envoyer
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )