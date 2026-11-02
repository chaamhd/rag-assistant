import json
import logging
import time

from app.logging_config import JsonFormatter
from app.main import traced


def test_json_formatter_keeps_extra_fields():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
    record.duration_ms = 12
    data = json.loads(JsonFormatter().format(record))
    assert data["message"] == "hello"
    assert data["level"] == "INFO"
    assert data["duration_ms"] == 12


def test_traced_writes_one_summary_line(caplog):
    events = iter([
        ("sources", {}),
        ("token", {"text": "Hel"}),
        ("token", {"text": "lo"}),
        ("done", {}),
    ])
    with caplog.at_level(logging.INFO, logger="app.main"):
        out = list(traced(
            events, request_id="abc", started=time.perf_counter(),
            search_ms=5, question_chars=10, sources=["a#1"],
        ))
    assert [name for name, _ in out] == ["sources", "token", "token", "done"]
    record = caplog.records[-1]
    assert record.request_id == "abc"
    assert record.status == "ok"
    assert record.stream_chunks == 2
    assert record.answer_chars == 5
    assert record.passages == 1