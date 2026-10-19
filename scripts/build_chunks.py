import json
import random
import statistics
from dataclasses import asdict
from pathlib import Path

from app.chunking import chunk_document

RAW = Path("data/raw")
OUT = Path("data/chunks.jsonl")


def main():
    files = sorted(RAW.rglob("*.md"))
    chunks = []
    for f in files:
        rel = f.relative_to(RAW).as_posix()
        chunks.extend(chunk_document(rel, f.read_text(encoding="utf-8")))

    with OUT.open("w", encoding="utf-8") as out:
        for c in chunks:
            record = asdict(c)
            record["id"] = f"{c.source}#{c.index}"
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    sizes = [len(c.text) for c in chunks]
    print(f"Fichiers : {len(files)} | Passages : {len(chunks)}")
    print(
        f"Taille (caractères) : min {min(sizes)} | médiane "
        f"{int(statistics.median(sizes))} | max {max(sizes)}"
    )
    print(f"Passages < 300 caractères : {sum(s < 300 for s in sizes)}")

    random.seed(0)
    for c in random.sample(chunks, 3):
        print("\n" + "=" * 60)
        print(f"{c.source} | {c.title} | {c.section}")
        print("-" * 60)
        print(c.text)


if __name__ == "__main__":
    main()