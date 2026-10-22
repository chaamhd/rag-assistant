from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from scripts.dataset import load_dataset
from scripts.eval_metrics import normalize

OUTCOMES = ("correcte", "refus à tort", "termes absents")


def classify(outcome: dict) -> str:
    if outcome["correct"]:
        return "correcte"
    return "refus à tort" if outcome["refused"] else "termes absents"


def missing_terms(answer: str, terms: list[str]) -> list[str]:
    text = normalize(answer)
    return [term for term in terms if normalize(term) not in text]


def excerpt(answer: str, size: int = 150) -> str:
    return " ".join(answer.split())[:size]


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage : python -m scripts.diagnose <resultats.json> <questions.yaml>")
        return 2

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    expected_terms = {q.id: q.expected_terms for q in load_dataset(Path(sys.argv[2]))}

    table: Counter = Counter()
    with_page, without_page = [], []
    for q in data["questions"]:
        if q["should_refuse"]:
            continue
        found = q["rank"] is not None
        classes = [classify(o) for o in q["runs"]]
        for outcome_class in classes:
            table[(found, outcome_class)] += 1
        failing = [(o, c) for o, c in zip(q["runs"], classes) if c != "correcte"]
        if failing:
            (with_page if found else without_page).append((q, failing))

    print("RÉSULTAT DES ESSAIS SELON QUE LA BONNE PAGE ÉTAIT TROUVÉE OU NON")
    print(f"  {'':<18}{'page trouvée':>14}{'page absente':>14}")
    for name in OUTCOMES:
        print(f"  {name:<18}{table[(True, name)]:>14}{table[(False, name)]:>14}")

    print("\nÉCHECS ALORS QUE LA BONNE PAGE ÉTAIT DANS LES PASSAGES")
    for q, failing in with_page:
        print(f"  - {q['id']} [{q['category']}] : {len(failing)}/{len(q['runs'])} essais en échec")
        answer, kind = failing[0]
        if kind == "termes absents":
            print(f"      termes absents : {missing_terms(answer['answer'], expected_terms[q['id']])}")
        else:
            print("      le modèle a refusé de répondre")
        print(f"      {excerpt(answer['answer'])}")

    print("\nÉCHECS ALORS QUE LA BONNE PAGE N'ÉTAIT PAS DANS LES PASSAGES")
    for q, failing in without_page:
        pages = [r["source"] for r in q["retrieved"][:3]]
        print(f"  - {q['id']} [{q['category']}] : {len(failing)}/{len(q['runs'])} essais en échec")
        print(f"      pages remontées : {pages}")
    return 0


if __name__ == "__main__":
    sys.exit(main())