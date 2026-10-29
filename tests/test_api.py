import json
from types import SimpleNamespace

import psycopg
import pytest
from fastapi.testclient import TestClient

import app.main as main
import app.rag as rag
from app.config import settings
from app.llm import LLMError


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


def fake_result():
    return SimpleNamespace(
        id="a.md#0", source="a.md", title="T", section="S", text="x", score=0.9
    )


def parse_sse(body: str) -> list[tuple[str, dict]]:
    """Découpe un flux SSE en (nom de l'événement, données)."""
    events = []
    for block in body.strip().split("\n\n"):
        name_line, data_line = block.split("\n", 1)
        events.append(
            (
                name_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return events


def use_fake_search_and_model(monkeypatch, pieces=("ok",)):
    monkeypatch.setattr(main, "search", lambda question: [fake_result()])
    monkeypatch.setattr(rag, "stream_answer", lambda messages: iter(pieces))


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_streams_events_in_order(client, monkeypatch):
    use_fake_search_and_model(monkeypatch, pieces=("Hel", "lo"))
    response = client.post("/ask", json={"question": "How do I pin Python?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["sources", "token", "token", "done"]
    assert events[0][1]["sources"][0]["number"] == 1
    assert events[1][1] == {"text": "Hel"}


def test_blank_question_is_rejected(client, monkeypatch):
    use_fake_search_and_model(monkeypatch)
    assert client.post("/ask", json={"question": "   "}).status_code == 422


def test_question_over_limit_is_rejected(client, monkeypatch):
    use_fake_search_and_model(monkeypatch)
    too_long = "a" * (settings.question_max_chars + 1)
    assert client.post("/ask", json={"question": too_long}).status_code == 422


def test_question_at_limit_is_accepted(client, monkeypatch):
    use_fake_search_and_model(monkeypatch)
    at_limit = "a" * settings.question_max_chars
    assert client.post("/ask", json={"question": at_limit}).status_code == 200


def test_missing_question_is_rejected(client):
    assert client.post("/ask", json={}).status_code == 422


def test_question_is_stripped_before_search(client, monkeypatch):
    received = []

    def fake_search(question):
        received.append(question)
        return [fake_result()]

    monkeypatch.setattr(main, "search", fake_search)
    monkeypatch.setattr(rag, "stream_answer", lambda messages: iter(["ok"]))
    client.post("/ask", json={"question": "  hello  "})
    assert received == ["hello"]


def test_database_failure_returns_503_without_details(client, monkeypatch):
    def broken_search(question):
        raise psycopg.OperationalError("password=secret")

    monkeypatch.setattr(main, "search", broken_search)
    response = client.post("/ask", json={"question": "q"})
    assert response.status_code == 503
    assert "secret" not in response.text


def test_llm_failure_sends_error_event_without_details(client, monkeypatch):
    def broken_stream(messages):
        raise LLMError("secret detail")
        yield

    monkeypatch.setattr(main, "search", lambda question: [fake_result()])
    monkeypatch.setattr(rag, "stream_answer", broken_stream)
    response = client.post("/ask", json={"question": "q"})
    assert response.status_code == 200
    assert [name for name, _ in parse_sse(response.text)] == ["sources", "error"]
    assert "secret" not in response.text