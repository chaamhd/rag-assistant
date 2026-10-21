import sys
from pathlib import Path

from app.llm import LLMError, generate
from app.prompts import build_messages
from app.search import search


def read_questions(path: Path) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage : python -m scripts.try_questions <fichier de questions>")

    for number, question in enumerate(read_questions(Path(sys.argv[1])), start=1):
        results = search(question)
        print("=" * 72)
        print(f"Q{number}. {question}")
        print(
            "Sources : "
            + " | ".join(f"{r.source} ({r.score:.2f})" for r in results[:3])
        )
        print("-" * 72)
        try:
            print(generate(build_messages(question, results)).strip())
        except LLMError as exc:
            print(f"[ERREUR MODÈLE] {exc}")
        print()


if __name__ == "__main__":
    main()