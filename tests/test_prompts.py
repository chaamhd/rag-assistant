from types import SimpleNamespace

from app.prompts import SYSTEM_PROMPT, build_messages


def fake_result(n: int):
    return SimpleNamespace(
        source=f"doc{n}.md", title=f"Title {n}", section=f"Section {n}", text=f"Text {n}"
    )


def test_messages_structure():
    messages = build_messages("my question?", [fake_result(1), fake_result(2)])
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1]["role"] == "user"
    assert "Question: my question?" in messages[1]["content"]


def test_passages_are_numbered_from_one():
    content = build_messages("q", [fake_result(1), fake_result(2)])[1]["content"]
    assert "[1] doc1.md" in content
    assert "[2] doc2.md" in content
    assert "[0]" not in content