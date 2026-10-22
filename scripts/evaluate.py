from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.llm import LLMError, generate
from app.prompts import build_messages
from app.search import search
from scripts.dataset import DatasetError, Question, load_dataset
from scripts.eval_metrics import first_rank, score_answer


def evaluate_question(q: Question, runs: int) -> dict:
    results = search(q.question)  # la recherche est déterministe : une seule fois
    sources = [r.source for r in results]
    passages_text = "\n".join(r.text for r in results)

    outcomes = []
    for _ in range(runs):
        answer = generate(build_messages(q.question, results)).strip()
        outcomes.append(
            score_answer(
                answer=answer,
                should_refuse=q.should_refuse,
                expected_terms=q.expected_terms,
                expected_sources=q.expected_sources,
                sources=sources,
                passages_text=passages_text,
            )
        )

    return {
        "id": q.id,
        "category": q.category,
        "question": q.question,
        "should_refuse": q.should_refuse,
        "expected_sources": q.expected_sources,
        "retrieved": [
            {"source": r.source, "section": r.section, "score": round(r.score, 4)}
            for r in results
        ],
        "rank": None if q.should_refuse else first_rank(sources, q.expected_sources),
        "top_score": round(results[0].score, 4) if results else None,
        "runs": outcomes,
    }


def pct(count: int, total: int) -> str:
    return "n/a" if total == 0 else f"{100 * count / total:.0f} % ({count}/{total})"


def describe(scores: list[float]) -> str:
    if not scores:
        return "n/a"
    return (
        f"min {min(scores):.2f} | médiane {statistics.median(scores):.2f} "
        f"| max {max(scores):.2f}"
    )


def best_threshold(with_answer: list[float], without_answer: list[float]):
    """Seuil de score qui minimise les erreurs de la règle « refuser si score < seuil »."""
    best = None
    for threshold in sorted(set(with_answer + without_answer)):
        errors = sum(s < threshold for s in with_answer) + sum(
            s >= threshold for s in without_answer
        )
        if best is None or errors < best[1]:
            best = (threshold, errors)
    return best


def print_summary(records: list[dict]) -> None:
    top_k = settings.search_top_k
    answerable = [r for r in records if not r["should_refuse"]]
    refusals = [r for r in records if r["should_refuse"]]
    line = "=" * 66

    print(f"\n{line}\nRECHERCHE (questions avec réponse : {len(answerable)})")
    hits = [r for r in answerable if r["rank"] is not None]
    mrr = (
        statistics.mean(1 / r["rank"] if r["rank"] else 0 for r in answerable)
        if answerable
        else 0
    )
    print(f"  Bonne page dans les {top_k} premiers : {pct(len(hits), len(answerable))}")
    print(f"  MRR (1 = toujours en tête)          : {mrr:.2f}")

    runs = [o for r in answerable for o in r["runs"]]
    answered = [o for o in runs if not o["refused"]]
    print(f"\n{line}\nRÉPONSES (questions avec réponse, tous essais confondus)")
    print(f"  Réponses correctes   : {pct(sum(o['correct'] for o in runs), len(runs))}")
    print(f"  Refus à tort         : {pct(sum(o['refused'] for o in runs), len(runs))}")
    print(f"  Parmi les {len(answered)} réponses non refusées :")
    print(f"    avec une citation valide     : {pct(sum(o['has_citation'] for o in answered), len(answered))}")
    print(f"    citent une page attendue     : {pct(sum(o['cites_expected_source'] for o in answered), len(answered))}")
    print(f"    avec du code absent des passages : {pct(sum(bool(o['unsupported_snippets']) for o in answered), len(answered))}")

    ref_runs = [o for r in refusals for o in r["runs"]]
    refused_ok = [o for o in ref_runs if o["correct"]]
    print(f"\n{line}\nREFUS (questions sans réponse : {len(refusals)})")
    print(f"  Refus corrects       : {pct(len(refused_ok), len(ref_runs))}")
    print(f"  Refus avec citation  : {pct(sum(o['cited_in_refusal'] for o in refused_ok), len(refused_ok))}")

    unstable = [
        r["id"] for r in records if len({o["correct"] for o in r["runs"]}) > 1
    ]
    print(f"\n{line}\nSTABILITÉ")
    print(f"  {len(unstable)} question(s) sur {len(records)} changent de résultat d'un essai à l'autre")
    for question_id in unstable:
        print(f"    - {question_id}")

    print(f"\n{line}\nPAR CATÉGORIE")
    print(f"  {'catégorie':<14}{'n':>3}   {'page trouvée':<14}{'résultat correct'}")
    for category in sorted({r["category"] for r in records}):
        group = [r for r in records if r["category"] == category]
        group_answerable = [r for r in group if not r["should_refuse"]]
        found = (
            pct(sum(r["rank"] is not None for r in group_answerable), len(group_answerable))
            if group_answerable
            else "—"
        )
        outcomes = [o for r in group for o in r["runs"]]
        print(f"  {category:<14}{len(group):>3}   {found:<14}{pct(sum(o['correct'] for o in outcomes), len(outcomes))}")

    with_answer = [r["top_score"] for r in answerable if r["top_score"] is not None]
    without_answer = [r["top_score"] for r in refusals if r["top_score"] is not None]
    print(f"\n{line}\nSCORE DU MEILLEUR PASSAGE")
    print(f"  questions avec réponse : {describe(with_answer)}")
    print(f"  questions sans réponse : {describe(without_answer)}")
    if with_answer and without_answer:
        threshold, errors = best_threshold(with_answer, without_answer)
        print(
            f"  Indicatif : un seuil à {threshold:.2f} donnerait {errors} erreur(s) "
            f"sur {len(with_answer) + len(without_answer)} questions (non appliqué)"
        )


def print_failures(records: list[dict]) -> None:
    print("\n" + "=" * 66 + "\nÀ RELIRE (premier essai fautif de chaque question)")
    for r in records:
        bad = next((o for o in r["runs"] if not o["correct"]), None)
        if bad is None:
            continue
        if r["should_refuse"]:
            kind = "aurait dû refuser"
        elif bad["refused"]:
            kind = "refus à tort"
        else:
            kind = "termes attendus absents"
        excerpt = " ".join(bad["answer"].split())[:160]
        print(f"  - {r['id']} ({kind})\n      {excerpt}")

def print_flags(records: list[dict]) -> None:
    print("\n" + "=" * 66)
    print("À CLASSER À LA MAIN : code absent des passages, citations hors pages attendues")
    for r in records:
        if r["should_refuse"]:
            continue
        snippets: list[str] = []
        off_pages: list[str] = []
        for o in r["runs"]:
            snippets += [s for s in o["unsupported_snippets"] if s not in snippets]
            for n in o["citations"]:
                if 1 <= n <= len(r["retrieved"]):
                    page = r["retrieved"][n - 1]["source"]
                    if page not in r["expected_sources"] and page not in off_pages:
                        off_pages.append(page)
        if snippets or off_pages:
            print(f"  - {r['id']}")
            if snippets:
                print(f"      code : {snippets}")
            if off_pages:
                print(f"      pages citées hors pages attendues : {off_pages}")

def git_commit() -> str:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return done.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Évalue la recherche et les réponses de l'assistant."
    )
    parser.add_argument("dataset", type=Path, help="fichier YAML des questions")
    parser.add_argument("--runs", type=int, required=True, help="essais par question")
    parser.add_argument("--output", type=Path, required=True, help="résultats JSON détaillés")
    parser.add_argument("--limit", type=int, help="ne traiter que les N premières questions")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs doit valoir au moins 1")

    try:
        questions = load_dataset(args.dataset)
    except DatasetError as exc:
        print(f"Jeu de questions invalide :\n{exc}")
        return 1
    if args.limit:
        questions = questions[: args.limit]

    records = []
    started = time.perf_counter()
    try:
        for number, q in enumerate(questions, start=1):
            record = evaluate_question(q, args.runs)
            records.append(record)
            marks = "".join("✓" if o["correct"] else "✗" for o in record["runs"])
            print(f"[{number}/{len(questions)}] {marks:<5} {q.id}", flush=True)
    except LLMError as exc:
        print(f"\nErreur du modèle : {exc}\nOllama est-il lancé ?")
        return 1
    elapsed = time.perf_counter() - started

    print_summary(records)
    print_failures(records)
    print_flags(records)
    print(f"\nDurée : {elapsed / 60:.1f} min")

    payload = {
        "meta": {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_commit": git_commit(),
            "dataset": str(args.dataset),
            "questions": len(questions),
            "runs": args.runs,
            "llm_model": settings.llm_model,
            "llm_temperature": settings.llm_temperature,
            "embedding_model": settings.embedding_model,
            "search_top_k": settings.search_top_k,
        },
        "questions": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Résultats détaillés : {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())