from scripts.eval_metrics import (
    extract_citations,
    first_rank,
    is_refusal,
    score_answer,
    unsupported_snippets,
)


def test_refusals_are_detected():
    assert is_refusal("The documentation does not contain information about the capital of Australia.")
    assert is_refusal("The provided passages do not contain information on how to configure Kubernetes.")


def test_normal_answer_is_not_a_refusal():
    assert not is_refusal("You can pin the version with `uv python pin`. [2]")


def test_citations_ignore_code():
    answer = "Use `items[1]` then run:\n```python\nx = y[0]\n```\nSee [2][3]."
    assert extract_citations(answer) == [2, 3]


def test_unsupported_snippets():
    passages = "Run uv python pin to create a .python-version file. See pyproject.toml."
    answer = "Run `uv python pin`, not `uv python pin >=3.12`. Unlike `pyproject.tom_tol`."
    assert unsupported_snippets(answer, passages) == [
        "uv python pin >=3.12",
        "pyproject.tom_tol",
    ]


def test_first_rank():
    assert first_rank(["a.md", "b.md", "c.md"], ["c.md", "x.md"]) == 3
    assert first_rank(["a.md"], ["z.md"]) is None


def test_correct_refusal():
    outcome = score_answer(
        answer="The documentation does not contain this.",
        should_refuse=True,
        expected_terms=[],
        expected_sources=[],
        sources=["a.md"],
        passages_text="x",
    )
    assert outcome["correct"] is True


def test_wrong_refusal_is_counted():
    outcome = score_answer(
        answer="The documentation does not contain this.",
        should_refuse=False,
        expected_terms=["uv tool install"],
        expected_sources=["guides/tools.md"],
        sources=["guides/tools.md"],
        passages_text="uv tool install ruff",
    )
    assert outcome["refused"] is True
    assert outcome["correct"] is False