from fastapi.testclient import TestClient

from app import main
from app.ratelimit import RateLimiter

QUESTION = {"question": "How do I install uv?"}


def test_unexpected_search_error_gives_neutral_503(monkeypatch):
    def broken(question):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(main, "search", broken)
    response = TestClient(main.app).post("/ask", json=QUESTION)
    assert response.status_code == 503
    assert "secret detail" not in response.text


def test_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(1, 60))
    monkeypatch.setattr(main, "search", lambda question: [])
    monkeypatch.setattr("app.rag.stream_answer", lambda messages: iter(["ok"]))
    client = TestClient(main.app)
    assert client.post("/ask", json=QUESTION).status_code == 200
    second = client.post("/ask", json=QUESTION)
    assert second.status_code == 429
    assert "Retry-After" in second.headers