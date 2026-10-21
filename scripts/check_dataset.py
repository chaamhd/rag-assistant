from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from scripts.dataset import DatasetError, load_dataset


def load_corpus(path: Path) -> dict[str, str]:
    """Texte de chaque page du corpus, reconstitué à partir de ses passages."""
    pages: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            pages.setdefault(chunk["source"], []).append(chunk["text"])
    return {source: "\n".join(texts) for source, texts in pages.items()}


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage : python -m scripts.check_dataset <questions.yaml> <chunks.jsonl>")
        return 2

    try:
        questions = load_dataset(Path(sys.argv[1]))
    except DatasetError as exc:
        print(f"Format invalide :\n{exc}")
        return 1

    pages = load_corpus(Path(sys.argv[2]))
    whole_corpus = "\n".join(pages.values()).lower()

    problems = []
    for q in questions:
        if q.should_refuse:
            for term in q.absent_terms:
                if term.lower() in whole_corpus:
                    problems.append(
                        f"{q.id} : « {term} » est dans le corpus, "
                        "la question n'est donc pas hors sujet"
                    )
            continue
        for source in q.expected_sources:
            if source not in pages:
                problems.append(f"{q.id} : source inconnue « {source} »")
        text = "\n".join(pages[s] for s in q.expected_sources if s in pages)
        for term in q.expected_terms:
            if term not in text:
                problems.append(f"{q.id} : « {term} » introuvable dans les sources attendues")

    print(f"{len(questions)} questions valides sur le format")
    for category, count in sorted(Counter(q.category for q in questions).items()):
        print(f"  {category:<14} {count}")

    if problems:
        print(f"\n{len(problems)} problème(s) de vérité terrain :")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nVérité terrain cohérente avec le corpus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())