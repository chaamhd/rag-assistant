"""Mesure rapide de la recherche, sans modèle de langage.
Pour chaque question qui a une réponse, regarde si les termes attendus
(expected_terms) se trouvent dans les k meilleurs passages, pour plusieurs
valeurs de k. Quelques secondes suffisent : le LLM n'est pas lancé.

Usage : python -m scripts.retrieval_eval eval/dataset.yaml --ks 5 10 20
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from app.search import SearchResult, search
from scripts.dataset import load_dataset


def contains_all(passages: list[SearchResult], terms: list[str]) -> bool:
    """Vrai si chaque terme apparaît dans l'ensemble des passages (casse ignorée)."""
    text = "\n".join(p.text for p in passages).lower()
    return all(term.lower() in text for term in terms)


def needed_k(passages: list[SearchResult], terms: list[str]) -> int | None:
    """Plus petit k tel que les k premiers passages contiennent tous les termes."""
    for k in range(1, len(passages) + 1):
        if contains_all(passages[:k], terms):
            return k
    return None


def first_page_rank(
    passages: list[SearchResult], expected_sources: list[str]
) -> int | None:
    """Rang du premier passage venant d'une page attendue."""
    for rank, passage in enumerate(passages, start=1):
        if passage.source in expected_sources:
            return rank
    return None


def percent(count: int, total: int) -> str:
    return f"{count}/{total} ({100 * count / total:.0f} %)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Mesure rapide de la recherche.")
    parser.add_argument("dataset", type=Path, help="fichier YAML des questions")
    parser.add_argument(
        "--ks", type=int, nargs="+", required=True,
        help="valeurs de k à comparer, par ex. 5 10 20",
    )
    args = parser.parse_args()

    ks = sorted(set(args.ks))
    questions = [q for q in load_dataset(args.dataset) if not q.should_refuse]

    # Une seule recherche par question, avec le plus grand k : les k plus
    # petits sont le début de la même liste (la recherche est exacte).
    results = []  # (question, k nécessaire, rang de la première bonne page)
    for q in questions:
        passages = search(q.question, k=ks[-1])
        results.append(
            (
                q,
                needed_k(passages, q.expected_terms),
                first_page_rank(passages, q.expected_sources),
            )
        )

    total = len(results)
    print(f"{total} questions avec réponse\n")

    print("Questions dont les passages contiennent TOUS les termes attendus :")
    for k in ks:
        found = sum(1 for _, n, _ in results if n is not None and n <= k)
        print(f"  k = {k:>2} : {percent(found, total)}")

    print("\nBonne page parmi les k premiers passages (critère indulgent) :")
    for k in ks:
        found = sum(1 for _, _, r in results if r is not None and r <= k)
        print(f"  k = {k:>2} : {percent(found, total)}")

    by_category = defaultdict(list)
    for item in results:
        by_category[item[0].category].append(item)

    print("\nTermes attendus trouvés, par catégorie (nombre de questions) :")
    print("  " + "catégorie".ljust(14) + "n".rjust(3)
          + "".join(f"k={k}".rjust(8) for k in ks))
    for category, items in by_category.items():
        cells = "".join(
            str(sum(1 for _, n, _ in items if n is not None and n <= k)).rjust(8)
            for k in ks
        )
        print(f"  {category:<14}{len(items):>3}{cells}")

    print(f"\nQuestions non résolues à k = {ks[0]} :")
    for q, n, r in results:
        if n is None or n > ks[0]:
            terms = f"k = {n}" if n is not None else f"jamais (k ≤ {ks[-1]})"
            page = f"rang {r}" if r is not None else "absente"
            print(f"  {q.id:<34} {q.category:<13} termes : {terms:<16} page : {page}")


if __name__ == "__main__":
    main()