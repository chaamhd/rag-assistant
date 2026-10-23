from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from app.search import search
from scripts.dataset import load_dataset
from scripts.diagnose import classify
from scripts.eval_metrics import all_terms_present


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage : python -m scripts.context_check <resultats.json> <questions.yaml>")
        return 2

    results_file = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    baseline = {q["id"]: q for q in results_file["questions"]}

    rows = []
    for q in load_dataset(Path(sys.argv[2])):
        if q.should_refuse:
            continue
        context = "\n".join(r.text for r in search(q.question))
        record = baseline[q.id]
        failures = sum(classify(o) != "correcte" for o in record["runs"])
        rows.append(
            {
                "id": q.id,
                "category": q.category,
                "page": record["rank"] is not None,
                "context": all_terms_present(context, q.expected_terms),
                "failures": failures,
                "runs": len(record["runs"]),
            }
        )

    summary: Counter = Counter()
    for row in rows:
        summary[(row["context"], "corrects")] += row["runs"] - row["failures"]
        summary[(row["context"], "échecs")] += row["failures"]

    print("LES TERMES ATTENDUS ÉTAIENT-ILS DANS LES 5 PASSAGES ENVOYÉS AU MODÈLE ?")
    print(f"  {'':<38}{'essais corrects':>16}{'essais en échec':>17}")
    print(f"  {'oui (le modèle avait la réponse)':<38}{summary[(True, 'corrects')]:>16}{summary[(True, 'échecs')]:>17}")
    print(f"  {'non (réponse absente du contexte)':<38}{summary[(False, 'corrects')]:>16}{summary[(False, 'échecs')]:>17}")

    print("\nQUESTIONS EN ÉCHEC")
    print(f"  {'question':<30}{'catégorie':<14}{'page':<6}{'contexte':<10}échecs")
    for row in sorted(rows, key=lambda r: -r["failures"]):
        if row["failures"] == 0:
            continue
        print(
            f"  {row['id']:<30}{row['category']:<14}"
            f"{'oui' if row['page'] else 'non':<6}"
            f"{'oui' if row['context'] else 'non':<10}"
            f"{row['failures']}/{row['runs']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())