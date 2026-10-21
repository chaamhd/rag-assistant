from types import SimpleNamespace

import app.rag as rag
from app.llm import LLMError


def fake_result():
    return SimpleNamespace(
        id="a.md#0", source="a.md", title="T", section="S", text="x", score=0.9
    )


def test_events_order(monkeypatch):
    monkeypatch.setattr(rag, "stream_answer", lambda messages: iter(["Hel", "lo"]))
    events = list(rag.answer_events("q", [fake_result()]))
    assert [name for name, _ in events] == ["sources", "token", "token", "done"]
    assert events[1][1] == {"text": "Hel"}


def test_llm_failure_yields_error_without_details(monkeypatch):
    def broken(messages):
        raise LLMError("secret detail")
        yield  

    monkeypatch.setattr(rag, "stream_answer", broken)
    events = list(rag.answer_events("q", [fake_result()]))
    assert [name for name, _ in events] == ["sources", "error"]
    assert "secret detail" not in str(events[-1][1])