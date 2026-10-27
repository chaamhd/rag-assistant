"""Compare deux fichiers de résultats produits par scripts.evaluate.

Usage : python -m scripts.compare_results <avant.json> <après.json>

Seules les questions présentes dans les deux fichiers sont comparées.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VOLATILE_META = {"date", "git_commit"}
NOT_RECORDED = "non enregistré"
LINE = "=" * 66


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "meta": data.get("meta", {}),
        "questions": {q["id"]: q for q in data["questions"]},
    }


def meta_differences(before: dict, after: dict) -> list[tuple]:
    keys = sorted((set(before) | set(after)) - VOLATILE_META)
    differences = []
    for key in keys:
        old = before.get(key, NOT_RECORDED)
        new = after.get(key, NOT_RECORDED)
        if old != new:
            differences.append((key, old, new))
    return differences


def indicators(records: list[dict]) -> list[tuple]:
    """(libellé, nombre, total, plus_haut_est_mieux) pour chaque indicateur."""
    answerable = [r for r in records if not r["should_refuse"]]
    runs = [o for r in answerable for o in r["runs"]]
    answered = [o for o in runs if not o["refused"]]
    refusal_runs = [o for r in records if r["should_refuse"] for o in r["runs"]]
    return [
        ("Réponses correctes", sum(o["correct"] for o in runs), len(runs), True),
        ("Refus à tort", sum(o["refused"] for o in runs), len(runs), False),
        (
            "Réponses à côté",
            sum(not o["refused"] and not o["correct"] for o in runs),
            len(runs),
            False,
        ),
        (
            "Refus corrects (questions sans réponse)",
            sum(o["correct"] for o in refusal_runs),
            len(refusal_runs),
            True,
        ),
        (
            "Code absent des passages (réponses non refusées)",
            sum(bool(o["unsupported_snippets"]) for o in answered),
            len(answered),
            False,
        ),
    ]


def share(count: int, total: int) -> float | None:
    return None if total == 0 else 100 * count / total


def show(count: int, total: int) -> str:
    value = share(count, total)
    return "n/a" if value is None else f"{value:.0f} % ({count}/{total})"


def correct_runs(record: dict) -> int:
    return sum(o["correct"] for o in record["runs"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare deux fichiers de résultats.")
    parser.add_argument("before", type=Path, help="résultats de référence")
    parser.add_argument("after", type=Path, help="résultats à comparer")
    args = parser.parse_args()

    before, after = load(args.before), load(args.after)
    common = [i for i in before["questions"] if i in after["questions"]]
    only_one_side = set(before["questions"]) ^ set(after["questions"])
    if not common:
        parser.error("aucune question en commun entre les deux fichiers")
    records_before = [before["questions"][i] for i in common]
    records_after = [after["questions"][i] for i in common]
    alerts: list[str] = []

    print(f"{LINE}\nCONFIGURATION (seulement ce qui diffère)")
    differences = meta_differences(before["meta"], after["meta"])
    if not differences:
        print("  identique")
    for key, old, new in differences:
        print(f"  {key:<18}: {old}  →  {new}")
    if only_one_side:
        alerts.append(
            f"les fichiers n'ont pas les mêmes questions : "
            f"{len(common)} communes comparées, {len(only_one_side)} ignorées"
        )

    print(f"\n{LINE}\nINDICATEURS ({len(common)} questions communes)")
    print(f"  {'':<50}{'avant':>15}{'après':>15}{'écart':>10}")
    for (label, a_count, a_total, higher), (_, b_count, b_total, _) in zip(
        indicators(records_before), indicators(records_after)
    ):
        a_share, b_share = share(a_count, a_total), share(b_count, b_total)
        gap = ""
        if a_share is not None and b_share is not None:
            gap = f"{b_share - a_share:+.0f} pts"
            worse = b_share < a_share if higher else b_share > a_share
            if worse:
                alerts.append(f"« {label} » se dégrade : {a_share:.0f} % → {b_share:.0f} %")
        print(f"  {label:<50}{show(a_count, a_total):>15}{show(b_count, b_total):>15}{gap:>10}")

    print(f"\n{LINE}\nPAR CATÉGORIE (résultat correct)")
    for category in sorted({r["category"] for r in records_before}):
        ids = [i for i in common if before["questions"][i]["category"] == category]
        a_runs = [o for i in ids for o in before["questions"][i]["runs"]]
        b_runs = [o for i in ids for o in after["questions"][i]["runs"]]
        a_text = show(sum(o["correct"] for o in a_runs), len(a_runs))
        b_text = show(sum(o["correct"] for o in b_runs), len(b_runs))
        print(f"  {category:<16}{a_text:>15}{b_text:>15}")

    improved, degraded = [], []
    for question_id in common:
        old, new = before["questions"][question_id], after["questions"][question_id]
        old_rate = correct_runs(old) / len(old["runs"])
        new_rate = correct_runs(new) / len(new["runs"])
        change = (
            f"  {question_id:<34}"
            f"{correct_runs(old)}/{len(old['runs'])} → {correct_runs(new)}/{len(new['runs'])}"
        )
        if new_rate > old_rate:
            improved.append(change)
        elif new_rate < old_rate:
            degraded.append(change)

    print(f"\n{LINE}\nQUESTIONS AMÉLIORÉES : {len(improved)}")
    print("\n".join(improved))
    print(f"\nQUESTIONS DÉGRADÉES : {len(degraded)}")
    print("\n".join(degraded))
    if degraded:
        alerts.append(f"{len(degraded)} question(s) dégradée(s)")

    print(f"\n{LINE}\nPOINTS D'ATTENTION")
    print("\n".join(f"  - {alert}" for alert in alerts) if alerts else "  aucun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())