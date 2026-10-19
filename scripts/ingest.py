import json
from pathlib import Path

from app.config import settings
from app.db import connect
from app.embeddings import document_text, embed_documents

CHUNKS_FILE = Path("data/chunks.jsonl")
BATCH_SIZE = 64

SCHEMA = f"""
CREATE TABLE chunks (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    section     TEXT NOT NULL,
    chunk_index INT  NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector({settings.embedding_dim}) NOT NULL
)
"""

INSERT = (
    "INSERT INTO chunks (id, source, title, section, chunk_index, text, embedding) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


def load_chunks() -> list[dict]:
    with CHUNKS_FILE.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> None:
    chunks = load_chunks()
    print(f"{len(chunks)} passages à vectoriser (modèle : {settings.embedding_model})")

    with connect() as conn:
        # Reconstruction complète : si le modèle (donc la dimension) change,
        # la table est recréée avec le bon type de colonne.
        conn.execute("DROP TABLE IF EXISTS chunks")
        conn.execute(SCHEMA)

        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            vectors = embed_documents(
                [document_text(c["title"], c["section"], c["text"]) for c in batch],
                batch_size=BATCH_SIZE,
            )
            with conn.cursor() as cur:
                cur.executemany(
                    INSERT,
                    [
                        (c["id"], c["source"], c["title"], c["section"],
                         c["index"], c["text"], v)
                        for c, v in zip(batch, vectors)
                    ],
                )
            print(f"  {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)}")

    print("Terminé.")


if __name__ == "__main__":
    main()