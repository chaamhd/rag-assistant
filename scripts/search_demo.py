import sys

from app.db import connect
from app.embeddings import embed_query

DEFAULT_QUESTION = "How do I install a specific Python version?"

SEARCH = """
SELECT source, section, text, 1 - (embedding <=> %(q)s) AS score
FROM chunks
ORDER BY embedding <=> %(q)s
LIMIT 5
"""


def main() -> None:
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    print(f"Question : {question}\n")

    with connect() as conn:
        rows = conn.execute(SEARCH, {"q": embed_query(question)}).fetchall()

    for source, section, text, score in rows:
        preview = " ".join(text.split())[:200]
        print(f"[{score:.3f}] {source} | {section}\n    {preview}...\n")


if __name__ == "__main__":
    main()