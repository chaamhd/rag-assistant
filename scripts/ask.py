import sys
import time

from app.llm import LLMError, stream_answer
from app.prompts import build_messages
from app.search import search

DEFAULT_QUESTION = "How can I pin the Python version of a project?"


def main() -> None:
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    results = search(question)
    messages = build_messages(question, results)

    print(f"Question : {question}\n")
    start = time.perf_counter()
    first = None
    try:
        for piece in stream_answer(messages):
            if first is None:
                first = time.perf_counter() - start
            print(piece, end="", flush=True)
    except LLMError as exc:
        print(f"\nErreur du modèle : {exc}")
        sys.exit(1)
    total = time.perf_counter() - start

    print("\n\nSources :")
    for number, r in enumerate(results, start=1):
        print(f"  [{number}] {r.source} — {r.section} (score {r.score:.3f})")
    print(f"\nPremier mot après {first or 0:.1f} s, total {total:.1f} s")


if __name__ == "__main__":
    main()