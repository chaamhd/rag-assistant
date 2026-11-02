"""Résume les durées des questions à partir des logs JSON de l'API.

Usage : docker compose logs api --no-log-prefix | python -m scripts.latency_report
"""
import json
import statistics
import sys

FIELDS = {
    "search done": ("retrieve_ms", "rerank_ms"),
    "question answered": ("search_ms", "first_token_ms", "llm_ms", "total_ms"),
}


def main() -> None:
    rows: dict[str, list[dict]] = {message: [] for message in FIELDS}
    for line in sys.stdin:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("message") in rows:
            rows[data["message"]].append(data)
    for message, fields in FIELDS.items():
        print(f"{message} : {len(rows[message])} lignes")
        for field in fields:
            values = sorted(r[field] for r in rows[message] if r.get(field) is not None)
            if not values:
                continue
            median = statistics.median(values)
            p90 = values[min(len(values) - 1, int(len(values) * 0.9))]
            print(f"  {field:15} médiane {median:7.0f} ms   p90 {p90:7.0f} ms   max {values[-1]:7.0f} ms")


if __name__ == "__main__":
    main()