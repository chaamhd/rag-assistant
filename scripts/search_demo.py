import sys

from app.search import search

DEFAULT_QUESTION = "How do I install a specific Python version?"


def main() -> None:
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    print(f"Question : {question}\n")

    for r in search(question):
        preview = " ".join(r.text.split())[:200]
        print(f"[{r.score:.3f}] {r.source} | {r.section}\n    {preview}...\n")


if __name__ == "__main__":
    main()