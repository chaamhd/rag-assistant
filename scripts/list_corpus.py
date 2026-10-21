from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage : python -m scripts.list_corpus <chunks.jsonl>")
        return 2

    counts: Counter = Counter()
    titles: dict[str, str] = {}
    with Path(sys.argv[1]).open(encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            counts[chunk["source"]] += 1
            titles.setdefault(chunk["source"], chunk["title"])

    for source in sorted(counts):
        print(f"{counts[source]:3d}  {source}  --  {titles[source]}")
    print(f"\n{len(counts)} pages, {sum(counts.values())} passages")
    return 0


if __name__ == "__main__":
    sys.exit(main())