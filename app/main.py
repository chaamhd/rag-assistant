import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.rag import Event, answer_events
from app.schemas import AskRequest
from app.search import search

app = FastAPI(title="RAG Assistant")


@app.get("/health")
def health():
    return {"status": "ok"}

def to_sse(events: Iterator[Event]) -> Iterator[str]:
    """Met chaque événement au format SSE. Le JSON tient sur une seule ligne."""
    for name, data in events:
        yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/ask")
def ask(request: AskRequest) -> StreamingResponse:
    results = search(request.question)
    return StreamingResponse(
        to_sse(answer_events(request.question, results)),
        media_type="text/event-stream",
        # no-cache et X-Accel-Buffering évitent qu'un proxy retienne le flux avant de l'envoyer
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )