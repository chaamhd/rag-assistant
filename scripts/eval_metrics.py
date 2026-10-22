from __future__ import annotations

import re

MIN_SNIPPET_CHARS = 3  # en dessous, un extrait de code n'a pas de sens à vérifier
REFUSAL_WINDOW_CHARS = 300  # un refus s'exprime dès le début de la réponse

_REFUSAL_PATTERNS = [
    re.compile(
        r"\b(?:documentation|passages?|context)\b[^.\n]{0,40}?"
        r"\b(?:do(?:es)? not|don't|doesn't|cannot|can't)\b[^.\n]{0,20}?"
        r"\b(?:contain|include|provide|mention|cover|address|have|answer)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bno (?:relevant )?information\b", re.IGNORECASE),
    re.compile(
        r"\b(?:documentation|passages?)\b[^.\n]{0,40}?"
        r"\bne (?:contient|contiennent|mentionne|mentionnent|couvre|couvrent"
        r"|fournit|fournissent) pas\b",
        re.IGNORECASE,
    ),
]

_FENCED_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_ANY_FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_CITATION_RE = re.compile(r"\[(\d+)\]")


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def is_refusal(answer: str) -> bool:
    head = answer[:REFUSAL_WINDOW_CHARS]
    return any(pattern.search(head) for pattern in _REFUSAL_PATTERNS)


def extract_citations(answer: str) -> list[int]:
    """Numéros cités dans le texte, en ignorant le code (où [0] est un index, pas une citation)."""
    prose = _INLINE_CODE_RE.sub("", _ANY_FENCED_RE.sub("", answer))
    return [int(n) for n in _CITATION_RE.findall(prose)]


def code_snippets(answer: str) -> list[str]:
    snippets = []
    for block in _FENCED_BLOCK_RE.findall(answer):
        for line in block.splitlines():
            line = re.sub(r"^[$>]\s*", "", line.strip())
            if len(line) >= MIN_SNIPPET_CHARS:
                snippets.append(line)
    for span in _INLINE_CODE_RE.findall(_ANY_FENCED_RE.sub("", answer)):
        span = span.strip()
        if len(span) >= MIN_SNIPPET_CHARS:
            snippets.append(span)
    return snippets


def unsupported_snippets(answer: str, passages_text: str) -> list[str]:
    """Extraits de code de la réponse qui n'apparaissent dans aucun passage fourni."""
    haystack = normalize(passages_text)
    return [s for s in code_snippets(answer) if normalize(s) not in haystack]


def all_terms_present(answer: str, terms: list[str]) -> bool:
    text = normalize(answer)
    return all(normalize(term) in text for term in terms)


def first_rank(sources: list[str], expected: list[str]) -> int | None:
    """Rang (à partir de 1) de la première page attendue parmi les résultats."""
    for rank, source in enumerate(sources, start=1):
        if source in expected:
            return rank
    return None


def score_answer(
    *,
    answer: str,
    should_refuse: bool,
    expected_terms: list[str],
    expected_sources: list[str],
    sources: list[str],
    passages_text: str,
) -> dict:
    refused = is_refusal(answer)
    citations = extract_citations(answer)
    valid = [n for n in citations if 1 <= n <= len(sources)]
    outcome = {
        "answer": answer,
        "refused": refused,
        "citations": citations,
        "invalid_citations": [n for n in citations if n not in valid],
    }

    if should_refuse:
        outcome["correct"] = refused
        outcome["cited_in_refusal"] = refused and bool(citations)
        return outcome

    terms_ok = all_terms_present(answer, expected_terms)
    outcome["terms_ok"] = terms_ok
    outcome["correct"] = (not refused) and terms_ok
    outcome["has_citation"] = bool(valid)
    outcome["cites_expected_source"] = any(
        sources[n - 1] in expected_sources for n in valid
    )
    outcome["unsupported_snippets"] = (
        [] if refused else unsupported_snippets(answer, passages_text)
    )
    return outcome